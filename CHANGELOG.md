# Changelog

All notable changes to Executive AI Advisor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Root `SECURITY.md` pointing to detailed security documentation
- Populated project roadmap
- Improved README visibility for AI Replicability and CRA assessments (see related PR)
- MCP server (`python -m app.mcp_server`) exposing advisor tools, resources, and prompts over stdio and streamable HTTP
- MCP bearer-token authentication for streamable HTTP (`MCP_AUTH_TOKENS`) and a token generator (`python -m app.mcp_server.tokens`)
- MCP model allowlist (`config/models.yaml`), per-client rate limits, and an append-only `mcp_audit_events` table (migration `20261025_0008`)
- ADR 0001 and the MCP operations runbook

### Changed
- Documentation and contribution hygiene updates
- **Breaking:** the MCP HTTP transport exits with an error on a non-loopback `--host` unless `MCP_AUTH_TOKENS` is set or `MCP_ALLOW_INSECURE_BIND=true`
- MCP errors from providers and unexpected failures now return a generic message with a reference ID instead of the exception text
- Document-set helpers moved from the API routes to `app/services/document_sets.py`

### Security
- Upgraded sentence-transformers, pypdf, python-multipart, docling, requests, streamlit, python-dotenv, pytest, and torch to patched releases

## [0.1.0] - 2026-08

### Added
- FastAPI backend with PostgreSQL + pgvector
- Document ingestion, parsing, chunking, embeddings, and cited retrieval
- Technology Risk Scorecard, Board Brief, 100-Day Technology Plan, and AI Governance Assessment modules
- Technology Due Diligence Report and scenario-specific 100-day planning
- Cyber Resilience Act (CRA) Readiness Assessment
- AI Replicability Risk Assessment
- Streamlit executive UI with Markdown exports
- Deterministic evaluation framework
- Local-first defaults (mock LLM + local embeddings)
- Docker Compose local stack and Alembic migrations
- SLSA provenance support and security documentation
- Demo datasets (SampleCo, FinTechCo, AcquisitionTargetCo)
