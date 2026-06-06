# FinTechCo Security Assessment

Synthetic demo document for Executive AI Advisor. Not based on any real company.

## Security Posture

FinTechCo has moderate security maturity. The company has implemented important baseline controls, including SOC 2 Type II controls, annual penetration testing, MFA for core systems, centralized production logging, vulnerability scanning, and formal customer security questionnaire support. These controls are meaningful and support current commercial motion.

The concern is consistency and governance depth. Privileged access reviews are scheduled quarterly but inconsistently documented. PCI-DSS scope is not fully minimized. Incident response exists on paper but has not been tested in the last 12 months. Security leadership is distributed across engineering, DevOps, compliance operations, and the VP Engineering, with no dedicated senior security leader.

## Access Governance

MFA is enabled for AWS, GitHub, Kubernetes administrative access, Google Workspace, production observability, and the primary payment processor portal. SSO coverage is broad but not complete. Some vendor portals and finance operations tools are not fully integrated into the central identity provider.

Privileged access reviews occur quarterly. Evidence quality varies by system. AWS and GitHub evidence is usually complete, while Kubernetes cluster role reviews, database break-glass access, and payment processor portal permissions are less consistently documented.

| Area | Current State | Risk |
| --- | --- | --- |
| AWS IAM | MFA and role-based access exist | Some roles remain broader than necessary. |
| Kubernetes RBAC | Admin access is limited but manually reviewed | Review evidence is inconsistent. |
| Database access | Break-glass procedures exist | Usage evidence is not always retained. |
| Vendor portals | Access is business-critical | SSO and review coverage vary. |

## Application Security

The application has role-based access controls for payment workflow initiation, approvals, reconciliation views, and administrative functions. Sensitive workflows require approval steps and audit logging. Customer tenant isolation is implemented logically in application services and database queries.

Security tests cover core authorization paths, but coverage is weaker for administrative tools and legacy payment workflow exceptions. The company should expand tenant isolation and privileged workflow testing before larger enterprise expansion.

Annual penetration testing is performed. Recent findings were mostly medium and low severity, including missing security headers in selected internal tools, overly permissive administrative workflows, and inconsistent rate limiting on non-core APIs. Remediation is tracked, but closure evidence is sometimes handled manually.

## PCI-DSS and Data Protection

FinTechCo is in PCI-DSS scope because payment workflow metadata and selected token-handling workflows interact with regulated processes. The company does not intend to store full cardholder data, but scope is broader than necessary because several administrative and support workflows remain adjacent to payment execution paths.

Data encryption at rest and in transit is implemented across core AWS services. PostgreSQL, S3, Kafka, and Redis are configured with encryption controls appropriate for the current stage. Data retention policy exists, but enforcement is inconsistent across S3 exports, Kafka retention, audit artifacts, and support attachments.

## Incident Response

The incident response plan defines severity levels, incident commander role, customer communication owner, legal escalation, and post-incident review. However, the plan has not been tested in the last 12 months. The last tabletop exercise was completed before several Kubernetes and Kafka changes were introduced.

This creates a governance gap. For a regulated fintech platform, the board should expect evidence that incident procedures work under current architecture and current team structure.

## Security Leadership

The engineering team has strong domain knowledge but limited dedicated security leadership. Security ownership is shared among the head of DevOps, compliance operations, and senior engineers. This is workable at current scale but will not be enough for a larger enterprise customer base or more complex PCI scope reduction.

FinTechCo should consider hiring a security lead or fractional CISO with fintech and compliance experience. The role should own security roadmap, access governance, vulnerability management, incident readiness, vendor security review, and AI governance partnership.

## Priority Risks

- PCI-DSS scope is broader than necessary.
- Privileged access reviews lack consistent evidence.
- Incident response has not been tested recently.
- Security leadership is fragmented.
- Data retention policy enforcement is inconsistent.
- Administrative tools need stronger security coverage.
- AI use cases are emerging before governance is formalized.

## Recommendations

1. Complete a PCI scope reduction project with clear data-flow diagrams.
2. Centralize access review evidence and require system owner attestation.
3. Run incident response tabletop exercises twice per year.
4. Expand automated authorization tests for administrative and tenant-sensitive workflows.
5. Assign a named security leader with budget and authority.
6. Implement retention enforcement for S3, Kafka, and audit artifacts.
7. Establish AI governance before support, fraud triage, or finance AI workflows reach production.

## Overall Assessment

FinTechCo is not starting from zero. It has meaningful controls and audit experience. The risk is that security operations are still too manual and fragmented for the company's growth trajectory. The board should monitor access governance, PCI scope, incident readiness, and security leadership capacity.
