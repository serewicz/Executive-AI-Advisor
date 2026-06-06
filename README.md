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
├── ui
│   └── streamlit_app.py
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

The Docker Compose stack starts the FastAPI backend at `http://localhost:8000`. It does not start the Streamlit UI.

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

Opening `http://localhost:8000` shows a small API landing response. The executive demo website runs separately on Streamlit at `http://localhost:8501`.

Run the Streamlit executive demo UI from a second terminal. Streamlit runs on your host machine, so install the Python dependencies locally first:

```bash
python -m pip install -r requirements.txt
```

Then start the UI:

```bash
streamlit run ui/streamlit_app.py
```

After Streamlit starts, open:

```text
http://localhost:8501
```

The UI uses `API_BASE_URL` to reach the FastAPI backend and defaults to:

```bash
API_BASE_URL=http://localhost:8000
```

If the API is running somewhere else, set the backend URL when launching Streamlit:

```bash
API_BASE_URL=http://localhost:8000 streamlit run ui/streamlit_app.py
```

Recommended local demo flow:

1. Start the API with `docker compose up --build`
2. Wait for `http://localhost:8000/health` to return `{"status":"ok","database":"ok"}`
3. Start the UI with `streamlit run ui/streamlit_app.py`
4. Upload a PDF, then run parse, chunk, and embed from the Processing Pipeline section
5. Use Executive Q&A or Board Summary Generator to render advisor outputs without raw JSON

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
  "filename": "document.pdf",
  "status": "uploaded",
  "source_type": "board_material",
  "classification": "confidential"
}
```

## PDF Parsing

Uploaded PDFs can be parsed into page-aware text records.

Parsing behavior:

- Uses Docling as the preferred PDF parser
- Falls back to `pypdf` for simple text extraction when Docling fails
- Preserves page numbers where the parser exposes them
- Normalizes whitespace
- Skips empty pages
- Stores parsed text in `parsed_document_pages`
- Updates document status from `uploaded` to `parsing` to `parsed`
- Updates document status to `failed` and records `parse_error` in `document_metadata` if parsing fails

Trigger parsing for an uploaded document:

```bash
curl -X POST http://localhost:8000/documents/{document_id}/parse
```

Expected response:

```json
{
  "document_id": "...",
  "status": "parsed",
  "pages_parsed": 12
}
```

Fetch parsed page previews:

```bash
curl http://localhost:8000/documents/{document_id}/pages
```

Each page preview is limited to 1,000 characters.

Current limitations:

- Parsing is synchronous
- No embeddings yet
- No LLM calls yet
- No OCR tuning yet

## Document Chunking

Parsed document pages can be converted into retrieval-ready chunks.

Chunking behavior:

- Loads parsed pages in page order
- Combines page text into readable chunks
- Preserves `page_start` and `page_end`
- Uses a target chunk size of 1,000 estimated tokens
- Uses an overlap of 150 estimated tokens
- Estimates tokens with simple word count divided by `0.75`
- Replaces existing chunks when a document is re-chunked
- Updates document status to `chunked`

Trigger chunking for a parsed document:

```bash
curl -X POST http://localhost:8000/documents/{document_id}/chunk
```

Expected response:

```json
{
  "document_id": "...",
  "status": "chunked",
  "chunks_created": 8
}
```

Fetch chunk previews:

```bash
curl http://localhost:8000/documents/{document_id}/chunks
```

Each chunk preview is limited to 1,000 characters.

Current limitations:

- Simple token estimation only
- No LLM calls yet

## Semantic Search

Chunk embeddings can be generated and stored in PostgreSQL using pgvector.

Embedding behavior:

- Requires `OPENAI_API_KEY` only when `EMBEDDING_PROVIDER=openai`
- Uses local embeddings by default with `BAAI/bge-small-en-v1.5`
- Supports OpenAI-managed embeddings with `EMBEDDING_PROVIDER=openai`
- Uses `OPENAI_EMBEDDING_MODEL=text-embedding-3-small` when OpenAI embeddings are enabled
- Loads chunk content in `chunk_index` order
- Skips chunks that already have embeddings
- Limits each synchronous embedding request to 200 chunks by default
- Limits each embedding input to 12,000 characters by default
- Stores vectors on `document_chunks.embedding`
- Updates document status to `embedded`

The architecture abstracts embedding providers. We can use OpenAI-managed embeddings, or local embeddings for confidentiality, cost control, and air-gapped environments.

Trigger embedding for a chunked document:

```bash
curl -X POST http://localhost:8000/documents/{document_id}/embed
```

Expected response:

```json
{
  "document_id": "...",
  "status": "embedded",
  "chunks_embedded": 8
}
```

Search embedded chunks:

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the main technology risks?",
    "top_k": 5,
    "source_type": null,
    "classification": null
  }'
```

Search returns cited chunk previews with page references and document governance metadata. It does not generate LLM answers yet.

Retrieval and generation are intentionally separate. Embeddings and vector search identify relevant source chunks; LLM answer synthesis will be added later as a separate layer so retrieval quality, citations, provider choice, and governance controls can be evaluated independently.

Switch embedding providers with environment variables:

```bash
EMBEDDING_PROVIDER=local
LOCAL_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
```

```bash
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Cost and abuse controls:

- `MAX_EMBEDDING_CHUNKS_PER_REQUEST` caps synchronous embedding fan-out
- `MAX_EMBEDDING_TEXT_CHARS` caps each embedding input
- `MAX_SEARCH_QUERY_CHARS` caps semantic search query size
- `top_k` is capped at 20

## Cited Executive Q&A

Executive Q&A uses semantic search first, then asks the configured LLM provider to answer using only the retrieved chunks.

Q&A behavior:

- Retrieves relevant chunks with pgvector semantic search
- Formats retrieved chunks as numbered sources like `[S1]`, `[S2]`, and `[S3]`
- Requires answers to cite material claims using source labels
- Returns citation metadata with document IDs, chunk IDs, excerpts, and page ranges
- Defaults to `LLM_PROVIDER=mock` so local development and tests do not require an OpenAI key
- Can use OpenAI later with `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, and `OPENAI_CHAT_MODEL`

Ask an executive question:

```bash
curl -X POST http://localhost:8000/advisor/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the main technology risks?",
    "top_k": 5,
    "source_type": null,
    "classification": null
  }'
```

The mock provider returns deterministic cited answers for local development. Real answer generation can be enabled later without changing the retrieval pipeline.

## Board-Level Summary Generator

The board summary endpoint creates a structured memo from an existing document's chunks. It is grounded in retrieved source chunks and returns separate citation metadata with document IDs, chunk IDs, excerpts, and page ranges.

Supported summary types:

- `technology_risk`
- `diligence_summary`
- `ai_readiness`
- `security_governance`
- `board_brief`

Board summary behavior:

- Requires the document to be `chunked`, `embedded`, or `indexed`
- Uses query-based semantic retrieval when embeddings are available
- Falls back to the first ordered chunks when embeddings are not available or retrieval fails
- Labels sources as `[S1]`, `[S2]`, and so on
- Instructs the LLM provider to use only supplied sources, cite material claims, avoid speculation, and state limitations
- Defaults to the mock LLM provider, so no OpenAI key is required for local development

Generate a board-level memo:

```bash
curl -X POST http://localhost:8000/advisor/board-summary \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "00000000-0000-0000-0000-000000000000",
    "summary_type": "technology_risk",
    "top_k": 12
  }'
```

Current limitations:

- No legal, financial, investment, or regulatory advice
- No multi-document synthesis yet
- No background jobs or streaming yet
- Mock provider output is deterministic and intended for local development only

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
