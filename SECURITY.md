# Security — Task Manager Backend

Resumo das correções aplicadas em resposta a testes de segurança (pentest manual + análise estática com Bandit e pip-audit, rodado localmente em ambiente isolado). Cada item segue TDD: teste que comprova a falha (RED) → correção → teste passando (GREEN), com a suíte completa (`pytest --cov`), `ruff check` e `mypy` limpos antes de avançar para o próximo item.

Testes de regressão de segurança vivem em `tests/security/`. Suíte final (rodada 1 + rodada 2): **202 testes passando**, cobertura 91.10%, `ruff` e `mypy` limpos.

---

## Rodada 1

---

## 1. [ALTO] Ausência total de autenticação/autorização

**Vulnerabilidade:** todos os endpoints (`/api/users`, `/api/tasks`, `/api/notifications`, `/api/status`) eram públicos — qualquer requisição HTTP podia criar, ler, editar ou deletar qualquer recurso, sem verificação de identidade.

**Correção:** `src/task_manager/security.py` — dependência `require_api_key` (FastAPI `Depends`) validando o header `X-API-Key` contra a variável de ambiente `API_KEY`, com `secrets.compare_digest` (comparação em tempo constante). Aplicada via `dependencies=[Depends(require_api_key)]` em todos os routers (`users`, `tasks`, `notifications`, `status`). `/health` permanece público (única rota sem dado algum; probes de infra não carregam credenciais). Servidor sem `API_KEY` configurada falha fechado (500), nunca abre acesso silenciosamente.

**Teste de regressão:** `tests/security/test_auth.py` (18 testes) — cobre todo endpoint protegido sem chave (401), com chave errada (401), com chave certa (200/201), `/health` público, e fail-closed sem `API_KEY` no servidor.

**Débito técnico consciente:** o pentest sugeriu autorização por recurso ("usuário só edita/deleta suas próprias tasks"). Não implementado porque o domínio não tem hoje um conceito real de "usuário autenticado fazendo a requisição" — `User` é uma entidade de negócio (a quem uma `Task` é atribuída via `assigned_to`), não uma conta com login. Com uma única API key compartilhada, todo chamador autenticado tem os mesmos privilégios. Isso é aceitável para o estágio atual (single-tenant, MVP), mas **precisa ser resolvido antes de multi-tenancy real**: nesse ponto, `require_api_key` deve ser substituído por uma dependência OAuth2/JWT que resolve e retorna o `User` autenticado (o código já está estruturado para essa troca — ver `security.py` e a seção "Autenticação e Autorização" em ARCHITECTURE.md), e os endpoints de `PUT`/`DELETE` em `tasks.py` devem ganhar uma checagem `current_user.id == task.assigned_to`.

---

## 2. [MÉDIO] Erro 500 não tratado ao processar IDs muito grandes

**Vulnerabilidade:** um ID inteiro maior que o limite do SQLite (ex. `999999999999999999999999`) causava `OverflowError` não capturado no driver `sqlite3`, subindo como 500 genérico não tratado — potencial vazamento de detalhes internos dependendo da configuração do servidor ASGI.

**Correção:** duas camadas independentes.
1. `src/task_manager/constants.py` (`MAX_SQLITE_INTEGER = 9_223_372_036_854_775_807`, o máximo de um INTEGER assinado de 64 bits do SQLite) aplicado como `le=` em todo path param de ID (`Path(..., ge=1, le=MAX_SQLITE_INTEGER)` em `users.py`/`tasks.py`), query param (`assigned_to_id`, `task_id`, `user_id`) e campo de corpo (`TaskCreate.assigned_to_id`) — rejeita com `422` antes de chegar ao banco.
2. `main.py` — handler global `@app.exception_handler(Exception)` captura qualquer exceção não prevista, loga internamente com um `error_id` (UUID) correlacionável, e retorna só `{"detail": "Internal server error", "error_id": "..."}` ao cliente — nunca stack trace ou detalhe interno. Handlers mais específicos do FastAPI (`HTTPException`, `RequestValidationError`) continuam tendo precedência, então 400/404/422 não são afetados.

**Teste de regressão:** `tests/security/test_id_overflow.py` (9 testes) — IDs de overflow em todo path/query/body param retornam 422; e um teste que força uma exceção genérica (via `monkeypatch`) e verifica que a resposta é 500 genérico com `error_id`, sem vazar a mensagem original, tipo da exceção ou traceback.

