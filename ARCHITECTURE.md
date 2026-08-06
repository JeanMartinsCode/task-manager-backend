# Arquitetura — Task Manager

## Visão Geral

```
┌───────────────────────────────────────────────────────────┐
│                      FastAPI REST API                      │
│  api/users.py   api/tasks.py   api/notifications.py        │
│  api/status.py                              main.py:/health│
└───────────────────────────┬─────────────────────────────────┘
                             │ Depends(get_db)
                    ┌────────▼────────┐
                    │    services.py   │
                    │  UserService     │
                    │  TaskService     │
                    │  EscalationService│
                    │  NotificationService│
                    └────────┬────────┘
                             │ SQLAlchemy ORM
                    ┌────────▼────────┐
                    │    models.py     │
                    │ User / Task /    │
                    │ Notification     │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  SQLite (StaticPool) │
                    └─────────────────┘

┌───────────────────────────────────────────────────────────┐
│                 scheduler.py (APScheduler)                  │
│  BackgroundScheduler, job "escalate_urgent_tasks"           │
│  IntervalTrigger(minutes=1)                                  │
│  → run_escalation_job() abre sua própria sessão,             │
│    chama EscalationService.escalate_urgent_tasks(),          │
│    loga em JSON estruturado, atualiza _last_run_info          │
└───────────────────────────────────────────────────────────┘
```

Ciclo de vida: o `BackgroundScheduler` é criado e iniciado no `lifespan` do FastAPI (`main.py`), guardado em `app.state.scheduler`, e parado (`shutdown(wait=False)`) quando a aplicação encerra.

## Componentes

### `models.py`
Três modelos SQLAlchemy declarativos:
- **`User`**: `id`, `name`, `email` (único), `created_at`. Relaciona 1:N com `Task`.
- **`Task`**: `id`, `title`, `description`, `priority` (`PriorityEnum`: `LOW`/`MEDIUM`/`HIGH`), `status` (`TaskStatusEnum`: `PENDING`/`IN_PROGRESS`/`COMPLETED`), `deadline`, `assigned_to` (FK → `User`), `created_at`, `updated_at`. Relaciona 1:N com `Notification` (`cascade="all, delete-orphan"` — apagar uma tarefa apaga suas notificações).
- **`Notification`**: `id`, `task_id` (FK → `Task`), `notification_type` (`NotificationTypeEnum`), `message`, `created_at`.

### `schemas.py`
Schemas Pydantic separados por operação: `*Create` (validação de entrada — ex. `deadline` deve ser futuro), `*Update` (todos os campos opcionais, `None` não sobrescreve), `*Read` (saída, `model_config = {"from_attributes": True}` para serializar direto de objetos ORM).

### `services.py`
Toda a regra de negócio vive aqui, desacoplada do HTTP:
- **`UserService`**: criar/consultar usuários, valida e-mail duplicado.
- **`TaskService`**: CRUD de tarefas com filtros (status, prioridade, usuário) e paginação (`skip`/`limit`).
- **`EscalationService`**: `escalate_urgent_tasks(db)` — a regra central do produto (ver "Fluxo de Dados" abaixo).
- **`NotificationService`**: consulta de notificações por tarefa, por usuário ou geral, sempre mais-recente-primeiro.

### `scheduler.py`
Encapsula o job de background: `create_scheduler()` monta um `BackgroundScheduler` com o job de escalação registrado; `run_escalation_job()` abre sua própria sessão de banco, roda a escalação, loga em JSON estruturado e nunca deixa uma exceção derrubar o processo. O resultado da última execução fica em `_last_run_info` (estado em memória), lido pelo endpoint de status.

### `api/`
Routers FastAPI finos — cada endpoint apenas valida entrada (via schema), chama o service correspondente e traduz `ValueError`/`None` em `HTTPException` (400/404).

## Fluxo de Dados: Criar Tarefa → Escalação → Notificação

