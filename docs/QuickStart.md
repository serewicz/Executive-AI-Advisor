# Quick Start

This guide gets Executive AI Advisor running locally in about 15 to 20 minutes.

## Prerequisites

- Docker Desktop
- Python 3.12+
- Git
- Optional: OpenAI API key

The default configuration uses local embeddings and a mock LLM provider, so an OpenAI key is not required for local demos or tests.

## Clone The Repository

```bash
git clone https://github.com/serewicz/Executive-AI-Advisor.git
cd Executive-AI-Advisor
```

## Configure Environment

Create a local environment file:

```bash
cp .env.example .env
```

For the default local setup, no secrets are required. To enable OpenAI later, set:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_CHAT_MODEL=gpt-4o-mini
```

For OpenAI embeddings:

```bash
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Do not commit `.env`.

## Start The API

Start FastAPI and PostgreSQL:

```bash
docker compose up --build
```

Docker runs Alembic migrations before starting the API. You can safely apply them again after the stack is running:

```bash
docker compose exec api alembic upgrade head
```

The API will be available at:

```text
http://localhost:8000
```

FastAPI docs:

```text
http://localhost:8000/docs
```

Health check:

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

## Install Local Python Dependencies

In a second terminal, install dependencies for tests and Streamlit:

```bash
python -m pip install -r requirements.txt
```

## Run Tests

```bash
pytest -v
```

## Run Streamlit

Start the executive demo UI:

```bash
streamlit run ui/streamlit_app.py
```

Open:

```text
http://localhost:8501
```

If the API is not running at the default URL, set `API_BASE_URL`:

```bash
API_BASE_URL=http://localhost:8000 streamlit run ui/streamlit_app.py
```

## Demo Workflow

Use the Streamlit UI for the quickest end-to-end path.

1. Create or select an investigation workspace.
2. Upload one or more PDFs.
3. Select `source_type`.
4. Select `classification`.
5. Process the active investigation.
6. Ask an executive question.
7. Generate a board summary.
8. Run evaluation for a selected document.
9. Download the Markdown memo or evaluation report.

Suggested first question:

```text
What cybersecurity risks are disclosed?
```

For exact click-by-click instructions with the synthetic datasets, see [Exact Demo Tutorial](ExactDemoTutorial.md).

## API Workflow

Upload a PDF:

```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@/path/to/document.pdf;type=application/pdf" \
  -F "source_type=board_material" \
  -F "classification=confidential" \
  -F "document_set_id=00000000-0000-0000-0000-000000000000"
```

Parse:

```bash
curl -X POST http://localhost:8000/documents/{document_id}/parse
```

Chunk:

```bash
curl -X POST http://localhost:8000/documents/{document_id}/chunk
```

Embed:

```bash
curl -X POST http://localhost:8000/documents/{document_id}/embed
```

Ask a question:

```bash
curl -X POST http://localhost:8000/advisor/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What cybersecurity risks are disclosed?",
    "top_k": 5,
    "document_id": "00000000-0000-0000-0000-000000000000",
    "source_type": null,
    "classification": null
  }'
```

Omit `document_id` only when you intentionally want global search across all embedded documents.

Generate a board summary:

```bash
curl -X POST http://localhost:8000/advisor/board-summary \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "00000000-0000-0000-0000-000000000000",
    "summary_type": "technology_risk",
    "top_k": 12
  }'
```

Run evaluation:

```bash
curl -X POST http://localhost:8000/evaluation/run \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "00000000-0000-0000-0000-000000000000",
    "evaluation_type": "advisor_qa",
    "questions": [
      {
        "question": "What cybersecurity risks are disclosed?",
        "expected_themes": ["security", "risk", "controls"]
      }
    ]
  }'
```

## Troubleshooting

### `localhost:8000` Is Not Reachable

Confirm Docker Compose is running:

```bash
docker compose ps
```

Check logs:

```bash
docker compose logs api
```

### Missing Database Table

If you see an error such as `relation "document_sets" does not exist`, apply the latest Alembic migrations:

```bash
docker compose exec api alembic upgrade head
```

For a fresh local reset during development:

```bash
docker compose down -v
docker compose up --build
docker compose exec api alembic upgrade head
```

Warning: `docker compose down -v` deletes the local database volume and all local uploaded document metadata, chunks, embeddings, document sets, and evaluation runs.

### Docker Is Not Running

Start Docker Desktop, wait for it to finish initialization, then run:

```bash
docker compose up --build
```

### `pytest` Cannot Import `app`

Run tests from the repository root:

```bash
pytest -v
```

The repository includes `pytest.ini` with:

```ini
[pytest]
pythonpath = .
testpaths = tests
```

### OpenAI Key Missing

The default setup does not require OpenAI. If you select `LLM_PROVIDER=openai` or `EMBEDDING_PROVIDER=openai`, set:

```bash
OPENAI_API_KEY=your_key_here
```

### Large PDF Parsing Takes Time

Parsing runs synchronously in the current MVP. Large PDFs may take longer to parse, chunk, and embed. Keep the Docker logs open while testing large documents.
