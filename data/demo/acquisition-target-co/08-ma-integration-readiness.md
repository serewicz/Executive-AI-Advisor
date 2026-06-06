# AcquisitionTargetCo M&A Integration Readiness

Synthetic demo document for Executive AI Advisor. Not based on any real company.

## Executive Summary

AcquisitionTargetCo has moderate to low integration readiness. The product is stable and valued by customers, but the operating model is highly dependent on founder knowledge, manual deployment, incomplete documentation, and informal security ownership.

The acquirer should plan for a structured integration program rather than assume rapid consolidation. The highest-risk areas are identity management, data model differences, deployment process, support handoff, roadmap interruption, and customer data governance.

## Integration Domains

| Domain | Readiness | Key Concern |
| --- | --- | --- |
| Identity management | Low | SSO and admin access patterns need review. |
| Data model | Low to moderate | Domain-specific schema and customer configuration. |
| Deployment | Low | Manual founder-approved process. |
| Support handoff | Moderate | Support knowledge exists but is informal. |
| Security | Low | MFA gaps, weak staging masking, no formal vuln process. |
| Roadmap | Moderate | Customer-driven roadmap may conflict with platform plans. |

## Identity Management

Identity integration will require careful planning. The product has existing user roles and customer-specific permissions. Administrative tools are separate from some customer-facing permission models. Not all administrative tools enforce MFA.

The acquirer should avoid immediate identity consolidation without mapping roles, support workflows, and customer impact.

## Data Model

The Django data model reflects years of customer-specific workflow decisions. Some fields are overloaded, and configuration is not fully documented. Data migration or consolidation into a platform-company data model may be harder than it appears from high-level diagrams.

Before integration, the acquirer should create a data dictionary, identify customer-specific fields, and map retention obligations.

## Deployment and Operations

Deployment is manual and founder-approved. This is a major integration blocker. The acquirer should document and stabilize deployment before attempting platform consolidation.

Legacy cron jobs should be inventoried because they may support customer commitments that are not obvious in the UI.

## Support Handoff

Support handoff is moderate risk. The customer-facing support team understands common workflows, but engineering escalations often rely on the founder or senior engineer. The acquirer should capture escalation runbooks and known issue playbooks.

## Recommendations

- Complete technical knowledge transfer before changing architecture.
- Inventory identity, roles, and administrative access.
- Create data dictionary and customer configuration map.
- Document deployment and rollback.
- Inventory cron jobs and support escalations.
- Sequence integration to protect customer retention.

## Overall Assessment

Integration is feasible but should be deliberate. The acquirer should prioritize stabilization and knowledge capture before consolidation. A rushed integration could harm customer retention and reduce acquisition value.

## Integration Due Diligence Checklist

Before close, the buyer should verify identity flows, customer roles, support escalation process, database schema ownership, cron job inventory, customer-specific configuration, backup restore evidence, staging data handling, and deployment steps. Each area should have an owner and a post-close remediation target.

The acquirer should also identify dependencies between commercial commitments and technical integration. For example, a large customer's promised report may depend on a cron job that only the founder understands. A billing workflow may depend on manual exports. A support process may rely on direct database inspection.

The integration team should preserve customer continuity while creating platform-company controls. This means sequencing governance improvements carefully and communicating internally before forcing product consolidation.
