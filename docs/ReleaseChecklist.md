# Release Checklist

Use this checklist before creating a stable demo or portfolio release.

## Before Tagging

Run tests:

```bash
pytest -v
```

Build and start the local stack:

```bash
docker compose up --build
```

Apply migrations:

```bash
docker compose exec api alembic upgrade head
```

Run a Streamlit smoke test:

```bash
streamlit run ui/streamlit_app.py
```

Validate the executive workflow:

- Upload demo PDFs
- Process all documents
- Generate Technology Due Diligence Report
- Generate 100-Day Plan
- Download Markdown exports
- Confirm citations and evidence are scoped to the active investigation

Run the secret scan:

```bash
python scripts/check_no_secrets.py
```

## Tagging

Create and push the release tag:

```bash
git tag v0.x.0
git push origin v0.x.0
```

## After Tagging

Confirm:

- CI passes
- SLSA provenance workflow succeeds for the release
- Release assets and provenance artifacts are present where expected
- README and demo documentation match the released behavior
