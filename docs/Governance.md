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

## AI Incident Response and Board Escalation

AI governance should include incident response, not only acceptable-use policies.

Organizations should define what qualifies as an AI incident. AI incidents may include sensitive data exposure, unauthorized model behavior, unsafe outputs, model/provider compromise, prompt injection, loss of human oversight, material hallucination in high-risk workflows, or uncontrolled AI system behavior.

Management should define escalation paths for security, legal, compliance, executive leadership, and the board. Boards should receive clear reporting on material AI incidents, remediation status, control gaps, and lessons learned.

This is governance readiness guidance, not legal advice. Reporting obligations vary by jurisdiction, company role, system type, and incident type. Legal and compliance counsel should confirm applicable obligations.
