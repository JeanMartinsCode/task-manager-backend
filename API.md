# API Reference — Task Manager

Documentação interativa completa (OpenAPI/Swagger) sempre disponível em `http://localhost:8000/docs` — este arquivo é um complemento com exemplos prontos de `curl`.

Todas as datas são ISO-8601 em UTC. Todos os corpos de requisição/resposta são JSON.

## Considerações de Segurança

### Autenticação

Todo endpoint sob `/api/*` exige o header `X-API-Key` (veja [ARCHITECTURE.md](ARCHITECTURE.md)). `/health` é a única rota pública.

Requisição sem o header, ou com chave errada, recebe `401`. Os exemplos abaixo assumem a chave exportada na shell — a mesma configurada no `.env` do servidor:

```bash
export API_KEY=a-chave-configurada-no-servidor
```

### Limite de requisições (rate limiting)

Endpoints de **escrita** (`POST`, `PUT`, `DELETE`) são limitados por IP — padrão `20/minute`, configurável via `RATE_LIMIT_WRITE`. Ao exceder, a resposta é `429` e **nada é criado ou alterado**. Endpoints de leitura (`GET`) não são limitados.

Um cliente que faça escritas em lote deve tratar `429` com backoff, não como erro fatal.

### Tamanho máximo do corpo

Requisições com corpo acima de `MAX_BODY_BYTES` (padrão 100 KB) são rejeitadas com `413` **antes de o corpo ser lido/parseado** — é uma proteção contra DoS por consumo de memória, não uma validação de schema. Campos individuais têm limites próprios bem menores (ver `422` na tabela abaixo e [SECURITY.md](SECURITY.md)).

### Conteúdo armazenado sem sanitização (XSS)

`name`, `email`, `title` e `description` são armazenados e devolvidos **exatamente como enviados**, sem escapar ou remover HTML/JavaScript. Um payload como `<script>alert(1)</script>` em `title` é persistido e volta assim no JSON de `GET /api/tasks/{id}`.

Isso é intencional, não um descuido: a API não sabe (nem deveria precisar saber) em que contexto cada consumidor vai renderizar esse texto. Filtrar/bloquear tags na entrada:

- destruiria dados legítimos (ex.: uma tarefa cujo título é literalmente "corrigir a tag `<script>` do header.html"), e
- daria uma falsa sensação de segurança — qualquer filtro de blocklist é contornável, e o problema real de XSS só existe se e quando um cliente renderiza esse texto como HTML sem escapar.

**Responsabilidade do consumidor:** qualquer frontend (ou outro serviço) que renderize `name`, `email`, `title` ou `description` como HTML **deve escapar o conteúdo no momento da renderização** (ex.: interpolação seguro do framework — JSX, `{{ }}` do Vue/Angular com auto-escape, `textContent` em vez de `innerHTML`, ou uma função de escape explícita se montando HTML manualmente). Nunca usar `innerHTML`/`v-html`/`dangerouslySetInnerHTML` direto com esses campos.

### Null bytes

Os mesmos campos de texto livre rejeitam `\x00` (null byte) com `422` — não é sobre XSS, mas evita corromper logs, exports CSV e integrações downstream que tratam strings como C-strings.

## Códigos de erro

| Código | Quando acontece |
|---|---|
| `400` | Regra de negócio violada (ex.: e-mail já existe, `assigned_to_id` inexistente) |
| `401` | Header `X-API-Key` ausente ou com valor inválido (qualquer rota `/api/*`) |
| `404` | Recurso não encontrado por ID (usuário ou tarefa) |
| `413` | Corpo da requisição acima de `MAX_BODY_BYTES` (padrão 100 KB), rejeitado antes do parse |
| `422` | Falha de validação do corpo/query params (schema Pydantic ou `Query(...)`) — inclui campo acima do `max_length`, null byte, ID acima do limite de 64 bits e `deadline` no passado |
| `429` | Limite de escrita por IP excedido (`RATE_LIMIT_WRITE`, padrão `20/minute`); o recurso **não** é criado nem alterado |
| `500` | Erro inesperado. O corpo traz só `{"detail": "Internal server error", "error_id": "..."}` — nunca stack trace; use o `error_id` para correlacionar com o log do servidor. Também é o código devolvido se o próprio servidor estiver sem `API_KEY` configurada |

---

## Usuários

### `POST /api/users` — Criar usuário

```bash
curl -X POST http://localhost:8000/api/users \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "Ana Silva", "email": "ana@example.com"}'
```

Resposta `201`:
```json
{"id": 1, "name": "Ana Silva", "email": "ana@example.com", "created_at": "2026-07-25T10:00:00"}
```

