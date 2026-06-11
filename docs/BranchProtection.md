# Branch Protection

Use branch protection to keep `main` stable while preserving a lightweight workflow for a personal portfolio repository.

## Recommended Rule

In GitHub:

1. Go to `Repo -> Settings -> Branches`.
2. Select `Add branch protection rule`.
3. Set branch name pattern to:

```text
main
```

Enable:

- Require a pull request before merging
- Require status checks to pass before merging
- Require branches to be up to date before merging
- Select the stable required check: `ci-validate`
- Allow squash merging

Do not require yet:

- two reviewers
- code owner review
- signed commits
- linear history

## Rationale

This is currently a personal portfolio repository. The goal is to protect `main`, require automated validation, and avoid accidental direct merges without adding team-level process friction.

As the project becomes collaborative or production-hosted, consider adding reviewer requirements, CODEOWNERS, signed commits, deployment environments, and release approvals.
