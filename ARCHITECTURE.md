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
| **SQLite** em vez de PostgreSQL | Zero setup, arquivo único, suficiente para o volume do MVP; a troca futura exige só mudar `DATABASE_URL` (o ORM já abstrai o dialeto) |
| **APScheduler** em vez de Celery+Redis | Roda no mesmo processo da API, sem infraestrutura externa; adequado para um único job de baixa frequência |
| **Camada de `services` separada da API** | Regra de negócio testável sem subir HTTP; os routers ficam finos e triviais |
| **`StaticPool` no SQLAlchemy** | Necessário para compartilhar uma única conexão SQLite entre threads (API + scheduler rodando em paralelo) |
| **Import de compatibilidade (`try: from task_manager.X / except: from src.task_manager.X`)** | Permite que os módulos sejam importados tanto como pacote instalado (`task_manager`) quanto via `src.task_manager` (como os testes fazem), sem duplicar código |
| **Estado da última escalação em memória** (não persistido) | Simples e suficiente para o MVP; é perdido em restart, o que é aceitável pois o job roda a cada minuto |

## Melhorias Futuras

- Migrar `models.py` de `Column()` para `Mapped[]`/`mapped_column()` (tipagem estática nativa do SQLAlchemy 2.0, eliminaria os `# type: ignore` atuais)
- PostgreSQL para produção (múltiplas conexões concorrentes reais)
- Celery + Redis se o volume de jobs crescer além de uma única verificação por minuto
- Persistir o histórico de execuções do scheduler (hoje só a última fica em memória)
- Autenticação/autorização e multi-tenancy
- Migrar queries de `db.query()` (legado) para `select()`/`session.execute()` (API 2.0 do SQLAlchemy, com tipagem melhor)