---

## 3. [MÉDIO] Sem limite de tamanho em campos de texto

**Vulnerabilidade:** `name`, `title`, `description` (e `email`) aceitavam payloads arbitrariamente grandes (testado com 500KB) sem rejeição — vetor de DoS por amplificação de payload.

**Correção:** `max_length` em `src/task_manager/schemas.py`:
- `name`: 200 (DB é `String(255)`; nenhum nome real chega perto disso)
- `email`: 254 (máximo prático de RFC 5321 — não pedido explicitamente, mas coberto pela mesma razão dos demais campos de texto livre)
- `title`: 200 (DB é `String(255)`; título é rótulo curto, não documento)
- `description`: 2000 (~300-400 palavras; suficiente para descrição real, limita o pior caso a poucos KB em vez de centenas)

**Teste de regressão:** `tests/security/test_field_length_limits.py` (9 testes) — payload de 500KB em cada campo retorna 422; valor exatamente no limite é aceito; um caractere acima do limite é rejeitado.

---

## 4. [BAIXO] XSS armazenado — dados não sanitizados

**Vulnerabilidade:** payloads como `<script>alert(1)</script>` são armazenados e devolvidos crus no JSON.

**Decisão: não sanitizar.** Bloquear/filtrar tags HTML destruiria dados legítimos (ex. uma task cujo título é "corrigir a tag `<script>` do header.html") e daria falsa sensação de segurança — a defesa correta contra XSS é escapar na renderização, não filtrar na entrada, e a API não controla o contexto de renderização de cada consumidor. Documentado explicitamente em `API.md` ("Considerações de Segurança"), com a responsabilidade de escapar output atribuída claramente ao consumidor.

**Teste:** `tests/security/test_xss_storage.py` (2 testes) — não são testes de "correção" (nenhum código mudou), mas de **caracterização**: travam o comportamento atual (payload armazenado e devolvido verbatim) para que qualquer mudança futura de comportamento (ex. alguém adicionar sanitização sem atualizar a doc) quebre o teste e force uma decisão consciente.

---

## 5. [BAIXO] Ausência de rate limiting

**Vulnerabilidade:** 30 requisições consecutivas em ~180ms foram todas aceitas sem throttling.

**Correção:** `src/task_manager/rate_limit.py` — `slowapi.Limiter` por IP, aplicado via `@limiter.limit(RATE_LIMIT_WRITE)` nos endpoints de escrita (`POST /api/users`, `POST/PUT/DELETE /api/tasks`). Configurável pela env var `RATE_LIMIT_WRITE` (padrão `20/minute`; produção real deveria ajustar conforme tráfego esperado). Endpoints de leitura (`GET`) não são limitados. Documentado em ARCHITECTURE.md que isso é redundância, não substituto: produção real deveria ter rate limiting também (e principalmente) numa camada de gateway/proxy reverso, mais difícil de contornar e sem custo de CPU/memória da aplicação por requisição rejeitada.

**Teste de regressão:** `tests/security/test_rate_limiting.py` (3 testes) — suíte de testes fixa `RATE_LIMIT_WRITE=5/minute` (determinístico e rápido); confirma que a 6ª requisição de escrita na mesma janela retorna 429, que uma resposta 429 não tem efeito colateral (recurso não é criado), e que `GET` não é afetado. `tests/conftest.py` ganhou um fixture `autouse` que reseta o estado do limiter antes de cada teste, evitando vazamento de contagem entre testes que compartilham o mesmo `app`/`limiter` (singletons do processo).

---

## 6. [INFORMATIVO] Null byte aceito em campos de texto

**Vulnerabilidade:** strings com `\x00` eram aceitas e armazenadas sem erro — não explorável diretamente por esta API, mas uma armadilha para qualquer integração downstream que trate a string como C-string (truncamento silencioso) ou a escreva em logs/exports CSV (corrupção).

**Correção:** `_reject_null_bytes` em `schemas.py`, aplicado via `field_validator` em `UserCreate.name`, `UserCreate.email`, `TaskCreate.title`/`description` e `TaskUpdate.title`/`description` — rejeita com 422 qualquer valor contendo `\x00`.

