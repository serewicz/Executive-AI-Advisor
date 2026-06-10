# User Guide

Executive AI Advisor is a board-facing document intelligence tool. It helps users upload complex business and technology documents, ask executive questions, generate board-level summaries, inspect citations, and evaluate output quality.

The product is designed for source-grounded analysis. It does not ask users to trust raw model output without evidence.

## Intended Users

- CTOs and technology executives
- PE operating partners
- Boards and investors
- Diligence teams
- AI governance leaders

## Supported Document Types

The current workflow is optimized for PDF documents such as:

- SEC filings
- diligence reports
- technology assessments
- cybersecurity assessments
- AI readiness reports
- board materials

## Synthetic Demo Datasets

The repository includes fictional demo datasets for safe local demonstrations:

- `data/demo/sampleco/`: mid-market B2B SaaS growth equity diligence scenario.
- `data/demo/fintechco/`: regulated fintech and compliance-heavy diligence scenario.
- `data/demo/acquisition-target-co/`: founder-led acquisition diligence and M&A integration-readiness scenario.

Each dataset includes multiple Markdown source documents plus a dataset README with suggested questions and expected risks. The documents are synthetic and not based on any real company. They are intended to help users test technology diligence reports, board technology briefs, AI governance assessments, risk scoring, 100-day technology plans, management interview questions, and M&A integration readiness.

Metadata captured during upload includes:

- `source_type`: `sec_filing`, `diligence_report`, `technology_assessment`, or `board_material`
- `classification`: `public`, `internal`, `confidential`, or `restricted`

## Workflow

The standard workflow is:

1. Create or select an investigation workspace.
2. Upload one or more PDFs into that workspace.
3. Parse PDFs into page-level text.
4. Chunk parsed pages into retrieval-ready passages.
5. Embed chunks for semantic search.
6. Ask executive questions scoped to the active investigation.
7. Run technology due diligence assessments.
8. Generate a technology due diligence report.
9. Generate a 100-day technology plan.
10. Generate a board summary.
11. Inspect citations and evidence.
12. Evaluate output quality.
13. Export Markdown memo, report, plan, or evaluation output.

## LLM Provider Selection

The Streamlit sidebar lets local demo users choose Mock, OpenAI, Anthropic, or Grok/xAI for answer and report generation. Mock remains the safest default for offline demonstrations and does not require an API key.

Users may choose their own provider keys for four reasons:

- Security: keys entered in Streamlit stay in the local session and are not saved by the app.
- Cost tracking: using a user-owned provider key lets usage and spend appear directly in the provider account.
- Provider control: users can compare Mock, OpenAI, Anthropic, and Grok outputs without changing application code.
- Governance: reports show which provider and model were used when the output was generated.

Provider and model metadata is shown in Streamlit reports and included in Markdown exports. API keys are never displayed or exported.

## Investigation Workspaces

Investigation workspaces, also called document sets, isolate documents by company, deal, or diligence effort. Use one workspace per company, such as `SampleCo Diligence` or `FinTechCo Diligence`.

When an investigation is active:

- uploaded PDFs are appended to that investigation
- the document list shows exactly which files are in scope
- Executive Q&A searches only documents in that investigation by default
- board summaries use only documents in that investigation by default
- previous company documents are excluded unless global search is explicitly selected

Removing a document from an investigation removes only the association. It does not delete the uploaded document.

## Document Upload

Upload one or more PDFs through the Streamlit UI or API. During upload, choose a source type and classification. These fields support later governance, filtering, and audit workflows.

## Processing Pipeline

The processing pipeline can process the active investigation in one step. For single-document fallback workflows, the individual actions are:

- Parse document: extracts page-aware text from the PDF.
- Chunk document: converts parsed text into retrieval-ready chunks.
- Embed document: generates vector embeddings for semantic search.

The document lifecycle status changes as processing progresses:

- `uploaded`
- `parsing`
- `parsed`
- `chunking`
- `chunked`
- `embedding`
- `embedded`
- `failed`

Streamlit shows each document status with a progress indicator. Buttons are disabled while processing is active, failed documents show visible error messaging, and a successful full pipeline ends with: `Processing complete. You can now run Q&A, Board Summary, Diligence Report, or 100-Day Plan.`

Use Refresh Status when another browser session, API call, or backend restart may have changed document state.

## Executive Q&A

