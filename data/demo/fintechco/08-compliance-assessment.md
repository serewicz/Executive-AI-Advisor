# FinTechCo Compliance Assessment

Synthetic demo document for Executive AI Advisor. Not based on any real company.

## Compliance Context

FinTechCo operates in payments and treasury workflows, which creates elevated customer expectations around control evidence, access governance, auditability, vendor oversight, and incident readiness. The company has completed SOC 2 Type II and is in PCI-DSS scope. Annual penetration testing is performed.

The compliance baseline is meaningful, but the operating model remains semi-manual. Evidence collection relies on compliance operations, engineering screenshots, ticket exports, and manual owner attestations. This creates diligence risk because controls may exist but be hard to prove quickly.

## SOC 2

SOC 2 controls cover security, availability, confidentiality, change management, access control, vendor management, incident response, and monitoring. The most recent Type II report had no severe exceptions, but management noted evidence delays and inconsistent review artifacts.

| Control Area | Maturity | Observation |
| --- | --- | --- |
| Change management | Moderate | Pull requests and deployment logs exist. Evidence is semi-manual. |
| Access reviews | Moderate | Quarterly reviews occur but documentation varies. |
| Incident response | Low to moderate | Plan exists; no test in last 12 months. |
| Vendor management | Moderate | Critical vendors reviewed, but concentration planning is incomplete. |
| Data retention | Low to moderate | Policy exists; enforcement is inconsistent. |

## PCI-DSS Scope

PCI-DSS scope is not fully minimized. FinTechCo uses third-party payment processing and does not intend to store full cardholder data, but payment workflow metadata, administrative support paths, and token-adjacent processes keep more systems near PCI scope than ideal.

Scope reduction should be a strategic compliance project. The company should update data-flow diagrams, segregate payment execution components, reduce support access to regulated workflows, and validate token handling responsibilities with the payment processor.

## Evidence Collection

Evidence collection is a diligence issue. Compliance operations maintains checklists, but control owners still gather evidence manually from GitHub, AWS, Kubernetes, ticketing systems, vendor portals, and observability tools.

The company should automate evidence where possible and assign clear control owners. This will reduce audit burden and improve investor confidence.

## Data Retention

A formal data retention policy exists, but enforcement is inconsistent. S3 exports, Kafka topics, audit support files, and support attachments have different retention behavior. Some retention settings are inherited from early customer requirements and have not been reviewed recently.

This matters for compliance, privacy, AI readiness, and cost control. Retention should be enforced through technical controls, not only policy documents.

## Incident Response

The incident response plan includes severity levels, roles, communication templates, and customer notification guidance. It has not been tested in the last 12 months. For a fintech company, this is a board-level compliance gap.

Recommended testing scenarios include payment workflow disruption, suspected unauthorized privileged access, payment processor outage, KYC provider outage, data exposure in support tooling, and AI-generated incorrect workflow guidance.

## Compliance Risks

- PCI-DSS scope remains broader than necessary.
- SOC 2 evidence collection is semi-manual.
- Access review evidence is inconsistent.
- Incident response testing is overdue.
- Vendor concentration planning is incomplete.
- Data retention enforcement is inconsistent.
- AI governance is not yet formalized.

## Recommendations

FinTechCo should create a compliance readiness program with executive ownership. Priority actions include PCI scope reduction, evidence automation, access review standardization, incident tabletop testing, vendor risk documentation, retention enforcement, and AI governance.

The board should receive quarterly compliance readiness updates with evidence quality, open control gaps, remediation deadlines, and ownership.

## Overall Assessment

FinTechCo has a meaningful compliance foundation, but audit readiness depends too much on manual effort. The company should use the investment period to turn compliance from periodic audit preparation into a repeatable operating system.

## Evidence Package Expectations

A mature diligence package should include the most recent SOC 2 Type II report, PCI responsibility matrix, penetration test executive summary, access review evidence, change management samples, vulnerability remediation evidence, vendor review records, incident response plan, and data retention policy. FinTechCo can produce many of these artifacts, but collection is slower than it should be because ownership is distributed.

The most revealing evidence will be control samples rather than policies. Diligence should inspect whether access reviews include actual owner attestation, whether high-risk findings have closure evidence, whether terminated users were removed from vendor portals, and whether retention policies are technically enforced.

Board oversight should focus on repeatability. Passing an audit is helpful, but the more important question is whether FinTechCo can produce evidence quickly, consistently, and without heroic manual work from compliance operations.
