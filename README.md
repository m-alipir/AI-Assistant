# Personal Intelligence System

Self-hosted, code-first daily intelligence briefing service. The project is being delivered
milestone by milestone; see [progress](docs/PROGRESS.md) for the current implementation state.

## Local development

Requires Python 3.12+ and Docker Desktop for the full development stack.

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
```

Start Postgres/pgvector and the API:

```powershell
docker compose up --build -d
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/ready
```

The database is exposed on `localhost:5433` by default so an existing PostgreSQL service on
`5432` is not interrupted. To use another free host port, set `POSTGRES_HOST_PORT` in `.env`
before running Compose; the application container always connects to `db:5432` over the internal
Compose network. This setting does not affect the API port (`8000`).

`/health` reports process liveness. `/ready` checks database connectivity and returns HTTP 503
until Postgres is reachable. The application runs `alembic upgrade head` before starting Uvicorn,
so `docker compose up` applies the current schema automatically. Neither endpoint requires an
external API key.

Stop the stack with `docker compose down`; named database data is retained. To intentionally
remove local database data as well, use `docker compose down --volumes`.

## CI

CI runs unit tests and Ruff. It deliberately does not call external providers or require
credentials. Database migrations are exercised by `docker compose` during local integration
verification.
