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

Metadata captured during upload includes:

- `source_type`: `sec_filing`, `diligence_report`, `technology_assessment`, or `board_material`
- `classification`: `public`, `internal`, `confidential`, or `restricted`

## Workflow

The standard workflow is:

1. Upload a PDF.
2. Parse the PDF into page-level text.
3. Chunk parsed pages into retrieval-ready passages.
4. Embed chunks for semantic search.
5. Ask executive questions.
6. Generate a board summary.
7. Inspect citations and evidence.
8. Evaluate output quality.
9. Export Markdown memo or evaluation report.

## Document Upload

Upload a PDF through the Streamlit UI or API. During upload, choose a source type and classification. These fields support later governance, filtering, and audit workflows.

## Processing Pipeline

The processing pipeline has three main actions:

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

Outputs include:

- answer
- confidence
- limitations
- citations
- source excerpts
- page ranges

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

## Citations And Evidence

Citations connect an answer or memo claim back to source chunks. Citation cards show:

- source label
- document title
- page range
- excerpt
- document ID
- chunk ID

This makes answers reviewable and helps users challenge or validate the system’s conclusions.

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
