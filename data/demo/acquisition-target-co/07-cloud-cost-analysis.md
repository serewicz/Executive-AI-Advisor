# AcquisitionTargetCo Cloud Cost Analysis

Synthetic demo document for Executive AI Advisor. Not based on any real company.

## Executive Summary

AcquisitionTargetCo's cloud spend is stable and modest for an $8M ARR vertical SaaS business. The company uses AWS EC2, RDS PostgreSQL, S3, and supporting services. Spend is not currently a major concern, but cost allocation by customer, product line, and workload is weak.

The cloud environment reflects simplicity rather than optimized governance. This is acceptable pre-close but should be improved during integration.

## Estimated Monthly Spend

| Category | Monthly Spend | Notes |
| --- | ---: | --- |
| EC2 application servers | $8,500 | Monolith, background workers, and admin tools. |
| RDS PostgreSQL | $7,800 | Primary database and limited replicas. |
| S3 | $2,200 | Attachments, exports, report files. |
| CloudWatch and logs | $1,600 | Basic logging and alarms. |
| Networking | $1,400 | Load balancing, transfer, NAT. |
| Backup and snapshots | $1,100 | RDS snapshots and selected file backups. |
| Miscellaneous | $1,900 | DNS, email, queues, utility services. |
| Total | $24,500 | Approximate monthly run rate. |

Annualized cloud spend is approximately $294,000, or 3.7 percent of ARR. This is reasonable, but not deeply analyzed.

## Cost Governance

Cost governance is informal. The founder reviews monthly bills and approves major infrastructure changes. Engineering investigates spikes when they occur. There is no regular cost review with finance or product.

Tagging is inconsistent. Environment tags are common, but customer, product line, owner, and workload tags are incomplete. This makes it hard for an acquirer to understand cost-to-serve.

## Cost Risks

The largest cost risk is not overspend today. It is unknown cost behavior after integration. If the product is migrated, consolidated, or connected to platform-company systems, infrastructure costs may change materially.

Legacy cron jobs and report exports may also create hidden workload costs during customer growth or data migration.

## Optimization Opportunities

- Improve tagging and cost allocation.
- Review EC2 utilization and instance sizing.
- Validate RDS storage growth and backup retention.
- Apply lifecycle policies to S3 exports.
- Inventory cron job resource usage.
- Include cloud cost in integration planning.

## Overall Assessment

Cloud cost is not a major acquisition blocker. The acquirer should treat cost visibility as part of integration readiness and operational maturity rather than a primary value creation lever.

## Integration Cost Considerations

Cloud cost may increase temporarily after acquisition. Better logging, vulnerability scanning, backup testing, staging data remediation, and deployment automation all add some cost. That increase is acceptable if it reduces operational risk and improves governance.

The acquirer should build a baseline before making changes. The baseline should include monthly AWS spend, EC2 utilization, RDS storage growth, backup retention, S3 object growth, cron job compute usage, and data transfer. Without this baseline, post-close integration teams may confuse normal modernization cost with waste.

Customer profitability analysis should be introduced gradually. The target's pricing model may not reflect storage, export, support, or custom workflow intensity. Better allocation will help the acquirer decide which customers or product lines need pricing changes.
