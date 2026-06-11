# Contributing

Executive AI Advisor uses a protected-main workflow. Keep changes reviewable, tested, and free of secrets.

## Development Workflow

1. Create a feature branch from `main`.
2. Make focused changes in that branch.
3. Run the local validation checks before opening a pull request.
4. Open a pull request into `main`.
5. Use squash merge after review and passing CI.

## Required Local Checks

Run tests:

```bash
python -m pytest -v
```

Run the tracked-file secret scan:

```bash
python scripts/check_no_secrets.py
```

After schema changes, run Alembic:

```bash
docker compose up --build
docker compose exec api alembic upgrade head
```

## Secrets

Do not commit `.env`, API keys, provider tokens, customer documents, or private diligence materials. Use `.env.example` for placeholders only.

## Pull Requests

Pull requests should explain:

- what changed
- why it changed
- how it was tested
- any migration or setup impact

Keep pull requests small enough for executive and technical review.
