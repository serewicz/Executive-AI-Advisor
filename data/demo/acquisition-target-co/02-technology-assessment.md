# AcquisitionTargetCo Technology Assessment

Synthetic demo document for Executive AI Advisor. Not based on any real company.

## Architecture Overview

AcquisitionTargetCo runs a monolithic Django application on AWS EC2. The application includes customer workflows, administration tools, reporting, billing support, user management, and scheduled processing. PostgreSQL on Amazon RDS is the primary database. S3 stores customer attachments, report exports, and generated files. Legacy cron jobs run on EC2 instances and perform nightly reporting, customer notifications, data syncs, and billing-related exports.

This architecture is common for a profitable founder-led SaaS company. It is not inherently bad. The issue is that operating discipline, documentation, and automation have not kept pace with customer importance or acquisition readiness.

## System Components

| Component | Role | Risk |
| --- | --- | --- |
| Django monolith | Core product and admin workflows | Large change surface and limited modularity. |
| EC2 | Application hosting | Manual server management and deployment complexity. |
| RDS PostgreSQL | System of record | Limited read replicas and manual performance tuning. |
| S3 | Attachments and exports | Retention and access patterns need review. |
| Cron jobs | Nightly and scheduled workflows | Limited observability and documentation. |

## Scalability

The platform supports current usage and has not experienced sustained scalability failure. Customer retention is high, and the product is stable for normal workloads. However, scaling depends on careful manual management rather than mature automation.

PostgreSQL is the main operational dependency. Read replicas exist for limited reporting workloads, but most application traffic still depends on the primary database. Query optimization is handled reactively by the founder and senior engineer. There is no formal performance review cadence.

Legacy cron jobs create operational risk. Some jobs perform important customer communications and reporting work, but ownership, retry behavior, and failure alerts vary. A missed cron job can create customer support issues without immediate engineering awareness.

## Software Delivery

Deployment is manual and founder-approved. Engineers prepare changes, the founder reviews release notes, and deployments are executed during low-traffic windows. This model has limited the frequency of major incidents, but it does not scale and creates unnecessary dependency.

There is no formal architecture decision record process. Technical decisions are discussed in Slack, issue comments, or directly with the founder. This creates historical knowledge gaps for the acquirer.

Automated test coverage is minimal. Critical paths are often manually validated after release. This increases regression risk and slows integration work.

## Documentation

Documentation is incomplete. There are partial setup notes, a dated architecture diagram, and several runbook fragments. The most reliable source of truth remains the founder and senior engineer.

Missing documentation includes:

- Current architecture diagram.
- Deployment and rollback procedure.
- Database restore procedure.
- Cron job inventory.
- Customer-specific configuration guide.
- Security control ownership.
- Integration mapping for buyer systems.

## Technical Debt

Technical debt is moderate to high. It is concentrated in the monolith, cron jobs, manual deployment, limited tests, and undocumented customer-specific behavior. The system does not need an immediate rewrite, but it needs stabilization and modularization planning.

## Recommendations

- Document architecture and operational runbooks immediately.
- Create an inventory of cron jobs with owner, schedule, failure mode, and customer impact.
- Improve deployment automation and rollback.
- Add automated tests for critical customer workflows.
- Create architecture decision records for material changes.
- Review PostgreSQL performance and replica usage.
- Plan selective modularization after post-close stabilization.

## Overall Assessment

The technology is commercially proven but operationally under-mature. The acquirer should plan for documentation, automation, test coverage, and deployment modernization before pursuing larger integration or platform consolidation work.

## Acquisition Implications

The monolith should be treated as a known operating asset, not an immediate modernization failure. It likely contains years of domain-specific business rules that customers depend on. A premature rewrite could damage the very retention profile that makes the company attractive.

The better post-close strategy is to stabilize the monolith, improve observability, add tests around revenue-critical workflows, and document data models before making architectural changes. After the first stabilization phase, the acquirer can decide whether to modularize reporting, integrations, identity, or billing.

Important diligence questions include: Which modules are hardest to change? Which database tables are most customer-specific? Which cron jobs have no owner? Which support fixes require direct database edits? Which parts of the system are understood only by the founder or senior engineer?
