# Developer Guide

This guide explains how to work on Executive AI Advisor as an engineer.

## Local Setup

Prerequisites:

- Python 3.12+
- Docker Desktop
- Git

Clone the repository:

```bash
git clone https://github.com/serewicz/Executive-AI-Advisor.git
cd Executive-AI-Advisor
```

Create local environment configuration:

```bash
cp .env.example .env
```

Install Python dependencies:

```bash
python -m pip install -r requirements.txt
```

## Docker Setup

Start the API and database:

```bash
docker compose up --build
```

Docker Compose starts:

- FastAPI at `http://localhost:8000`
- PostgreSQL with pgvector

The API container runs Alembic migrations before starting FastAPI. If you are updating an existing local database after pulling schema changes, you can also apply migrations explicitly:

```bash
docker compose exec api alembic upgrade head
```

The Streamlit UI is not started by Docker Compose. Run it separately from the host.

Stop the stack:

```bash
docker compose down
```

## Environment Variables

Configuration is loaded through `pydantic-settings`.

Common variables:

- `APP_NAME`
- `APP_ENV`
- `APP_DEBUG`
- `DATABASE_URL`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `OPENAI_API_KEY`
- `LLM_PROVIDER`
- `OPENAI_CHAT_MODEL`
- `EMBEDDING_PROVIDER`
- `LOCAL_EMBEDDING_MODEL`
- `OPENAI_EMBEDDING_MODEL`
- `EMBEDDING_DIMENSIONS`
- `MAX_EMBEDDING_CHUNKS_PER_REQUEST`
- `MAX_EMBEDDING_TEXT_CHARS`
- `MAX_SEARCH_QUERY_CHARS`

Do not hardcode secrets. Do not commit `.env`.

## Running The API

With Docker:

```bash
docker compose up --build
```

Without Docker, apply migrations first:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

API docs:

```text
http://localhost:8000/docs
```

## Running Streamlit

```bash
streamlit run ui/streamlit_app.py
```

The UI defaults to:

```bash
API_BASE_URL=http://localhost:8000
```

Override it if needed:

```bash
API_BASE_URL=http://localhost:8000 streamlit run ui/streamlit_app.py
```

Open:

```text
http://localhost:8501
```

## Running Tests

```bash
pytest -v
```

Compile-check a touched module:

```bash
python -m py_compile app/path/to/module.py
```

Testing guidance:

- Do not call external APIs in tests.
- Use mock providers or monkeypatch provider factories.
- Validate citation shape and source labels.
- Validate failure paths, not only happy paths.
- Keep tests deterministic.

## Project Structure

```text
.
├── app
│   ├── advisor
│   ├── api
│   ├── core
│   ├── db
│   ├── evaluation
│   ├── ingestion
│   ├── models
│   ├── retrieval
│   └── schemas
├── data
├── docs
├── migrations
├── scripts
├── tests
├── ui
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## Adding A New API Route

1. Create a route module under `app/api/routes/`.
2. Define request and response schemas in the relevant schema package.
3. Keep business logic in a service module rather than inside the route.
4. Register the router in `app/api/router.py`.
5. Add tests under `tests/`.

Example:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/example", tags=["example"])


@router.post("/run")
def run_example():
    return {"status": "ok"}
```

## Adding A New Document Type

Current upload support is PDF-only. To add another document type:

1. Extend upload validation in `app/api/routes/documents.py`.
2. Add parser support in `app/ingestion/parser.py`.
3. Preserve source metadata and classification.
4. Store page-aware or section-aware records.
5. Add tests for valid files, invalid files, and parser failure.

Do not bypass file validation or filename sanitization.

## Adding A New Embedding Provider

Embedding providers live under:

```text
app/ingestion/embeddings/
```

To add a provider:

1. Implement the `EmbeddingProvider` interface.
2. Return embeddings in the same order as input texts.
3. Expose `embedding_dimension()`.
4. Add the provider to the factory.
5. Add tests that do not call external APIs.

Provider rules:

- Normalize input whitespace.
- Fail clearly on configuration errors.
- Do not hardcode API keys.
- Preserve local/default behavior for tests.

## Adding A New LLM Provider

LLM providers live under:

```text
app/advisor/providers/
```

To add a provider:

1. Implement the `LLMProvider` interface.
2. Support executive Q&A.
3. Support board summary generation.
4. Return structured results.
5. Fail clearly if required configuration is missing.
6. Add mock-based tests.

Provider rules:

- No LLM calls without retrieved context.
- No board output without citations, limitations, and confidence.
- Do not expose raw prompts in responses.

## Adding Evaluation Metrics

Evaluation code lives under:

```text
app/evaluation/
```

Current deterministic metrics:

- citation quality
- groundedness
- relevance
- executive usefulness

To add a metric:

1. Add scoring logic in `app/evaluation/scoring.py`.
2. Extend `EvaluationResult` in `app/evaluation/schemas.py`.
3. Store the new metric in `EvaluationRun.results`.
4. Update tests.
5. Update Streamlit rendering if the metric should be visible.

Do not add RAGAS or LLM-as-judge calls until those are intentionally scoped and mocked in tests.

## Database Migrations

The project uses Alembic as the source of truth for schema creation and schema changes. Do not add `Base.metadata.create_all(...)` to application startup as a normal schema mechanism.

Docker Compose runs:

```bash
alembic upgrade head
```

before starting the API. The command is idempotent, so it is safe to run again after the container is up:

```bash
docker compose exec api alembic upgrade head
```

Fresh local setup:

```bash
docker compose up --build
docker compose exec api alembic upgrade head
curl http://localhost:8000/health
```

Create a migration after model changes:

```bash
alembic revision --autogenerate -m "describe change"
```

Review generated migrations before committing them. Confirm the migration includes all intended table, column, index, constraint, and pgvector changes. If Alembic cannot render `Vector(1536)` correctly, edit the migration manually and import `Vector` from `pgvector.sqlalchemy`.

Apply migrations after pulling schema changes:

```bash
docker compose exec api alembic upgrade head
```

Reset the local development database only when you can delete local data:

```bash
docker compose down -v
docker compose up --build
docker compose exec api alembic upgrade head
```

Warning: `docker compose down -v` deletes the local PostgreSQL volume, including uploaded document metadata, parsed pages, chunks, embeddings, document sets, and evaluation runs.

Useful Alembic commands:

```bash
docker compose exec api alembic current
docker compose exec api alembic history
docker compose exec api alembic upgrade head
```

Existing local development databases may need `docker compose exec api alembic upgrade head` after pulling new model changes. If migration history becomes inconsistent during local MVP development, a local reset is acceptable as long as you understand that it deletes local data.

## Coding Conventions

- Keep provider abstractions in place.
- No hardcoded secrets.
- No real external API calls in tests.
- No LLM output without citations.
- No board output without limitations and confidence.
- Keep retrieval and generation separated.
- Prefer deterministic behavior for local development.
- Preserve document classification and source metadata.
- Keep route handlers thin and service logic testable.
