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
9. Generate a board summary.
10. Inspect citations and evidence.
11. Evaluate output quality.
12. Export Markdown memo, report, or evaluation output.

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
- `chunked`
- `embedded`
- `failed`

## Executive Q&A

Executive Q&A lets users ask questions such as:

```text
What cybersecurity risks are disclosed?
```

The system retrieves relevant chunks, assigns source labels such as `[S1]`, and produces an answer that should cite material claims.

By default, Streamlit scopes Executive Q&A to the active investigation workspace. If no workspace is active, it can scope to the selected document. Use Search across all documents only when you intentionally want global retrieval. Global search may include documents from other investigations.

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

Outputs include executive summary, top risks, category findings, recommended owners, management questions, board discussion points, recommended actions, a 30/60/90-day plan, limitations, and citations with relevant excerpts. The report can be downloaded as Markdown.

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
