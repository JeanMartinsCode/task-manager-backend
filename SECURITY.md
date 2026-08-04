# Security — Task Manager Backend

Resumo das correções aplicadas na branch `security-hardening` em resposta a um teste de segurança (pentest manual + análise estática com Bandit e pip-audit, rodado localmente em ambiente isolado). Cada item segue TDD: teste que comprova a falha (RED) → correção → teste passando (GREEN), com a suíte completa (`pytest --cov`), `ruff check` e `mypy` limpos antes de avançar para o próximo item.

Testes de regressão de segurança vivem em `tests/security/`. Suíte final: **185 testes passando** (139 pré-existentes + 46 novos), cobertura 91.70%, `ruff` e `mypy` limpos.

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

## Débito técnico consciente (resumo)

| Item | O que falta | Quando resolver |
|---|---|---|
| Autorização por recurso | `current_user.id == task.assigned_to` em `PUT`/`DELETE /api/tasks/{id}` | Quando o produto precisar de multi-tenancy real / usuários com login próprio |
| Identidade por usuário | API key única compartilhada → trocar por OAuth2/JWT (`get_current_user`) | Mesmo ponto acima — `security.py` já isolado para essa troca |
| Rate limiting de borda | Limite hoje só na aplicação (`slowapi`) | Antes de produção real: adicionar rate limiting no gateway/proxy reverso |
| Migração `Column()` → `Mapped[]` | Débito pré-existente, não relacionado a segurança | Ver ARCHITECTURE.md "Melhorias Futuras" |
