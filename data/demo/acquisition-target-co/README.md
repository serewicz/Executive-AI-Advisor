# AcquisitionTargetCo Demo Dataset

Synthetic demo document for Executive AI Advisor. Not based on any real company.

## Company Profile

AcquisitionTargetCo is a fictional $8M ARR founder-led vertical B2B SaaS company with 48 employees and a 6-person engineering team. The product is profitable, valued by customers, and has high retention, but the technology environment reflects a lean founder-led operating model.

The company runs a monolithic Django application on AWS EC2 with RDS PostgreSQL, S3, and legacy cron jobs. It is being evaluated as a potential acquisition target for a PE-backed platform company.

## Document List

| File | Purpose |
| --- | --- |
| `01-executive-summary.md` | Acquisition diligence summary and board-level risks |
| `02-technology-assessment.md` | Architecture, reliability, documentation, and technical debt |
| `03-security-assessment.md` | Security ownership, MFA, staging data, and vulnerability management |
| `04-engineering-organization.md` | Team capacity, founder dependency, and operating model |
| `05-ai-readiness.md` | Low AI readiness, data quality, and governance gaps |
| `06-technology-roadmap.md` | First 100 days and 12-month remediation plan |
| `07-cloud-cost-analysis.md` | Stable cloud spend and cost attribution gaps |
| `08-ma-integration-readiness.md` | Integration risks for platform-company acquisition |
| `09-operational-risk-review.md` | Backup, deployment, support, and continuity risks |

## Intended Demo Use

Use this dataset to test founder-led acquisition diligence, M&A integration readiness, key-person risk scoring, operational risk analysis, and first 100-day post-close planning.

## Suggested Questions

- What are the top acquisition technology risks?
- What key-person risks exist?
- What integration risks should the acquirer plan for?
- What security gaps require immediate remediation?
- What should be addressed in the first 100 days post-close?
- What diligence questions should management answer?

## Expected Risks The System Should Detect

- Architecture is a monolithic Django application.
- Deployment is manual and founder-approved.
- Minimal automated test coverage.
- Documentation is incomplete.
- Restore testing is not recent.
- Security ownership is informal.
- MFA is not enabled for all administrative tools.
- No formal vulnerability management process exists.
- Customer data is duplicated into staging with weak masking.
- One founder and one senior engineer hold most operational knowledge.
- Integration readiness is moderate to low.
