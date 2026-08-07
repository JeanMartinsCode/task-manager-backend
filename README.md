# 📋 Task Manager — Escalação Automática de Prioridade

[![CI](https://github.com/JeanMartinsCode/task-manager-backend/actions/workflows/ci.yml/badge.svg)](https://github.com/JeanMartinsCode/task-manager-backend/actions/workflows/ci.yml)

📫 **Contato:** [LinkedIn](https://www.linkedin.com/in/jean-martins-dev)

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
- **Expõe tudo via API REST** documentada automaticamente (OpenAPI/Swagger), protegida por autenticação via API key

## 🛠️ Tecnologias

| Componente | Escolha | Motivo |
|---|---|---|
| Linguagem | Python 3.11+ | Tipagem estática, ecossistema maduro |
| Web Framework | FastAPI | Validação automática, docs OpenAPI, assíncrono |
| Banco de dados | SQLite + SQLAlchemy | Zero setup, ACID, suficiente para o MVP |
| Migrations | Alembic | Versionamento de schema |
| Scheduler | APScheduler | Job em background, sem infraestrutura externa (Redis/Celery) |
| Rate limiting | slowapi | Limite de requisições em rotas de escrita, defesa em profundidade |
| Testes | pytest + pytest-cov | Fixtures ricas, cobertura de código |
| Qualidade | mypy + ruff | Tipagem estática e linting |
| CI | GitHub Actions | Instala o pacote de verdade (`uv sync`), roda migrations, suíte completa, lint e type-check a cada push/PR |

## 🚀 Como rodar localmente

Pré-requisitos: Python 3.11+ e [uv](https://github.com/astral-sh/uv).

```bash
# 1. Clonar o repositório
git clone https://github.com/JeanMartinsCode/task-manager-backend.git
cd task-manager-backend

# 2. Instalar dependências
make install          # uv sync --all-extras

# 3. Rodar as migrations
make migrate           # alembic upgrade head

# 4. Definir a API key (obrigatória — sem ela, toda rota /api/* responde 500)
cp .env.example .env   # edite API_KEY com um valor seu

# 5. Subir o servidor
make run                # uvicorn task_manager.main:app --reload

# 6. Testar
curl http://localhost:8000/health
curl -H "X-API-Key: <seu-valor>" http://localhost:8000/api/status
```

A documentação interativa da API fica disponível em `http://localhost:8000/docs`.

### Rodando os testes

```bash
make test          # roda toda a suíte (210 testes)
make test-cov       # roda com relatório de cobertura
```

O mesmo fluxo (`make install && make migrate && make test`) roda no CI a cada push, contra o pacote instalado de verdade — não só num checkout bruto — para garantir que o que passa aqui também passa para quem clona e instala do zero.

### Qualidade de código

```bash
make lint          # ruff check
make type-check    # mypy
make format         # ruff format
```

## 🔐 Autenticação

Todos os endpoints sob `/api/*` exigem o header `X-API-Key`, comparado em tempo constante (`secrets.compare_digest`) para evitar timing attacks. A API falha fechado: se `API_KEY` não estiver configurada no servidor, toda rota `/api/*` responde `500` em vez de liberar acesso — nunca abre por omissão. `/health` é a única rota pública. Ver [`SECURITY.md`](./SECURITY.md) para o modelo de ameaça completo e o que ainda não está coberto (autorização por recurso, multi-tenancy).

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
| `GET` | `/health` | Health check (liveness — não verifica dependências) |

Rotas de escrita têm rate limit (`429` acima do limite configurado) e limite de tamanho de corpo (`413` acima do teto); ambos configuráveis por variável de ambiente. Exemplos completos de requisição/resposta, incluindo os códigos de erro, em [`API.md`](./API.md).

## 📁 Estrutura do projeto

```
task-manager-backend/
├── src/task_manager/
│   ├── main.py              # Entry point da aplicação FastAPI (inclui lifespan do scheduler)
│   ├── database.py          # Configuração da sessão e engine SQLAlchemy
│   ├── models.py            # Modelos: User, Task, Notification
│   ├── schemas.py           # Schemas Pydantic (request/response)
│   ├── services.py          # Regras de negócio (CRUD, filtros, escalação, notificações)
│   ├── scheduler.py         # Job de escalação automática (APScheduler)
│   ├── security.py          # Autenticação via X-API-Key (constant-time)
│   ├── rate_limit.py        # Rate limiting em rotas de escrita (slowapi)
│   ├── body_limit.py        # Limite de tamanho de corpo de requisição
│   ├── constants.py         # Limites compartilhados (ex.: bounds de ID/paginação)
│   └── api/
│       ├── users.py         # Endpoints de usuários
│       ├── tasks.py         # Endpoints de tarefas
│       ├── notifications.py # Endpoints de notificações
│       └── status.py        # Endpoint de status do sistema
├── alembic/                 # Migrations do banco de dados
├── tests/
│   ├── unit/                # Testes unitários (schemas)
│   ├── integration/         # Testes de integração (endpoints via TestClient)
│   ├── security/            # Testes de regressão de segurança (pentest rodadas 1 e 2)
│   ├── test_module_identity.py # Guarda contra duplicação de módulo/engine (ver ARCHITECTURE.md)
│   └── test_*.py            # Testes unitários de services/scheduler/alembic
├── .github/workflows/ci.yml # CI: install real → migrate → testes → lint → type-check
├── pyproject.toml           # Dependências e configuração de ferramentas
└── Makefile                 # Atalhos para tarefas comuns
```

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────┐
│              FastAPI REST API                │
│   /api/users   /api/tasks   /api/notifications│
│              /api/status   /health            │
│          (autenticação via X-API-Key)         │
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
- O resultado da última execução do job fica em um pequeno estado em memória, exposto via `GET /api/status` — limitação conhecida sob múltiplas réplicas, ver [`ARCHITECTURE.md`](./ARCHITECTURE.md).

Detalhes de decisões de design, débito técnico consciente e como o projeto evoluiu em [`ARCHITECTURE.md`](./ARCHITECTURE.md).

## 🔒 Segurança

Duas rodadas completas de pentest manual (SQLi, XSS, IDOR, mass assignment, payloads extremos, rate limiting, condições de corrida) + análise estática (Bandit, pip-audit), cada achado corrigido via TDD com teste de regressão dedicado. Detalhes completos, causa raiz e débito técnico consciente em [`SECURITY.md`](./SECURITY.md).

## 🗺️ Próximos Passos (pós-MVP)

- **Frontend**: interface web (React ou HTML+HTMX) consumindo esta API
- **Deploy**: containerização (Docker)
- **Integrações**: notificações por e-mail/Slack, sincronização com calendário
- **Autorização por recurso e multi-tenancy**: hoje a API key é única e compartilhada — qualquer chamador autenticado acessa todos os recursos (ver débito técnico em [`SECURITY.md`](./SECURITY.md))
- **Banco de produção**: migração para PostgreSQL — a conexão SQLite única (`StaticPool`) não é segura sob concorrência real de threads (ver [`SECURITY.md`](./SECURITY.md))

## 🗺️ Status do desenvolvimento

Desenvolvido em TDD, fase a fase:

- ✅ **Fase 1 — Fundação**: setup do projeto, SQLite, Alembic, modelos (`User`, `Task`, `Notification`)
- ✅ **Fase 2 — Usuários**: schemas, service e endpoints de usuário
- ✅ **Fase 3 — Tarefas (CRUD)**: schemas, service e endpoints de tarefas com filtros e paginação
- ✅ **Fase 4 — Escalation Scheduler**: serviço de escalação automática + job periódico com APScheduler
- ✅ **Fase 5 — Notificações**: endpoints para consulta de notificações
- ✅ **Fase 6 — Status/Health**: endpoint de status agregado do sistema
- ✅ **Fase 7 — Qualidade**: 139 testes (>90% de cobertura), `mypy` e `ruff` limpos
- ✅ **Fase 8 — Documentação**: README, `ARCHITECTURE.md` e `API.md` finalizados
- ✅ **Fase 9 — Segurança (rodada 1)**: autenticação, validação de limites, rate limiting, DoS/XSS — ver [`SECURITY.md`](./SECURITY.md)
- ✅ **Fase 10 — Segurança (rodada 2)**: naive/aware datetime, overflow de paginação, limite de corpo, condição de corrida — ver [`SECURITY.md`](./SECURITY.md)
- ✅ **Fase 11 — Correção estrutural**: eliminado bug de dual-import/dual-engine que quebrava a suíte sob instalação real (`pip install -e .` / `uv sync`); teste de regressão permanente (`test_module_identity.py`) e CI criado do zero rodando contra o pacote instalado
- ✅ **Fase 12 — Consistência de documentação**: `.env` carregado de verdade (`load_dotenv`, antes só documentado), `DATABASE_URL` passou a ser respeitada, README/`ARCHITECTURE.md`/`API.md` corrigidos para bater com o código real (auth, rate limit, limite de corpo, estrutura de arquivos)

**210 testes passando**, 96%+ de cobertura, `ruff` e `mypy` limpos — validado tanto em execução direta quanto sob instalação real via CI.

**Fora do escopo do MVP**: frontend, deploy em nuvem, integrações de notificação (e-mail/Slack), autorização por recurso e multi-tenancy.

## 📄 Licença

Business Source License 1.1 (BSL 1.1) — uso comercial requer licença comercial. Uso pessoal, educacional e avaliação por recrutadores é gratuito.
