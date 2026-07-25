# 📋 Task Manager — Escalação Automática de Prioridade

API REST em Python que gerencia tarefas e **escalona automaticamente a prioridade** de tarefas cujo prazo está se esgotando, sem depender de intervenção manual.

## 💡 Problema

Times que gerenciam tarefas em ferramentas genéricas costumam sofrer com:

- 📋 Tarefas que se perdem no backlog
- ⏰ Prazos que estouram sem ninguém perceber a tempo
- 🔴 Ausência de escalação automática (tarefas urgentes continuam com prioridade baixa)
- 👁️ Nenhuma visibilidade sobre o "risco" de uma tarefa (perto do prazo, atrasada, bloqueada)

## ✅ Solução

Um backend que:

- **Gerencia tarefas**: criação, leitura, atualização e remoção, com status (`PENDING` → `IN_PROGRESS` → `COMPLETED`) e prioridade (`LOW`, `MEDIUM`, `HIGH`)
- **Escalona prioridade automaticamente**: um job em background (APScheduler) roda a cada minuto e, para toda tarefa incompleta com prazo em até 24h e prioridade abaixo de `HIGH`, eleva a prioridade e registra uma notificação explicando o motivo
- **Gerencia usuários** e a atribuição de tarefas a eles
- **Registra notificações** de cada escalação, consultáveis por tarefa ou por usuário
- **Expõe status do sistema**: conectividade com o banco, contagem de tarefas por status/prioridade e dados da última execução da escalação
- **Expõe tudo via API REST** documentada automaticamente (OpenAPI/Swagger)

## 🛠️ Tecnologias

| Componente | Escolha | Motivo |
|---|---|---|
| Linguagem | Python 3.11+ | Tipagem estática, ecossistema maduro |
| Web Framework | FastAPI | Validação automática, docs OpenAPI, assíncrono |
| Banco de dados | SQLite + SQLAlchemy | Zero setup, ACID, suficiente para o MVP |
| Migrations | Alembic | Versionamento de schema |
| Scheduler | APScheduler | Job em background, sem infraestrutura externa (Redis/Celery) |
| Testes | pytest + pytest-cov | Fixtures ricas, cobertura de código |
| Qualidade | mypy + ruff | Tipagem estática e linting |

## 🚀 Como rodar localmente

