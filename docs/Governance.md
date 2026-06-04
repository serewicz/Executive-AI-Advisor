# Governance

Executive AI Advisor treats governance as a product requirement, not a later compliance wrapper.

## Artifact Provenance

Builds for the Dockerized service produce SLSA provenance so reviewers can connect a release artifact back to:

- The GitHub repository
- The source revision
- The GitHub Actions build workflow
- The generated Docker image artifact
- The release tag

This creates an auditable chain of custody for the application layer that will eventually process confidential and restricted executive documents.

## Portfolio Evidence

For demonstrations and portfolio review, capture:

- A screenshot of the GitHub Actions run showing the provenance artifact
- A screenshot of the GitHub Release assets showing the `.intoto.jsonl` file
- A short demo showing `slsa-verifier` passing against the release artifact

These artifacts communicate enterprise AI supply-chain awareness and support future SOC 2, vendor diligence, and board-level risk discussions.