1. Cliente faz `POST /api/tasks` com um `deadline` futuro e prioridade `LOW`/`MEDIUM`. `TaskService.create_task` valida o usuário e persiste a tarefa com `status=PENDING`.
2. A cada 1 minuto, o job do `scheduler.py` roda `EscalationService.escalate_urgent_tasks(db)`.
3. O service busca tarefas **não concluídas**, com **prioridade ≠ HIGH** e **deadline ≤ agora + 24h**. Cada uma tem a prioridade elevada para `HIGH` e ganha uma `Notification` (`type=ESCALATION`) com uma mensagem indicando as horas restantes.
4. O job atualiza `_last_run_info` (contagem + timestamp) e loga o resultado em JSON.
5. Cliente pode consultar `GET /api/tasks/{id}` (vê a nova prioridade), `GET /api/notifications?task_id=...` (vê a notificação) ou `GET /api/status` (vê `last_escalation_time`/`last_escalation_count`).
6. Como o filtro exclui tarefas já `HIGH`, rodar o job de novo sobre a mesma tarefa **não** gera escalação nem notificação duplicada — a idempotência é uma consequência direta do filtro, não de um controle extra.

## Decisões de Design

| Decisão | Por quê |
|---|---|
| **SQLite** em vez de PostgreSQL | Zero setup, arquivo único, suficiente para o volume do MVP. `DATABASE_URL` já é lida do ambiente, mas trocar de backend também exige rever o `connect_args={"check_same_thread": False}` e o `StaticPool` em `database.py`, que são específicos de SQLite |
| **APScheduler** em vez de Celery+Redis | Roda no mesmo processo da API, sem infraestrutura externa; adequado para um único job de baixa frequência |
| **Camada de `services` separada da API** | Regra de negócio testável sem subir HTTP; os routers ficam finos e triviais |
| **`StaticPool` no SQLAlchemy** | Necessário para compartilhar uma única conexão SQLite entre threads (API + scheduler rodando em paralelo) |
| **Caminho de import único (`task_manager.X`), pacote sempre instalado** | Um único nome canônico para cada módulo. O padrão anterior de import duplo (`try: task_manager.X / except: src.task_manager.X`) permitia duas identidades para o mesmo arquivo e foi removido — ver "Identidade de módulo" abaixo |
| **Estado da última escalação em memória** (não persistido) | Simples e suficiente para o MVP; é perdido em restart, o que é aceitável pois o job roda a cada minuto |

## Identidade de módulo (import único)

**Regra:** todo módulo é importado por um único caminho canônico — `task_manager.X` — em `src/`, nos testes, no `alembic/env.py` e no `Makefile`. O prefixo `src.task_manager.` não é usado em lugar nenhum, e o pacote é sempre instalado (`uv sync` / `pip install -e .`) em vez de rodado direto de um checkout cru.

**Por que isso é uma regra e não um detalhe de estilo:** até então, cada módulo carregava um import de compatibilidade (`try: from task_manager.X / except ModuleNotFoundError: from src.task_manager.X`) que pretendia suportar os dois modos. Com o pacote instalado, o `try` passa a funcionar — mas quem alcançava o mesmo arquivo pelo caminho `src.task_manager.*` (testes, `alembic/env.py`) o carregava uma **segunda vez, sob outra identidade de módulo**. Como `database.py` cria seu `engine` no nível do módulo, o resultado eram duas engines e duas conexões `StaticPool` distintas para o mesmo arquivo SQLite, cada uma enxergando um estado diferente.

Evidências concretas do problema, antes da correção: `issubclass(User, Base)` retornando `False` (duas hierarquias de classe para o mesmo modelo), um `PermissionError` do Windows ao tentar remover o arquivo do banco após `engine.dispose()` (outra conexão seguia aberta) e 29 dos 202 testes falhando sob `uv sync && alembic upgrade head && pytest`. O mesmo mecanismo ameaçava silenciosamente o `limiter` de `rate_limit.py` e o `_last_run_info` de `scheduler.py`, que também são estado de nível de módulo.

