# Exact Demo Tutorial

This tutorial walks through a local executive demo from a clean clone to a cited board memo.

Executive AI Advisor is safe for a local demo on your own machine. It is not ready to expose publicly without authentication, database lockdown, production server settings, and protected API docs.

## 1. Clone And Enter The Repository

```bash
git clone https://github.com/serewicz/Executive-AI-Advisor.git
cd Executive-AI-Advisor
```

## 2. Create Local Configuration

```bash
cp .env.example .env
```

The default local setup uses:

- local embeddings
- mock LLM responses
- PostgreSQL through Docker Compose

No OpenAI API key is required for the default demo.

## 3. Start The API And Database

```bash
docker compose up --build
```

Wait until the API logs show Uvicorn is running. Then confirm health from a second terminal:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "database": "ok"
}
```

## 4. Install Local UI And Test Dependencies

In the second terminal:

```bash
python -m pip install -r requirements.txt
```

If your shell uses `python3` instead of `python`, run:

```bash
python3 -m pip install -r requirements.txt
```

## 5. Start Streamlit

```bash
streamlit run ui/streamlit_app.py
```

Open:

```text
http://localhost:8501
```

If the API is running somewhere else:

```bash
API_BASE_URL=http://localhost:8000 streamlit run ui/streamlit_app.py
```

## 6. Choose Demo Source Material

The app currently uploads PDFs. The repository includes synthetic Markdown datasets under:

- `data/demo/sampleco/`
- `data/demo/fintechco/`
- `data/demo/acquisition-target-co/`

For a polished demo, convert one or more Markdown files from a dataset to PDF using your preferred tool. Common options:

- open the Markdown preview in an editor and print to PDF
- use a Markdown-to-PDF extension
- use `pandoc` if already installed

Example with `pandoc`:

```bash
pandoc data/demo/sampleco/01-executive-summary.md \
  -o /tmp/sampleco-executive-summary.pdf
```

Recommended first demo:

```text
data/demo/sampleco/01-executive-summary.md
```

Convert it to a PDF, then upload the PDF through Streamlit.

## 7. Upload The PDF

In Streamlit:

1. Open Document Upload.
2. Upload the SampleCo PDF.
3. Set `source_type` to `technology_assessment` or `board_material`.
4. Set `classification` to `confidential`.
5. Click Upload PDF.

Copy or keep visible the returned document ID. Streamlit stores the selected document ID for the rest of the workflow.

## 8. Process The Document

Use the Processing Pipeline buttons in order:

1. Parse document.
2. Chunk document.
3. Embed document.

Expected lifecycle:

```text
uploaded -> parsed -> chunked -> embedded
```

## 9. Ask A Scoped Executive Question

In Executive Q&A, ask:

```text
What are the top technology risks?
```

Leave Search across all documents unchecked.

Expected behavior:

- The answer is scoped to the selected document.
- Citations come only from that document.
- The response metadata shows document scope.
- Citation cards show concise relevant excerpts.
- Full source text is available only when expanded.

Use Search across all documents only when you intentionally want cross-document retrieval.

## 10. Generate A Board Summary

In Board Summary Generator:

1. Confirm the document ID is populated.
2. Choose `technology_risk`.
3. Click Generate Board Summary.

Expected output:

- executive summary
- key risks
- evidence
- board questions
- recommended actions
- confidence
- limitations
- citations with relevant excerpts

Download the memo with Download Board Memo.md.

## 11. Run Evaluation

In Evaluation:

1. Confirm the document ID is populated.
2. Click Run Evaluation.

Expected output:

- average score
- per-question citation score
- groundedness score
- relevance score
- executive usefulness score
- notes
- visible citations without nested expander errors

Download the evaluation report with Download Evaluation Report.md.

## 12. Suggested Demo Questions

For SampleCo:

- What are the top technology risks?
- What AI governance gaps exist?
- What should the board monitor?
- What should be included in the first 100-day technology plan?

For FinTechCo:

- What compliance risks should the board monitor?
- What vendor concentration risks exist?
- What AI governance gaps exist?
- What should be included in a 100-day technology plan?

For AcquisitionTargetCo:

- What are the top acquisition technology risks?
- What key-person risks exist?
- What integration risks should the acquirer plan for?
- What security gaps require immediate remediation?

## 13. Run Tests

```bash
pytest -v
```

Expected result:

```text
all tests pass
```

## 14. Shut Down

Stop Streamlit with `Control-C`.

Stop Docker Compose with:

```bash
docker compose down
```
