# Demo Script

## Scenario

You are reviewing a company and need a board-level technology risk summary. The source material may be a Snowflake 10-K, a diligence report, a cybersecurity assessment, or a technology assessment PDF.

The goal of the demo is to show that Executive AI Advisor can turn long-form source material into cited executive outputs with evaluation built into the workflow.

## Demo Setup

Start the API and database:

```bash
docker compose up --build
```

Start Streamlit in a second terminal:

```bash
streamlit run ui/streamlit_app.py
```

Open:

```text
http://localhost:8501
```

Confirm API docs are available:

```text
http://localhost:8000/docs
```

## Demo Document

Suggested documents:

- Snowflake 10-K
- sample technology diligence PDF
- cybersecurity assessment
- AI readiness assessment
- board technology risk packet

Use a document that can be discussed publicly if the demo is being shown outside a confidential environment.

## Synthetic Demo Datasets

The repository includes synthetic Markdown datasets that can be converted to PDF or copied into demo packets for upload.

| Dataset | Location | Best For |
| --- | --- | --- |
| FinTechCo | `data/demo/fintechco/` | Regulated fintech, compliance-heavy diligence, PCI scope, vendor concentration, access governance, and AI governance. |
| AcquisitionTargetCo | `data/demo/acquisition-target-co/` | Founder-led acquisition diligence, key-person dependency, aging architecture, security basics, and M&A integration readiness. |

Use FinTechCo when the audience wants to see board-level technology diligence for a high-growth regulated software company. Good questions include:

- What compliance risks should the board monitor?
- What vendor concentration risks exist?
- What AI governance gaps exist?
- What should be included in a 100-day technology plan?

Use AcquisitionTargetCo when the audience wants to see acquisition diligence for a profitable but under-instrumented founder-led software company. Good questions include:

- What are the top acquisition technology risks?
- What key-person risks exist?
- What integration risks should the acquirer plan for?
- What security gaps require immediate remediation?

## Demo Flow

### 1. Upload Document

In Streamlit:

1. Open Document Upload.
2. Choose a PDF.
3. Select `source_type`.
4. Select `classification`.
5. Click Upload PDF.

Talking point:

The system captures governance metadata at the moment of ingestion. This is important for future filtering, audit, and access-control workflows.

### 2. Parse Document

Click Parse document.

Talking point:

The parser stores page-aware text so later citations can point back to page ranges rather than anonymous text blobs.

### 3. Chunk Document

Click Chunk document.

Talking point:

Chunking prepares the document for retrieval. Chunks preserve page ranges, which enables evidence cards and citations.

### 4. Embed Document

Click Embed document.

Talking point:

Local embeddings are the default. That reduces cost and data exposure during demos and supports confidential or air-gapped environments.

### 5. Ask Executive Question

Suggested question:

```text
What cybersecurity risks are disclosed?
```

Other options:

- What should the board monitor over the next 12 months?
- What governance concerns exist?
- What operational dependencies create business risk?

Talking point:

Retrieval and generation are separated. The system first retrieves relevant evidence, then uses those sources to produce a cited answer.

### 6. Generate Board Summary

Choose a summary type such as:

```text
technology_risk
```

Click Generate Board Summary.

Talking point:

The board memo is structured for executive review: summary, risks, evidence, board questions, recommended actions, limitations, confidence, and citations.

### 7. Inspect Citations

Open the citation cards.

Talking point:

Every material claim should be reviewable against source excerpts and page ranges. The goal is not just answer generation; it is inspectable decision support.

### 8. Run Evaluation

Open the Evaluation section and click Run Evaluation.

Talking point:

Evaluation is part of trust, not an afterthought. The system scores citation quality, groundedness, relevance, and executive usefulness.

### 9. Export Markdown Memo

Use Download Board Memo.md or Download Evaluation Report.md.

Talking point:

Outputs are designed to move into executive workflows, board prep, diligence notes, or review packets.

## Suggested Talking Points

- Retrieval and generation are separated.
- Local embeddings reduce cost and data exposure.
- The mock LLM provider supports safe local demos.
- OpenAI providers are optional and configurable.
- Citations are required for material claims.
- Confidence and limitations are explicit.
- Evaluation creates repeatable quality evidence.
- Metadata supports future governance and access-control layers.

## Audience-Specific Emphasis

### CTO Audience

Highlight:

- FastAPI service boundaries
- PostgreSQL and pgvector architecture
- provider abstractions
- Alembic migrations
- deterministic tests
- evaluation framework
- no external API calls required by default

### PE Audience

Highlight:

- faster document triage
- board-level risk summaries
- cited diligence evidence
- repeatable evaluation
- exportable memos
- ability to compare operating risks across documents in the future

### Board Audience

Highlight:

- source-grounded summaries
- board questions
- recommended actions
- limitations and confidence
- ability to inspect evidence
- no claim should be accepted without citation

### AI Governance Audience

Highlight:

- classification metadata
- local embeddings by default
- mock LLM default
- citation requirements
- deterministic evaluation
- SLSA provenance and artifact attestation documentation
- future audit-log path

## Closing Line

Executive AI Advisor is not trying to replace diligence or judgment. It is designed to make executive document review faster, more traceable, and easier to govern.
