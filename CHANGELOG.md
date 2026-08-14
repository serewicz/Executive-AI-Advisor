# Changelog

All notable changes to Executive AI Advisor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Root `SECURITY.md` pointing to detailed security documentation
- Populated project roadmap
- Improved README visibility for AI Replicability and CRA assessments (see related PR)

### Changed
- Documentation and contribution hygiene updates

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
