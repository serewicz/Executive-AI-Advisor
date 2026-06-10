# Executive AI Advisor

Executive AI Advisor is a secure, retrieval-augmented AI system for converting SEC filings, diligence reports, and technology assessments into cited executive summaries, board-level risk memos, and decision-support outputs.

## Who It Is For

- CTOs and technology executives
- PE operating partners
- Boards and investors
- Diligence teams
- AI governance leaders

## What It Demonstrates

- Secure document ingestion
- Diligence workspaces for company/deal isolation
- PDF parsing and page-aware text extraction
- Document chunking and lifecycle tracking
- Low-value chunk filtering for table-of-contents and other weak evidence
- Local and optional external embeddings
- PostgreSQL and pgvector semantic search
- Document-scoped cited executive Q&A
- Board-level summary generation
- Concise relevant citation excerpts with optional full source text
- Streamlit executive demo UI
- Deterministic evaluation workflows
- AI governance, citation, and auditability patterns

## Current Capabilities

- Upload PDFs with source type and classification metadata
- Create diligence workspaces and upload multiple PDFs per investigation
- Parse PDFs into page-level records
- Chunk documents into retrieval-ready passages
- Generate embeddings with local providers by default
- Search embedded chunks with pgvector
- Ask cited executive questions scoped to the active investigation by default
- Scope Q&A and board summaries to the active investigation by default
- Run technology due diligence assessments
- Generate technology due diligence reports for active investigations
- Generate scenario-specific 100-day technology operating plans from diligence findings
- Review 100-day plan executive one-pagers, timeline summaries, risk heatmaps, deliverables, owners, and board checkpoints
- Generate board summaries with citations, confidence, and limitations
- Render workflows in Streamlit without raw JSON
- Export board memos, diligence reports, executive one-pagers, 100-day plans, and evaluation reports as Markdown
- Run deterministic evaluation for citation quality, groundedness, relevance, and executive usefulness

## Quick Start

Start here:

[Quick Start](docs/QuickStart.md)

For a step-by-step executive demo, use:

[Exact Demo Tutorial](docs/ExactDemoTutorial.md)

## Security Notice

Executive AI Advisor is currently safe for a local executive demo on your own machine. It is not ready to expose publicly. Before hosting it on a shared network or public URL, add authentication, lock down the database port, set `APP_DEBUG=false`, run Uvicorn without `--reload`, and protect or disable public API docs.

Mock is the default LLM provider. OpenAI, Anthropic, and Grok/xAI keys must be supplied through environment variables or the Streamlit password input for local demo sessions. Streamlit session keys are not saved by the app, and Markdown exports include provider/model metadata but never API keys. Never commit keys to the repository.

Run the lightweight tracked-file secret scan before commits:

```bash
python scripts/check_no_secrets.py
```

Short version:

```bash
cp .env.example .env
docker compose up --build
docker compose exec api alembic upgrade head
python -m pip install -r requirements.txt
streamlit run ui/streamlit_app.py
```

Open:

- Streamlit UI: `http://localhost:8501`
- FastAPI docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

## Documentation

- [Quick Start](docs/QuickStart.md)
- [Methodology](docs/Methodology.md)
- [Exact Demo Tutorial](docs/ExactDemoTutorial.md)
- [User Guide](docs/UserGuide.md)
- [Architecture](docs/Architecture.md)
- [Developer Guide](docs/DeveloperGuide.md)
- [Demo Script](docs/DemoScript.md)
- [Evaluation](docs/Evaluation.md)
- [Governance](docs/Governance.md)
- [Security](docs/Security.md)

## Methodology

Executive AI Advisor automates portions of the CTO Operating System advisory methodology through document ingestion, retrieval, citations, diligence reports, board briefs, and 100-day technology plans. See [Methodology](docs/Methodology.md) for how this software platform relates to the CTO Operating System repository.

## Demo Datasets

Synthetic diligence datasets are available for local demos and testing:

- [SampleCo](data/demo/sampleco/): mid-market B2B SaaS growth equity diligence.
- [FinTechCo](data/demo/fintechco/): regulated fintech / compliance-heavy diligence.
- [AcquisitionTargetCo](data/demo/acquisition-target-co/): founder-led acquisition diligence and M&A integration readiness.

## Architecture Overview

Executive AI Advisor separates ingestion, retrieval, generation, and evaluation:

1. Upload and classify a PDF.
2. Add it to a diligence workspace.
3. Parse it into page-aware text.
4. Chunk text into retrieval passages.
5. Embed chunks with a local or optional OpenAI provider.
6. Search with pgvector inside the selected investigation by default.
7. Generate cited Q&A or board memos.
8. Run technology due diligence assessments.
9. Generate technology due diligence reports with risk ratings, confidence levels, risk heatmaps, and 30/60/90-day actions.
10. Generate scenario-specific 100-day technology operating plans with an executive one-pager, timeline summary, risk heatmap, deliverables, board checkpoints, and Markdown export.
11. Evaluate output quality and store evaluation runs.

See [Architecture](docs/Architecture.md) for the full system design.

## Executive Planning Outputs

100-Day Technology Plans are generated from Technology Due Diligence Report findings. The plan types are scenario-specific:

- `growth_equity`: scale readiness, governance, delivery predictability, security, AI governance, hiring coverage, and FinOps.
- `acquisition_integration`: acquirer coordination, knowledge transfer, identity mapping, data migration readiness, deployment handoff, documentation, and support transition.
- `turnaround`: urgent stabilization, spend control, backup validation, production access review, vulnerability triage, production ownership, and operating discipline.

Streamlit renders the plan in two tabs:

- Executive One-Pager: concise board-readable current state, target state, top priorities, first 30 days, board decisions, success metrics, and dependencies.
- Full 100-Day Plan: timeline summary, plan at a glance, risk heatmap, phase-based actions, deliverables, success metrics, citations, board checkpoints, dependencies, and limitations.

Risk and confidence scoring are shown in the Technology Due Diligence Report and carried into the 100-day plan risk heatmap. The heatmap includes category, risk rating, confidence, evidence count, and primary recommended action. Markdown downloads are available for the executive one-pager, full 100-day plan, diligence report, board memo, and evaluation report. Export filenames include the investigation name, report type, plan type when applicable, and generation timestamp.

## Database Migrations

Alembic is the source of truth for database schema creation and schema changes. Docker runs `alembic upgrade head` before starting the API, and the command can be run explicitly after pulling schema changes:

```bash
docker compose exec api alembic upgrade head
```

If a local development volume has stale schema state, see [Quick Start](docs/QuickStart.md) or [Developer Guide](docs/DeveloperGuide.md) for the reset workflow. `docker compose down -v` deletes local database data.

## Project Status

Executive AI Advisor is an early portfolio-grade MVP. It is intended to demonstrate CTO-level architecture, AI governance thinking, secure RAG patterns, and executive decision-support workflows.

Implemented:

- FastAPI backend
- PostgreSQL with pgvector
- Docker Compose local stack
- Alembic migrations
- SQLAlchemy models
- PDF upload, parsing, chunking, embeddings, search
- cited Q&A
- board summary generation
- technology due diligence report and 100-day plan generation
- executive one-pager, timeline summary, and risk heatmap outputs for technology planning
- Streamlit UI
- deterministic evaluation framework
- SLSA provenance and security documentation

Planned:

- authentication and role-based access control
- multi-document synthesis
- background jobs
- richer export formats
- hosted deployment profiles
- RAGAS or LLM-as-judge evaluation
- audit logs and governance dashboards

## License

Apache 2.0. See [LICENSE](LICENSE).