**Teste de regressão:** `tests/security/test_null_bytes.py` (5 testes) — null byte em cada campo retorna 422; valor comum sem null byte continua aceito normalmente.

---

## Rodada 2

Segunda rodada de pentest, achados novos e independentes dos da rodada 1 (auth, overflow de ID, DoS de payload, rate limiting e null bytes seguem cobertos e sem alteração).

---

## 7. [ALTO] Comparação de datetime naive vs aware quebra o endpoint de tasks

**Vulnerabilidade:** `_validate_deadline` (`TaskCreate`/`TaskUpdate`) comparava `v <= datetime.utcnow()` diretamente. Um `deadline` ISO-8601 com timezone explícito — sufixo `Z` ou offset (`+03:00`), exatamente o formato que `Date.toISOString()` do JS produz — chega ao validator já como `datetime` *aware* (Pydantic faz esse parse), e comparar aware com naive levanta `TypeError: can't compare offset-naive and offset-aware datetimes`, não capturado → 500 em vez de validar corretamente. Reproduzia em `POST /api/tasks` e `PUT /api/tasks/{id}`.

**Correção:** `_normalize_deadline_to_utc` em `schemas.py` — se o `deadline` recebido for aware, converte para UTC e remove o tzinfo (`astimezone(timezone.utc).replace(tzinfo=None)`) antes de comparar e antes de retornar (ou seja, o valor armazenado no banco também fica normalizado). Naive é assumido como já-UTC, mantendo a convenção já existente no resto do código (`created_at`/`updated_at`, `EscalationService`). Isso garante que todo `deadline` que chega ao banco é consistentemente naive-UTC, comparável com o resto da aplicação.

**Teste de regressão:** `tests/security/test_deadline_timezone.py` (8 testes) — `deadline` com sufixo `Z` e com offset explícito, futuro (aceita, 201/200) e passado (rejeita, 422 nunca 500), em `POST` e `PUT`.

---

## 8. [MÉDIO] Overflow no parâmetro `skip` da paginação

**Vulnerabilidade:** `skip: int = Query(0, ge=0)` em `tasks.py`, `users.py` e `notifications.py` não tinha limite superior — o mesmo padrão já corrigido para IDs de recurso (`le=MAX_SQLITE_INTEGER`) não havia sido aplicado ao `skip`. Um valor como `999999999999999999999` causava `OverflowError` não capturado no `sqlite3` (parâmetro do `OFFSET`) → 500.

**Correção:** `le=MAX_SQLITE_INTEGER` adicionado ao `skip` nas três rotas, idêntico ao que já existe para IDs.

**Teste de regressão:** `tests/security/test_skip_overflow.py` (4 testes) — `skip` acima do limite retorna 422 nas três rotas; o valor limite (`MAX_SQLITE_INTEGER`) em si continua aceito.

---

## 9. [MÉDIO] Corpo de requisição sem limite de tamanho (DoS de memória)

**Vulnerabilidade:** `max_length` do Pydantic só rejeita um campo *depois* do corpo inteiro já ter sido lido e parseado como JSON. Um corpo de 48MB foi recebido e processado por completo (RSS do processo subiu ~150MB numa única requisição, ~1.7s) antes de ser rejeitado com 422 — DoS de memória/CPU independente do `max_length` já existir nos campos.

**Correção:** `src/task_manager/body_limit.py` — `BodySizeLimitMiddleware`, middleware ASGI puro que inspeciona o header `Content-Length` *antes* de Starlette ler um único byte do corpo, rejeitando com `413` qualquer requisição acima de `MAX_BODY_BYTES` (padrão 100KB, configurável via variável de ambiente do mesmo nome) — bem acima de qualquer payload legítimo dado os `max_length` já definidos, e ordens de magnitude abaixo de um payload de ataque. Registrado como o middleware mais externo em `main.py` (roda antes do rate limiting, da autenticação e do roteamento). Como o rate limiting (item 5, rodada 1), é defesa em profundidade — documentado que um limite de corpo também deveria existir na camada de gateway/proxy em produção real.

Efeito colateral necessário: `tests/security/test_field_length_limits.py` usava payloads de 500KB para provar o `max_length` de campo — como isso agora é maior que o novo teto de corpo, esses testes passaram a ser interceptados por este middleware (413) antes de chegar à validação de campo que queriam provar. Ajustado para 10KB (acima de qualquer `max_length` de campo, abaixo do teto de corpo), preservando a intenção original do teste.