Erros: `400` (e-mail duplicado), `422` (e-mail com formato inválido, `name` vazio).

### `GET /api/users` — Listar usuários

```bash
curl -H "X-API-Key: $API_KEY" "http://localhost:8000/api/users?skip=0&limit=10"
```

Resposta `200`: lista de `UserRead`. Query params: `skip` (≥0, padrão 0), `limit` (1–100, padrão 100).

### `GET /api/users/{id}` — Buscar usuário

```bash
curl -H "X-API-Key: $API_KEY" http://localhost:8000/api/users/1
```

Resposta `200`: `UserRead`. Erro: `404` se não existir.

---

## Tarefas

### `POST /api/tasks` — Criar tarefa

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Corrigir bug de login",
    "description": "Usuários não conseguem autenticar",
    "deadline": "2026-07-26T18:00:00",
    "priority": "MEDIUM",
    "assigned_to_id": 1
  }'
```

Resposta `201`: `TaskRead` (com `status: "PENDING"`). Campos: `title` (obrigatório), `description` (opcional), `deadline` (obrigatório, deve ser futuro), `priority` (`LOW`/`MEDIUM`/`HIGH`, padrão `MEDIUM`), `assigned_to_id` (obrigatório, > 0).

Erros: `400` (`assigned_to_id` não existe), `422` (`deadline` no passado, `title` vazio).

### `GET /api/tasks` — Listar tarefas (filtros + paginação)

```bash
curl -H "X-API-Key: $API_KEY" "http://localhost:8000/api/tasks?status=PENDING&priority=HIGH&assigned_to_id=1&skip=0&limit=10"
```

Resposta `200`:
```json
{"items": [ { "id": 1, "title": "...", "...": "..." } ], "total": 1}
```

Query params (todos opcionais, combináveis): `status` (`PENDING`/`IN_PROGRESS`/`COMPLETED`), `priority` (`LOW`/`MEDIUM`/`HIGH`), `assigned_to_id`, `skip`, `limit`.

### `GET /api/tasks/{id}` — Buscar tarefa

```bash
curl -H "X-API-Key: $API_KEY" http://localhost:8000/api/tasks/1
```

Resposta `200`: `TaskRead`. Erro: `404`.

### `PUT /api/tasks/{id}` — Atualizar tarefa

```bash
curl -X PUT http://localhost:8000/api/tasks/1 \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"status": "IN_PROGRESS"}'
```

Todos os campos são opcionais; só os enviados são alterados. Resposta `200`: `TaskRead`. Erro: `404`.

### `DELETE /api/tasks/{id}` — Remover tarefa

```bash
curl -X DELETE -H "X-API-Key: $API_KEY" http://localhost:8000/api/tasks/1
```

Resposta `204` (sem corpo). Apaga também as notificações associadas. Erro: `404`.

---

## Notificações

### `GET /api/notifications` — Listar notificações

```bash
# Todas, mais recentes primeiro
curl -H "X-API-Key: $API_KEY" "http://localhost:8000/api/notifications?skip=0&limit=20"

# Filtrar por tarefa
curl -H "X-API-Key: $API_KEY" "http://localhost:8000/api/notifications?task_id=1"

# Filtrar por usuário (tarefas atribuídas a ele)
curl -H "X-API-Key: $API_KEY" "http://localhost:8000/api/notifications?user_id=1"
```

Resposta `200`: lista de `NotificationRead`:
```json
[{
  "id": 1, "task_id": 1, "notification_type": "ESCALATION",
  "message": "Deadline in ~12h, escalated to HIGH",
  "created_at": "2026-07-25T10:00:00+00:00"
}]
```

Se `task_id` e `user_id` forem enviados juntos, `task_id` tem precedência. Filtro sem correspondência retorna `200` com lista vazia (não é `404`).

---

## Status e Saúde

### `GET /api/status` — Status do sistema

```bash
curl -H "X-API-Key: $API_KEY" http://localhost:8000/api/status
```

Resposta `200`:
```json
{
  "db_connected": true,
  "tasks_count": 5,
  "tasks_by_status": {"PENDING": 3, "IN_PROGRESS": 1, "COMPLETED": 1},
  "tasks_by_priority": {"HIGH": 1, "MEDIUM": 3, "LOW": 1},
  "last_escalation_time": "2026-07-25T10:00:00+00:00",
  "last_escalation_count": 1
}
```

Antes da primeira execução do job de escalação, `last_escalation_time` é `null` e `last_escalation_count` é `0`.

### `GET /health` — Health check

```bash
curl http://localhost:8000/health
```

Resposta `200`: `{"status": "healthy"}`.
