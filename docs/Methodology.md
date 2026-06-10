# Methodology

Executive AI Advisor separates operating methodology from application code.

The CTO Operating System repository defines the advisory frameworks, templates, scoring models, and operating partner methodology:

https://github.com/serewicz/cto-operating-system

Executive AI Advisor is the software platform that automates and demonstrates portions of those frameworks through document ingestion, retrieval, citations, diligence reports, board briefs, evaluation, and 100-day technology plans.

## Relationship Between Repositories

| Repository | Purpose |
| --- | --- |
| CTO Operating System | Defines CTO, fractional CTO, operating partner, AI governance, diligence, risk scoring, board reporting, and post-close planning methodology |
| Executive AI Advisor | Implements selected workflows from that methodology as a retrieval-augmented software platform |

## What Executive AI Advisor Automates

Executive AI Advisor turns source documents into structured executive outputs by automating:

- PDF upload and metadata capture
- diligence workspaces for company or deal isolation
- page-aware PDF parsing
- document chunking and evidence filtering
- local or optional external embeddings
- pgvector semantic retrieval
- document-scoped executive Q&A
- citation-backed board summaries
- technology due diligence reports
- red/yellow/green risk and confidence scoring
- risk heatmaps
- cited 100-day technology plans
- executive one-pagers
- timeline summaries
- deterministic evaluation of answer quality

## What Remains Methodology

The CTO Operating System repository remains the source of truth for the advisory frameworks themselves, including:

- technology due diligence methodology
- technology risk scoring model
- 100-day technology plan framework
- board technology brief template
- AI governance assessment framework
- portfolio company technology review model
- CTO and fractional CTO operating templates

Executive AI Advisor should not become a general repository for advisory templates. New methodology should live in CTO Operating System first, then be automated in Executive AI Advisor when useful.

## Synthetic Demo Datasets

Synthetic demo datasets remain in Executive AI Advisor because they support local product demonstrations, testing, retrieval quality checks, and end-to-end workflow validation.

These datasets are intentionally fictional and are used to demonstrate how the software applies the methodology to realistic diligence-style documents.

## Operating Principle

Methodology should explain how a CTO or operating partner thinks.

Software should make that methodology repeatable, evidence-backed, and easier to demonstrate.
