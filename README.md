# Support Ticket Triage Agent

AI agent that triages incoming customer support tickets: classifies urgency, extracts key
information, searches a knowledge base, and decides the next action
(auto-respond / route to specialist / escalate to human).

> Work in progress — usage instructions will be completed as the implementation lands.

## Requirements

- Docker with Docker Compose v2.24+

Everything (app, Postgres + pgvector) runs in containers. Python dependencies are managed with
[uv](https://docs.astral.sh/uv/) inside the image and pinned in `uv.lock`.

## Setup

```bash
cp .env.example .env        # then set OPENAI_API_KEY
docker compose build
```

## Usage

Triage the sample tickets from the command line:

```bash
docker compose run --rm app python scripts/triage_tickets.py data/sample_tickets.json
docker compose run --rm app python scripts/triage_tickets.py data/sample_tickets.json --ticket T-1001
docker compose run --rm app python scripts/triage_tickets.py data/sample_tickets.json --json
```

Or run the HTTP API and post a ticket (interactive docs at http://localhost:8000/docs):

```bash
docker compose up api
curl -X POST localhost:8000/triage -H 'content-type: application/json' -d '{
  "ticket_id": "T-1", "customer_id": "C-3001",
  "messages": [{"sent_at": "2026-11-07T09:00:00Z", "content": "Is there a dark mode?"}]
}'
```

### Postgres + pgvector backend

By default the tools read the JSON files in `data/` and search the knowledge base with BM25.
To use Postgres instead (hybrid search: pgvector similarity + full-text, fused with RRF):

```bash
docker compose run --rm app python scripts/seed_db.py          # load data/ and embed the KB
echo "REPOSITORY_BACKEND=postgres" >> .env
docker compose run --rm app python scripts/triage_tickets.py data/sample_tickets.json
```

Re-running the seed replaces the data and only embeds chunks whose text changed
(`--reset` drops and recreates the tables).

## Development

```bash
docker compose run --rm app pytest            # starts Postgres for the integration tests
docker compose run --rm app ruff check .
docker compose run --rm app ruff format .
```

Source, tests and data are mounted into the container, so code changes don't need a rebuild.
Rebuild only after changing dependencies (`pyproject.toml` / `uv.lock`).