Executive Q&A lets users ask questions such as:

```text
What cybersecurity risks are disclosed?
```

The system retrieves relevant chunks, assigns source labels such as `[S1]`, and produces an answer that should cite material claims.

By default, Streamlit scopes Executive Q&A to the active investigation workspace. If no workspace is active, it can scope to the selected document. Use Industry Benchmark / Cross-Investigation Analysis only when you intentionally want global retrieval. Global search may include documents from other investigations and companies, so it is for benchmarking and trend analysis rather than company-specific diligence.

Outputs include:

- answer
- confidence
- limitations
- citations
- source excerpts
- page ranges
- scope metadata

## Board Summary Generator

The Board Summary Generator creates a structured memo from retrieved document chunks.

Supported summary types:

- `technology_risk`
- `diligence_summary`
- `ai_readiness`
- `security_governance`
- `board_brief`

Board summaries include:

- executive summary
- key risks
- evidence
- board questions
- recommended actions
- limitations
- confidence
- citations

The Streamlit UI can export the board memo as Markdown.

## Technology Due Diligence Assessments

The diligence module produces structured assessments for:

- architecture
- security
- technical debt
- key person risk
- AI readiness

Each assessment returns:

- executive summary
- score from 1 to 5
- findings
- risks
- recommendations
- citations
- confidence
- limitations

The current implementation uses deterministic scoring and retrieved document evidence. It is intended to support diligence review, not replace technical interviews, architecture walkthroughs, or security testing.

## Technology Due Diligence Report

The Technology Due Diligence Report Generator creates a structured board-quality report for the active investigation workspace. It retrieves evidence only from documents attached to the selected workspace, so SampleCo, FinTechCo, and AcquisitionTargetCo investigations remain isolated unless the user intentionally uses cross-investigation analysis elsewhere.

Recommended inputs include:

- executive summary
- technology assessment
- security assessment
- engineering organization review
- AI readiness assessment
- technology roadmap
- cloud cost analysis
- M&A or integration readiness materials

The report covers:

- architecture
- security
- technical debt
- engineering organization
- key person risk
- AI readiness
- cloud cost
- integration readiness

Risk ratings:

- `red`: material technology risk supported by multiple evidence passages or strong business impact indicators.
- `yellow`: moderate risk, manageable but requiring validation, remediation, or monitoring.
- `green`: limited evidence of concern or controls appear adequate based on retrieved material.

Confidence levels:

- `high`: multiple relevant citations across more than one document.
- `medium`: one or two relevant citations, or evidence is useful but incomplete.
- `low`: weak, indirect, or limited evidence.

Outputs include executive summary, top risks, an executive risk heatmap, category findings, recommended owners, management questions, board discussion points, recommended actions, a 30/60/90-day plan, limitations, and citations with relevant excerpts. The report can be downloaded as Markdown.

The executive risk heatmap summarizes each diligence category in one table:

- category
- red/yellow/green risk rating
- confidence level
- evidence count
- primary recommended action

The heatmap is generated from the same scoped diligence findings as the report, so it reflects only the active investigation workspace.

## 100-Day Technology Plan

The 100-Day Technology Plan Generator converts Technology Due Diligence Report findings into a sequenced operating plan for a CTO, operating partner, or portfolio company. It does not regenerate findings from scratch. It consumes the existing findings, risk ratings, confidence levels, business impacts, recommended owners, and citations.

Supported plan types:

- `growth_equity`: use when a company is preparing to scale. The plan emphasizes scalability, governance, delivery predictability, feature flagging, observability, AI pilot selection, hiring, and FinOps.
- `acquisition_integration`: use for acquisition or post-close planning. The plan emphasizes acquirer coordination, knowledge transfer, identity and access mapping, data migration mapping, deployment handoff, documentation, and support transition.
- `turnaround`: use when urgent stabilization is needed. The plan emphasizes immediate risk reduction, non-critical spend freeze, backup and restore validation, key-person shadow sessions, production access review, vulnerability triage, and cost control.

Prioritization:

- red findings become days 1-30 actions
- yellow findings become days 31-60 actions
- green findings become days 61-90 or monitoring actions

Outputs include executive summary, executive one-pager, timeline summary, risk heatmap, phase-based actions, business rationale, owners, risk reduction, citations, success metrics, board checkpoints, dependencies, and limitations. The plan can be downloaded as Markdown.

