# AcquisitionTargetCo Operational Risk Review

Synthetic demo document for Executive AI Advisor. Not based on any real company.

## Executive Summary

AcquisitionTargetCo's operational risk is moderate to high for an acquisition target. The product is stable in normal operations, but several critical processes depend on manual execution and personal knowledge. The largest risks are founder dependency, manual deployment, incomplete documentation, weak staging data controls, and untested recovery.

The acquirer should treat operational stabilization as a first 100-day priority.

## Deployment Risk

Deployments are manually coordinated and founder-approved. This process has kept changes cautious, but creates dependency and slows response. Rollback procedures are understood by the founder and senior engineer but not fully documented.

Integration will require more reliable deployment automation and release evidence.

## Backup and Recovery

RDS automated backups and S3 versioning exist. Restore testing is not recent. The team believes recovery would work but cannot provide current evidence.

This is one of the most important diligence findings. A restore test should be completed before or immediately after close.

## Cron Job Risk

Legacy cron jobs support reporting, notifications, syncs, and operational exports. Some jobs have alerts, while others are checked only when customer issues appear. The company needs a complete inventory of schedule, owner, inputs, outputs, failure mode, and customer impact.

## Documentation Risk

Documentation is incomplete and outdated. Operational knowledge resides with the founder and senior engineer. This creates continuity risk, onboarding delays, and integration risk.

## Security Operations Risk

Security ownership is informal. MFA is incomplete for some administrative tools, vulnerability management is not formalized, and customer data is copied into staging with weak masking. These issues should be remediated quickly because they are basic control expectations for an acquired SaaS asset.

## Customer Continuity

Customer retention is high, so operational changes must be sequenced carefully. The acquirer should avoid disrupting customer workflows during early integration. Support handoff should be planned before changing deployment, identity, or data flows.

## Recommendations

- Complete restore test and document recovery procedures.
- Create deployment and rollback runbooks.
- Inventory and monitor all cron jobs.
- Complete access review and MFA remediation.
- Mask staging data.
- Capture founder and senior engineer knowledge.
- Create operational dashboard for uptime, jobs, support escalations, and releases.

## Overall Assessment

The business is stable because experienced people know how to operate it. That is not enough after acquisition. Operational risk can be reduced substantially with documentation, automation, access control, and recovery testing.

## Board Questions

The board should ask management to answer practical operating questions: Who can deploy without the founder? When was the last successful restore test? Which cron jobs affect customer commitments? Which administrative tools lack MFA? Which customer data exists in staging? Which incidents would require the senior engineer to resolve?

These questions are intentionally operational. Acquisition risk often hides in ordinary workflows that never appear in a high-level architecture diagram. The buyer should insist on demonstrations, not just explanations.

The highest-value first milestone is proof that the product can be operated by a broader team. That means documented runbooks, secondary owners, tested backups, monitored jobs, and clear escalation paths.
