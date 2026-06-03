# Executive AI Advisor

Executive AI Advisor is a secure RAG-based platform designed to help executives, boards, investors, and technology leaders analyze complex business and technology documents.

The system ingests SEC filings, technology assessments, diligence reports, and other enterprise artifacts to produce cited executive summaries, risk assessments, and board-ready insights.

## Objectives

- Ingest SEC filings and corporate disclosures
- Analyze technology diligence reports
- Assess technology and cybersecurity risk
- Generate board-level summaries and recommendations
- Provide source-grounded answers with citations
- Demonstrate AI governance, security, and evaluation practices

## Planned Architecture

- FastAPI backend
- PostgreSQL + pgvector
- OpenAI embeddings and LLMs
- Document ingestion and parsing pipeline
- Retrieval-Augmented Generation (RAG)
- Evaluation and governance framework

## Status

🚧 Early development

Current milestone:
- Initial FastAPI scaffold
- PostgreSQL + pgvector local development stack
- SQLAlchemy document and chunk models
- Document status and governance metadata fields
- Initial document upload request/response schemas
- Health endpoint at `/health`

## Project Structure

```text
.
├── app
│   ├── api
│   │   ├── router.py
│   │   └── routes
│   │       └── health.py
│   ├── core
│   │   └── config.py
│   ├── db
│   │   ├── base.py
│   │   └── session.py
│   ├── models
│   │   └── document.py
│   ├── schemas
│   │   └── document.py
│   └── main.py
├── data
│   ├── processed
│   └── uploads
├── docs
├── scripts
│   └── init-db.sql
├── tests
│   └── test_health.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Local Development

### Prerequisites

- Python 3.12+
- Docker Desktop
- Git

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Start the API and database:

```bash
docker compose up --build
```

3. Check the API:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "database": "ok"
}
```

The FastAPI docs are available at:

```text
http://localhost:8000/docs
```

Upload a PDF document:

```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@/path/to/document.pdf;type=application/pdf" \
  -F "source_type=board_material" \
  -F "classification=confidential"
```

Expected response:

```json
{
  "document_id": "...",
  "status": "uploaded"
}
```

## Configuration

Runtime configuration is loaded from environment variables and `.env` using `pydantic-settings`.

Key variables:

- `APP_NAME`
- `APP_ENV`
- `APP_DEBUG`
- `DATABASE_URL`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

## Database

Docker Compose uses the `pgvector/pgvector:pg16` image. The `scripts/init-db.sql` file enables the `vector` extension when the database is first created.

Alembic migration scaffolding is included under `migrations/`.

Create a migration after model changes:

```bash
alembic revision --autogenerate -m "describe change"
```

Apply migrations:

```bash
alembic upgrade head
```

The initial scaffold still creates SQLAlchemy tables on application startup for easy local bootstrapping. As the schema matures, startup table creation should be removed and Alembic should become the only schema-management path.

## Testing

Install dependencies locally, then run:

```bash
pytest
```

## Roadmap

### Phase 1
- Document ingestion
- Chunking and embeddings
- Vector search
- Citation-based retrieval

### Phase 2
- Executive Q&A
- Board memo generation
- Technology diligence workflows

### Phase 3
- Governance controls
- Evaluation framework
- Security hardening
- Multi-document analysis

## License

Apache 2.0