The plan includes:

- Executive One-Pager tab for board-readable review
- Timeline Summary table showing Stabilize, Govern, Modernize, and Board Readout phases
- Executive Risk Heatmap table with category, risk rating, confidence, evidence count, and primary action
- 100-Day Plan at a Glance table
- Quick Wins for turnaround plans
- Days 1-30, 31-60, 61-90, and 91-100 board readout sections
- 2-4 concrete deliverables for each major action
- a success metric for each action
- structured board checkpoints with question, evidence requested, and decision needed

### Executive One-Pager

The Executive One-Pager is a concise view derived from the full 100-day plan. It is designed for board packets, sponsor updates, and management readouts. It includes:

- executive summary
- current state
- target state
- overall risk
- top 5 priorities
- first 30 days
- days 31-60
- days 61-90
- board decisions required
- success metrics
- key dependencies

The one-pager is available as a separate Streamlit tab and has its own Markdown download.

### Timeline Summary

The Timeline Summary shows how work is sequenced:

| Phase | Purpose |
| --- | --- |
| Days 1-30: Stabilize | Address the most urgent risks and create operating evidence. |
| Days 31-60: Govern | Add ownership, cadence, controls, and management discipline. |
| Days 61-90: Modernize | Convert remediation into operating leverage and durable improvements. |
| Days 91-100: Board Readout | Summarize completed work, residual risk, dependencies, and decisions required. |

Each phase includes a primary objective, key actions, expected outcomes, risk reduced, and board checkpoint.

### Scenario-Specific Plan Types

The plan language changes by scenario:

- `growth_equity` emphasizes scale readiness, delivery predictability, platform leverage, feature flags, observability, hiring coverage, AI governance, and FinOps.
- `acquisition_integration` emphasizes acquirer coordination, knowledge transfer, identity integration, data migration readiness, support handoff, documentation, and post-close continuity.
- `turnaround` emphasizes urgent stabilization, spend control, backup validation, privileged access review, vulnerability triage, production ownership, and operational discipline.

### Markdown Export

The Streamlit UI supports Markdown downloads for:

- Executive One-Pager
- full 100-Day Technology Plan
- Technology Due Diligence Report
- Board Summary
- Evaluation Report

Markdown exports are plain text and include the structured tables where applicable. They do not include raw JSON.

Export filenames are investigation-aware and include report type, plan type when applicable, and generation time. Examples:

- `SampleCo_Diligence_technology_due_diligence_2026-06-10_1432.md`
- `AcquisitionTargetCo_Diligence_100_day_plan_turnaround_2026-06-10_1432.md`
- `FinTechCo_Diligence_board_summary_2026-06-10_1432.md`

Each Markdown export starts with report metadata:

- Investigation
- Report Type
- Plan Type, when applicable
- Provider
- Model
- Generated At
- Document Set ID
- Included Documents

Exports never include provider API keys.

## Citations And Evidence

Citations connect an answer or memo claim back to source chunks. Citation cards show:

- source label
- document title
- page range
- relevant excerpt
- relevance reason, when available
- document ID
- chunk ID
- optional full source text

The system filters low-value chunks, such as table-of-contents style passages, by default. Citation excerpts are query-aware and designed to show the most relevant passage rather than the full chunk. Full source text remains available when users need to inspect the broader context.

## Confidence And Limitations

Advisor outputs include confidence and limitations. These are not guarantees. They are signals to help users understand whether the retrieved evidence appears strong, partial, or insufficient.

Common limitations include:

- the answer is limited to retrieved chunks
- evidence may be incomplete
- the mock provider was used for local development
- the system has not performed multi-document synthesis

## Evaluation

The Evaluation section runs default questions against a document and scores responses for:

- citation quality
- groundedness
- relevance
- executive usefulness

Evaluation results can be downloaded as Markdown. The current evaluation framework uses deterministic scoring, not an LLM judge.

## What The Tool Does Not Do

Executive AI Advisor:

- does not provide legal advice
- does not provide investment advice
- does not replace human diligence
- does not guarantee completeness
- does not independently verify the truth of source documents
- does not perform multi-document synthesis yet
- does not provide production authentication or access control yet

## Recommended Demo Questions

- What cybersecurity risks are disclosed?
- What operational risks are disclosed?
- What should the board monitor?
- What governance concerns exist?
- What dependencies create business risk?
