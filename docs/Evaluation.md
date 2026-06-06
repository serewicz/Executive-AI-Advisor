# Evaluation

Executive AI Advisor includes a deterministic evaluation framework for scoring advisor Q&A outputs. Evaluation exists to make generated outputs reviewable, repeatable, and suitable for governance conversations.

## Purpose

The evaluation workflow scores whether an advisor answer is:

- cited
- grounded in retrieved evidence
- relevant to the question
- useful for executive decision-making

Each run is stored in Postgres as an `EvaluationRun` record.

## API

Run an evaluation:

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

Response includes:

- evaluation run ID
- document ID
- evaluation type
- average score
- per-question results
- citations
- notes

## Default Question Set

Default questions live in:

```text
docs/evaluation/default_questions.json
```

Included questions:

- What cybersecurity risks are disclosed?
- What operational risks are disclosed?
- What governance concerns exist?
- What should the board monitor?
- What dependencies create business risk?

## Scoring Categories

### Citation Score

Rules:

- `1.0`: citations exist and cited source labels appear in the answer
- `0.5`: citations exist but are not referenced clearly
- `0.0`: no citations

### Groundedness Score

Rules:

- `1.0`: answer has citations and limitations
- `0.7`: answer has citations but no limitations
- `0.3`: answer has no citations
- `0.0`: answer appears empty

### Relevance Score

Uses deterministic keyword overlap between:

- question
- expected themes
- answer
- citation excerpts

### Executive Usefulness Score

Rewards answer language related to:

- risks
- actions
- recommendations
- board monitoring
- governance
- controls
- confidence
- limitations

## Streamlit Evaluation

The Streamlit UI includes an Evaluation section that can:

- run the default question set
- display average score
- display per-question scores
- show citations and notes
- download a Markdown evaluation report

## Current Limitations

- deterministic scoring only
- no RAGAS integration yet
- no LLM-as-judge yet
- no multi-document evaluation
- no background evaluation jobs
- no dashboards yet

## Future Direction

Planned evaluation improvements:

- RAGAS support
- LLM-as-judge scoring with strict rubrics
- regression baselines
- score thresholds for release gates
- trend reporting over time
- governance dashboards

Evaluation matters because it creates auditable evidence for generated outputs instead of relying on subjective review alone.
