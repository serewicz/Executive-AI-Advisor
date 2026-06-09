# Demo Script

## Scenario

You are reviewing a company and need a board-level technology risk summary. The source material may be a Snowflake 10-K, a diligence report, a cybersecurity assessment, or a technology assessment PDF.

The goal of the demo is to show that Executive AI Advisor can turn long-form source material into cited executive outputs with evaluation built into the workflow.

For exact setup and click-by-click instructions, see [Exact Demo Tutorial](ExactDemoTutorial.md).

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

## Investigation Workspace Setup

Create one workspace per company or deal before uploading documents. For example:

- `SampleCo Diligence`
- `FinTechCo Diligence`
- `AcquisitionTargetCo Diligence`

The active workspace is the default analysis scope. Previous company documents are excluded unless Industry Benchmark / Cross-Investigation Analysis is explicitly selected.

## Synthetic Demo Datasets

The repository includes synthetic Markdown datasets that can be converted to PDF or copied into demo packets for upload.

| Dataset | Location | Best For |
| --- | --- | --- |
| SampleCo | `data/demo/sampleco/` | Mid-market B2B SaaS growth equity diligence, moderate technical debt, security governance, AI readiness, and key-person risk. |
| FinTechCo | `data/demo/fintechco/` | Regulated fintech, compliance-heavy diligence, PCI scope, vendor concentration, access governance, and AI governance. |
| AcquisitionTargetCo | `data/demo/acquisition-target-co/` | Founder-led acquisition diligence, key-person dependency, aging architecture, security basics, and M&A integration readiness. |

Use SampleCo when the audience wants a balanced growth-equity SaaS diligence scenario. Good questions include:

- What are the top technology risks?
- What governance concerns should the board monitor?
- What AI readiness gaps exist?
- What should be included in the first 100-day technology plan?

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

1. Create or select an Investigation Workspace.
2. Open Document Upload.
3. Choose one or more PDFs.
4. Select `source_type`.
5. Select `classification`.
6. Click Upload PDFs.

Talking point:

The system captures governance metadata at the moment of ingestion. This is important for future filtering, audit, and access-control workflows.

### 2. Process Investigation

Click Process active investigation.

Talking point:

Processing parses, chunks, and embeds every document in the active investigation that needs processing. Local embeddings are the default, reducing cost and data exposure during demos.

### 3. Ask Executive Question

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

Leave Industry Benchmark / Cross-Investigation Analysis unchecked for investigation-scoped Q&A. Turn it on only when demonstrating benchmarking or trend analysis across multiple uploaded investigations.

### 4. Generate Technology Due Diligence Report

Click Generate Technology Due Diligence Report for the active investigation.

Talking point:

The report is not a chatbot answer. It is a structured diligence artifact scoped to the selected company workspace. It retrieves evidence by category, assigns red/yellow/green risk ratings, shows confidence, identifies recommended owners, and produces management questions, board discussion points, an executive risk heatmap, and a 30/60/90-day plan.

Explain the ratings:

- Red means material risk with stronger evidence or business impact.
- Yellow means manageable risk that needs validation or monitoring.
- Green means limited evidence of concern based on retrieved documents.
- Confidence indicates evidence strength. High confidence means stronger or broader citation support; medium means useful but incomplete support; low means weak, indirect, or limited evidence.

Show the Executive Risk Heatmap:

- Category shows the diligence area.
- Risk Rating shows red/yellow/green status.
- Confidence shows evidence strength.
- Evidence Count shows how many cited passages support the row.
- Primary Recommended Action gives the management action to validate or remediate the risk.

Good input packets include executive summary, technology assessment, security assessment, engineering organization review, AI readiness assessment, roadmap, cloud cost analysis, and integration readiness materials.

### 5. Generate 100-Day Technology Plan

Choose a plan type:

- `growth_equity` for SampleCo-style scaling plans.
- `acquisition_integration` for AcquisitionTargetCo-style integration planning, acquirer coordination, knowledge transfer, identity mapping, data migration, and support transition.
- `turnaround` for stabilization, immediate risk reduction, spend control, backup validation, production access review, and vulnerability triage.

Click Generate 100-Day Plan.

Talking point:

The plan is generated from the diligence findings, not from a new open-ended chat prompt. Red findings become days 1-30 actions, yellow findings become days 31-60 actions, and green findings become days 61-90 or monitoring actions.

Review the Executive One-Pager tab first:

- current state
- target state
- overall risk
- top 5 priorities
- first 30 days
- board decisions required
- success metrics
- key dependencies

Talking point:

The one-pager is the board-readable view. It hides raw JSON and compresses the operating plan into the sections a sponsor, CTO, or director would review first.

Review the Timeline Summary:

- Days 1-30: Stabilize
- Days 31-60: Govern
- Days 61-90: Modernize
- Days 91-100: Board Readout

Talking point:

The timeline explains sequencing. The plan starts with urgent risk containment, then adds governance, then moves into modernization, and ends with a board readout on residual risk and decisions required.

Review the Risk Heatmap:

The same category heatmap from the diligence report carries into the 100-day plan, so the audience can see which categories are red, yellow, or green and how much evidence supports each row.

Open the Full 100-Day Plan tab:

The full output includes a Timeline Summary, Plan at a Glance, Risk Heatmap, concrete deliverables, success metrics, structured board checkpoints, dependencies, limitations, and citations so management can inspect the source evidence.

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

Citations show metadata first, concise relevant excerpts second, and full source text only when the user asks to inspect it.

### 8. Run Evaluation

Open the Evaluation section and click Run Evaluation.

Talking point:

Evaluation is currently single-document. It is part of trust, not an afterthought. The system scores citation quality, groundedness, relevance, and executive usefulness.

### 9. Export Markdown Outputs

Use Download Board Memo.md, Download Technology Due Diligence Report.md, Download Executive One-Pager.md, Download 100-Day Technology Plan.md, or Download Evaluation Report.md.

Talking point:

Outputs are designed to move into executive workflows, board prep, diligence notes, or review packets. Markdown exports preserve the one-pager, timeline, heatmap, board checkpoints, citations, and limitations without exposing raw JSON.

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
- one-page planning summary for sponsor or board review
- timeline and heatmap views for quick prioritization
- cited diligence evidence
- repeatable evaluation
- exportable memos
- ability to compare operating risks across documents in the future

### Board Audience

Highlight:

- source-grounded summaries
- board questions
- recommended actions
- executive one-pager
- risk heatmap
- timeline summary
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