Pré-requisitos: Python 3.11+ e [uv](https://github.com/astral-sh/uv) (ou `pip`).

```bash
# 1. Clonar o repositório
git clone <repo-url>
cd task-manager-backend

# 2. Instalar dependências
make install          # ou: pip install -e ".[dev]"

# 3. Rodar as migrations
make migrate           # ou: alembic upgrade head

# 4. Subir o servidor
make run                # ou: uvicorn src.task_manager.main:app --reload

# 5. Testar
curl http://localhost:8000/health
```

A documentação interativa da API fica disponível em `http://localhost:8000/docs`.

### Rodando os testes

```bash
make test          # roda toda a suíte
make test-cov       # roda com relatório de cobertura
```

### Qualidade de código

```bash
make lint          # ruff check
make type-check    # mypy
make format         # ruff format
```

## 📡 Principais endpoints

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/api/users` | Cria um usuário |
| `GET` | `/api/users` | Lista usuários |
| `GET` | `/api/users/{id}` | Busca um usuário |
| `POST` | `/api/tasks` | Cria uma tarefa |
| `GET` | `/api/tasks` | Lista tarefas (com filtros e paginação) |
| `GET` | `/api/tasks/{id}` | Busca uma tarefa |
| `PUT` | `/api/tasks/{id}` | Atualiza uma tarefa |
| `DELETE` | `/api/tasks/{id}` | Remove uma tarefa |
| `GET` | `/api/notifications` | Lista notificações (filtros: `task_id`, `user_id`, paginação) |
| `GET` | `/api/status` | Status do sistema (DB, contagem de tarefas, última escalação) |
| `GET` | `/health` | Health check |

## 📁 Estrutura do projeto

```
task-manager-backend/
├── src/task_manager/
│   ├── main.py             # Entry point da aplicação FastAPI (inclui lifespan do scheduler)
│   ├── database.py         # Configuração da sessão e engine SQLAlchemy
│   ├── models.py           # Modelos: User, Task, Notification
│   ├── schemas.py          # Schemas Pydantic (request/response)
│   ├── services.py         # Regras de negócio (CRUD, filtros, escalação, notificações)
│   ├── scheduler.py        # Job de escalação automática (APScheduler)
│   └── api/
│       ├── users.py        # Endpoints de usuários
│       ├── tasks.py        # Endpoints de tarefas
│       ├── notifications.py # Endpoints de notificações
│       └── status.py       # Endpoint de status do sistema
├── alembic/                 # Migrations do banco de dados
├── tests/
│   ├── unit/                # Testes unitários (schemas)
│   ├── integration/         # Testes de integração (endpoints via TestClient)
│   └── test_*.py            # Testes unitários de services/scheduler
├── pyproject.toml           # Dependências e configuração de ferramentas
└── Makefile                  # Atalhos para tarefas comuns
```

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────┐
│              FastAPI REST API                │
│   /api/users   /api/tasks   /api/notifications│
│              /api/status   /health            │
└──────────────────┬────────────────────────────┘
                   │
            ┌──────▼──────┐
            │ SQLAlchemy  │
            │  ORM Layer  │
            └──────┬──────┘
                   │
            ┌──────▼──────┐
            │   SQLite    │
            └─────────────┘

┌─────────────────────────────────────────────┐
│      APScheduler (job em background)         │
│  A cada 1 min: verifica tarefas incompletas  │
│  com prazo ≤24h → escalona para HIGH →       │
│  registra Notification                        │
└─────────────────────────────────────────────┘
```

- A API expõe rotas REST que delegam para a camada de **services** (`services.py`), que concentra toda a regra de negócio e fala diretamente com o ORM.
- O `EscalationService` roda dentro de um job do APScheduler (`scheduler.py`), iniciado/parado junto com o ciclo de vida da aplicação FastAPI (`lifespan`).
- O resultado da última execução do job fica em um pequeno estado em memória, exposto via `GET /api/status`.

## 🗺️ Próximos Passos (pós-MVP)

- **Frontend**: interface web (React ou HTML+HTMX) consumindo esta API
- **Deploy**: containerização (Docker) e CI/CD
- **Integrações**: notificações por e-mail/Slack, sincronização com calendário
- **Autenticação/autorização** e suporte a múltiplos times (multi-tenancy)

## 🗺️ Status do desenvolvimento

Projeto guiado por spec (`.speckit-*.md`) e desenvolvido em TDD, fase a fase:

- ✅ **Fase 1 — Fundação**: setup do projeto, SQLite, Alembic, modelos (`User`, `Task`, `Notification`)
- ✅ **Fase 2 — Usuários**: schemas, service e endpoints de usuário
- ✅ **Fase 3 — Tarefas (CRUD)**: schemas, service e endpoints de tarefas com filtros e paginação
- ✅ **Fase 4 — Escalation Scheduler**: serviço de escalação automática + job periódico com APScheduler
- ✅ **Fase 5 — Notificações**: endpoints para consulta de notificações
- ✅ **Fase 6 — Status/Health**: endpoint de status agregado do sistema
- ✅ **Fase 7 — Qualidade**: 139 testes (>90% de cobertura), `mypy` e `ruff` limpos
- 🚧 **Fase 8 — Documentação**: README completo; `ARCHITECTURE.md`/`API.md` em andamento

**Fora do escopo do MVP**: frontend, deploy em nuvem, integrações de notificação (e-mail/Slack), multi-tenancy e autenticação.

## 📄 Licença

MIT