**Teste de regressão:** `tests/security/test_body_size_limit.py` (3 testes) — corpo acima do teto retorna 413 e nunca chega ao banco; requisição de tamanho normal não é afetada.

---

## 10. [MÉDIO] Condição de corrida na unicidade de e-mail

**Vulnerabilidade:** `UserService.create_user` usava check-then-insert (`SELECT ... WHERE email = ?` seguido de `INSERT`), não atômico. Sob requisições concorrentes com o mesmo e-mail, mais de uma pode passar pelo check antes de qualquer commit — a constraint `unique=True` real do banco rejeita corretamente todo INSERT além do primeiro, mas o `IntegrityError` resultante não era capturado em lugar nenhum, caindo no handler genérico → 500 em vez do 400 "email already exists" esperado. Reproduzido com 5 requisições simultâneas: 1 sucesso, 1 erro 400 correto, 3 erros 500.

**Correção:** `db.commit()` em `create_user` agora dentro de `try/except IntegrityError` — captura, faz `db.rollback()`, e relança como o mesmo `ValueError("email already exists")` já usado no caminho não-concorrente. Nenhuma mudança necessária no route handler (já converte `ValueError` em 400).

**Teste de regressão:** `tests/security/test_email_race_condition.py` (2 testes) — **determinístico, não usa concorrência real de threads.** Investigação durante esta correção mostrou que threads de SO genuinamente concorrentes contra a conexão SQLite única compartilhada deste projeto (`StaticPool` em `database.py`) corrompem estado de baixo nível do cursor/fetch de linhas (`IndexError: tuple index out of range` vindo de dentro do processador de linhas do SQLAlchemy) em ~75% das tentativas — um problema separado e pré-existente da configuração de conexão, fora do escopo deste item, que tornaria um teste baseado em threads reais não-confiável independentemente da correção estar certa. Em vez disso, o teste usa duas sessões sequenciais: uma comita um usuário de verdade; o check de existência da outra é forçado (monkeypatch pontual, escopado a uma única instância) a "não encontrar nada", exatamente como aconteceria se tivesse rodado antes do primeiro commit — o INSERT que segue é inteiramente real e colide com a constraint UNIQUE de verdade, gerando um `IntegrityError` genuíno pelo mesmo caminho de código, sem depender de sorte de scheduling.

---

## Débito técnico consciente (resumo)

| Item | O que falta | Quando resolver |
|---|---|---|
| Autorização por recurso | `current_user.id == task.assigned_to` em `PUT`/`DELETE /api/tasks/{id}` | Quando o produto precisar de multi-tenancy real / usuários com login próprio |
| Identidade por usuário | API key única compartilhada → trocar por OAuth2/JWT (`get_current_user`) | Mesmo ponto acima — `security.py` já isolado para essa troca |
| Rate limiting de borda | Limite hoje só na aplicação (`slowapi`) | Antes de produção real: adicionar rate limiting no gateway/proxy reverso |
| Limite de corpo na borda | Limite hoje só na aplicação (`body_limit.py`) | Antes de produção real: adicionar limite de corpo também no gateway/proxy reverso |
| **Conexão SQLite única não é segura sob concorrência real de threads** | `database.py` usa `StaticPool` (uma única conexão física compartilhada por todas as sessions). Sob threads de SO genuinamente concorrentes, chamadas simultâneas de `cursor.execute()`/fetch em cursores diferentes da mesma conexão corrompem estado interno (`IndexError: tuple index out of range` observado em ~75% das tentativas em investigação da rodada 2). Serializar só o `before_cursor_execute` não é suficiente — o problema também aparece no fetch de linhas. | Antes de qualquer deploy que sirva tráfego real concorrente (mesmo com um único worker, um servidor ASGI real despacha handlers síncronos em thread pool, então isso não é só um artefato de teste). Opções: pool por conexão real (Postgres em produção, já cogitado em ARCHITECTURE.md), ou lock de aplicação em torno de toda a sessão (não só do `execute()`) se SQLite precisar continuar em produção |
| Migração `Column()` → `Mapped[]` | Débito pré-existente, não relacionado a segurança | Ver ARCHITECTURE.md "Melhorias Futuras" |