**Guarda permanente:** `tests/test_module_identity.py` agrupa todas as entradas de `sys.modules` relacionadas a `task_manager` pelo caminho físico real do arquivo e falha se algum arquivo aparecer sob mais de um nome de módulo. Ele não procura pelo padrão `try/except` específico — verifica o invariante, então qualquer mecanismo futuro de duplicação (um `sys.path.insert` esquecido, um import de compatibilidade reintroduzido, um segundo registro de pacote) o dispara igual. O CI (`.github/workflows/ci.yml`) roda a suíte **contra o pacote instalado**, que é a condição sob a qual o bug se manifestava — rodar contra um checkout não instalado nunca o teria detectado.

## Autenticação e Autorização

**Decisão (estágio atual — MVP):** todo endpoint sob `/api/*` exige o header `X-API-Key`, validado por `security.require_api_key` (`src/task_manager/security.py`) contra a variável de ambiente `API_KEY`, usando `secrets.compare_digest` (comparação em tempo constante, evita timing attack). `/health` fica público de propósito — é a única rota sem dado algum, e probes de infraestrutura (load balancer, orquestrador) tipicamente não carregam credenciais.

**Por que uma API key compartilhada, e não OAuth2/JWT já de início:** o domínio hoje não tem conceito de "usuário autenticado fazendo a requisição" — `User` é uma entidade de negócio (a quem uma `Task` é atribuída), não uma conta com login. Nenhuma rota precisa hoje saber *quem* está chamando, só que quem chama é confiável. Implementar OAuth2/JWT agora seria construir infraestrutura de login para um requisito que não existe, adicionando complexidade sem benefício real (over-engineering).

**Caminho de evolução:** `require_api_key` foi isolado em `security.py` exatamente para ser substituível — quando houver necessidade real de identidade por usuário, troca-se essa dependência por uma que resolve e retorna o `User` autenticado (ex. `get_current_user` via OAuth2/JWT), mantendo a mesma forma de injeção (`Depends(...)`) nos routers. A partir daí, autorização por recurso (ex. "usuário só edita/deleta suas próprias tasks") vira uma checagem de `current_user.id == task.assigned_to` dentro do endpoint.

**Débito técnico consciente — autorização por recurso:** o pentest sugeriu "usuário só edita/deleta suas próprias tasks, se esse conceito já existir no domínio". Ele não existe de forma utilizável hoje: `assigned_to` identifica a quem uma tarefa pertence *no domínio*, mas nenhuma requisição HTTP se identifica como um `User` específico (só como "um cliente com a API key"). Implementar essa checagem agora exigiria inventar uma identidade de requisição sem um mecanismo real de login por trás — autorização de fachada, não autorização de verdade. Por isso, com uma única API key compartilhada, qualquer chamador autenticado tem os mesmos privilégios que qualquer outro (não há tenant/usuário isolado). Fica registrado como próximo passo natural junto da evolução para OAuth2/JWT, quando o produto precisar de multi-tenancy real — ver [SECURITY.md](SECURITY.md).

## Rate Limiting

`rate_limit.py` aplica um limite por IP (via `slowapi`) nos endpoints de escrita (`POST`/`PUT`/`DELETE`), configurável pela variável `RATE_LIMIT_WRITE` (padrão `20/minute`). Endpoints de leitura (`GET`) não são limitados.

**Isso é redundância, não substituto:** em um deploy de produção real, rate limiting deveria existir também (e principalmente) numa camada de gateway/proxy reverso (nginx, API gateway, Cloudflare etc.) — mais difícil de contornar e sem custo de CPU/memória da aplicação por requisição rejeitada. A camada na aplicação aqui existe para proteger deploys que ainda não têm essa camada de borda, e como segunda linha de defesa para os que já têm.

## Melhorias Futuras

- Migrar `models.py` de `Column()` para `Mapped[]`/`mapped_column()` (tipagem estática nativa do SQLAlchemy 2.0, eliminaria os `# type: ignore` atuais)
- PostgreSQL para produção (múltiplas conexões concorrentes reais)
- Celery + Redis se o volume de jobs crescer além de uma única verificação por minuto
- Persistir o histórico de execuções do scheduler (hoje só a última fica em memória)
- Autenticação/autorização e multi-tenancy
- Migrar queries de `db.query()` (legado) para `select()`/`session.execute()` (API 2.0 do SQLAlchemy, com tipagem melhor)
