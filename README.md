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

Docker runs `alembic upgrade head` before starting the API so local databases receive the latest schema changes.

3. For non-Docker local development, apply migrations before starting the API:

```bash
alembic upgrade head
```

4. Check the API:

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

Alembic is the source of truth for schema management. Apply migrations before running the API outside Docker.

## Testing

Install dependencies locally, then run:

```bash
pytest
```

## Supply Chain Provenance

Release and manual builds generate SLSA provenance for the Dockerized Executive AI Advisor service.

The workflow:

- Builds the Docker image artifact
- Generates SLSA L3 provenance using the OpenSSF SLSA GitHub Generator pinned to `v2.1.0`
- Uploads the Docker image artifact to the workflow run
- Uploads the `.intoto.jsonl` provenance file to the workflow run artifacts
- Creates a native GitHub Artifact Attestation for the Docker image artifact
- Attaches provenance to GitHub Release assets for `release:created` events

Create a test release:

```bash
git tag v0.0.1-slsa-test
git push origin v0.0.1-slsa-test
```

Then create a GitHub Release for the tag. Check:

- Workflow run Artifacts tab for `executive-ai-advisor-image`
- Workflow run Artifacts tab for `executive-ai-advisor-slsa-provenance`
- Workflow run Artifacts tab for `executive-ai-advisor-github-attestations`
- Release assets for `executive-ai-advisor-image.tar`
- Release assets for `executive-ai-advisor-image.intoto.jsonl`

Verify provenance with `slsa-verifier`:

```bash
slsa-verifier verify-artifact executive-ai-advisor-image.tar \
  --provenance-path executive-ai-advisor-image.intoto.jsonl \
  --source-uri github.com/serewicz/Executive-AI-Advisor \
  --source-tag v0.0.1-slsa-test
```

Verify the native GitHub Artifact Attestation:

```bash
gh attestation verify executive-ai-advisor-image.tar \
  --repo serewicz/Executive-AI-Advisor
```

Attestation creation requires the workflow permissions `id-token: write`, `attestations: write`, and `artifact-metadata: write`. GitHub Artifact Attestations are available for public repositories on current GitHub plans; private and internal repositories require GitHub Enterprise Cloud. SLSA provenance for private repositories is explicitly opted into and publishes the repository name to the public transparency log.

All release builds produce verifiable SLSA L3 provenance for the Dockerized RAG service, supporting SOC 2 evidence collection and immutable audit trails.

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
