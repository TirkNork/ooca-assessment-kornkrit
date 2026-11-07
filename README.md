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

## Development

```bash
docker compose run --rm app pytest
docker compose run --rm app ruff check .
docker compose run --rm app ruff format .
```

Source, tests and data are mounted into the container, so code changes don't need a rebuild.
Rebuild only after changing dependencies (`pyproject.toml` / `uv.lock`).
