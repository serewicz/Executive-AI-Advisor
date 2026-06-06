# SampleCo Security Assessment

Synthetic diligence document. SampleCo is a fictional company created for Executive AI Advisor testing and demonstration.

## Executive Security Summary

SampleCo has a developing security program that is appropriate for an earlier-stage B2B SaaS company but incomplete for sustained enterprise expansion. The company has implemented several baseline controls, including MFA for core systems, encrypted AWS services, HTTPS everywhere, GitHub branch protections, basic vulnerability scanning, and role-based access controls in the application. However, governance, evidence management, access reviews, incident response, and vendor risk management are not yet mature.

The company is preparing for growth equity investment and expects to pursue larger enterprise customers. This will increase scrutiny on SOC 2 readiness, data handling, audit logs, secure software development, cloud access management, and AI governance. SampleCo should treat security maturity as a commercial enablement priority, not only a risk reduction effort.

Overall security risk is moderate. There is no evidence of a known breach or reckless control failure, but the program is informal in several areas that matter to enterprise buyers.

## Data and Trust Context

SampleCo stores confidential customer business information, including customer account records, renewal notes, support escalations, product usage summaries, stakeholder maps, task history, uploaded operational documents, and integration metadata from systems such as Salesforce, HubSpot, Zendesk, Jira, Slack, and Microsoft Teams.

The company does not intentionally store payment card data, protected health information, or consumer financial data. Even so, the stored information can be commercially sensitive. Customer documents may include strategic plans, customer lists, pricing notes, implementation risks, and executive escalation details. This makes security governance important for customer trust and contractual negotiations.

SampleCo has not completed a SOC 2 Type I or Type II audit. Several customers have requested security questionnaires, and the sales team reports that enterprise prospects increasingly ask for independent assurance.

## Identity and Access Management

MFA is enabled for Google Workspace, GitHub, AWS console access, and the major customer support tools. SSO is available internally through Google Workspace, but not all SaaS tools are centrally managed. Access provisioning is coordinated through IT and people operations, but the process depends heavily on manual checklists.

Quarterly access reviews are planned but not consistently completed. The last documented review covered GitHub and AWS access but did not fully cover Datadog, Sentry, HubSpot, Slack, Salesforce sandbox access, or customer support tooling. Departing employee access removal is usually completed quickly, but there is no automated evidence package.

AWS IAM has improved over the last year, but several roles remain broader than needed. The VP Engineering and two senior engineers have administrator-level permissions. Some deployment roles can access production resources beyond their immediate function. Temporary credentials are used in most cases, but service account ownership is not consistently documented.

## Application Security

The application implements user authentication, tenant-level authorization checks, and role-based permissions for common workflows. Enterprise customers can use SAML SSO, though configuration is currently handled through support and engineering assistance. Audit logs exist for selected administrative actions, but coverage is incomplete across all sensitive events.

The largest application security concern is inconsistent tenant isolation testing. The architecture uses shared infrastructure with logical tenant separation. This is common and acceptable when implemented rigorously. SampleCo has authorization checks in core routes, but automated tests do not comprehensively validate cross-tenant access prevention across older endpoints, admin workflows, integrations, and reporting exports.

Input validation is generally handled by the API framework, but file upload handling needs stronger governance. Uploaded files are stored in S3 with signed URL access. Content-type validation exists, but malware scanning, file classification, retention rules, and customer-facing controls are incomplete.

## Secure Software Development

SampleCo uses GitHub pull requests, branch protections, code review, and automated test workflows. Dependency scanning is enabled through GitHub Dependabot. Static analysis exists for selected Python and JavaScript projects, but results are not always reviewed on a defined SLA.

Secrets management is partially mature. Production secrets are stored in AWS Secrets Manager and injected at runtime. Some older staging and development secrets remain in manually managed environment files. No active hardcoded production API keys were identified during the assessment summary, but SampleCo should complete a formal secret scanning baseline and rotate high-risk credentials before a major financing process.

The company does not yet have a formal secure development lifecycle. Threat modeling is not standard for new features, security acceptance criteria are inconsistent, and high-risk changes do not require a dedicated security review. This will become more important as AI features, file handling, and enterprise integrations expand.

## Cloud Security

AWS resources are deployed across development, staging, and production accounts. Core data stores use encryption at rest. Public access is blocked on primary S3 buckets. The application runs behind an application load balancer with TLS. Security groups generally restrict direct access to databases and internal services.

The main cloud security gaps are governance and evidence. Not all legacy resources are defined in Terraform. CloudTrail is enabled, but centralized review and alerting are limited. GuardDuty is enabled in production, but alert routing and investigation procedures are informal. AWS Config rules are partially implemented.

Network segmentation is reasonable for the current size, but not all administrative paths are consistently restricted. Database access is not exposed publicly, but emergency access patterns should be documented and audited. The company should avoid allowing engineering convenience to become a permanent exception model.

## Incident Response and Monitoring

SampleCo has a draft incident response plan, but it has not been approved by the leadership team or tested in a tabletop exercise. Incident ownership typically falls to the VP Engineering, who coordinates with customer success and the CEO for customer communication. This creates key-person risk and can slow response during complex incidents.

Monitoring uses Datadog, Sentry, AWS CloudWatch, and Slack alerts. Alerts cover uptime, latency, error rates, queue depth, and selected security events. There is no centralized SIEM or formal security operations process. Logs are available, but retention and query workflows vary by system.

The company should establish a severity framework, incident commander rotation, customer notification templates, legal review triggers, and post-incident review practices. These steps are practical and achievable without building a large security team.

## Compliance and Governance

SampleCo does not yet have a formal risk register, control owner matrix, or policy review cadence. Policies exist for acceptable use and employee onboarding, but data classification, vendor risk, AI usage, incident response, and access control policies are incomplete.

SOC 2 readiness is a near-term priority. Based on current maturity, SampleCo likely needs 6 to 9 months to prepare for a credible Type I audit and 12 to 15 months to complete a Type II period, assuming consistent executive sponsorship. The most important readiness work includes access evidence, change management evidence, vendor reviews, incident response testing, vulnerability management, backup and recovery testing, and employee security training records.

## AI Security and Governance

No formal AI governance program exists. Employees use general-purpose AI tools for drafting, summarization, coding assistance, and sales enablement. Product management is exploring AI-generated account summaries and renewal risk narratives. There is no approved model inventory, no formal prohibited-data policy, no customer data handling standard for AI providers, and no model output review process.

This is an urgent governance gap because the company handles confidential customer information and is moving toward enterprise buyers. SampleCo should establish an AI acceptable use policy, define approved tools, prohibit upload of confidential customer data to unapproved systems, require human review for customer-facing AI outputs, and create audit logs for AI-enabled product features.

## Priority Recommendations

SampleCo should complete a 100-day security governance plan focused on practical controls. Recommended actions include:

- Create a security owner matrix with executive sponsorship.
- Complete a full access review across AWS, GitHub, production databases, support tools, observability tools, and customer systems.
- Reduce AWS administrator permissions and implement more granular break-glass access.
- Formalize incident response and complete a tabletop exercise.
- Start SOC 2 readiness with an external advisor.
- Improve tenant isolation tests and audit logging coverage.
- Establish vulnerability management SLAs.
- Implement a vendor risk intake process.
- Create and enforce an AI governance policy before customer-facing AI launch.

## Overall Assessment

SampleCo's security posture is not unusually weak for its stage, but it is below the threshold expected by larger enterprise customers and institutional investors. The company should not be represented as fully enterprise-ready today. With focused investment and leadership attention, the security program can mature quickly enough to support the next phase of growth.
