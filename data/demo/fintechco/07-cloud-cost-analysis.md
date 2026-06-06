# FinTechCo Cloud Cost Analysis

Synthetic demo document for Executive AI Advisor. Not based on any real company.

## Executive Summary

FinTechCo's cloud spend has increased 42 percent year over year. The increase is driven by customer growth, transaction event volume, Kubernetes compute expansion, PostgreSQL scale-up, Kafka retention, observability ingestion, and data transfer related to payment workflow processing.

The current spend is not necessarily excessive for an $18M ARR regulated workflow platform, but cost governance is immature. Finance receives monthly cloud totals, while engineering reviews service-level detail only when there is a spike. Cost attribution by customer, product line, and workflow is incomplete.

## Estimated Monthly Spend

| Category | Monthly Spend | Observation |
| --- | ---: | --- |
| Kubernetes compute | $42,000 | API and worker services scale with workflow volume. |
| PostgreSQL | $31,000 | Primary system of record and reporting pressure. |
| Kafka | $18,000 | Transaction event processing and retention. |
| Redis | $7,500 | Workflow state, caching, and idempotency. |
| Observability | $24,000 | Strong production logging, high ingestion growth. |
| S3 and data transfer | $13,000 | Files, exports, audit packets, and integration traffic. |
| Networking and NAT | $8,500 | Private subnet egress and cross-AZ patterns. |
| Security and compliance tooling | $9,000 | Scanning, evidence, and monitoring tools. |
| Total | $153,000 | Approximate monthly run rate. |

Annualized spend is approximately $1.84M, or 10.2 percent of ARR. The company should target improved leverage as revenue scales.

## Cost Drivers

Kubernetes compute is the largest driver. Many services are provisioned for peak payment workflow periods, while average utilization is lower. Horizontal pod autoscaling exists for critical services, but resource requests and limits are not consistently reviewed.

PostgreSQL costs have increased because the database handles operational transactions, workflow approvals, audit records, reporting queries, and reconciliation support. Read replicas help, but reporting and audit export workloads still create pressure.

Kafka costs are growing with transaction event volume and retention. Topic retention policies are not consistently aligned with business requirements. Some topics retain data longer than needed because ownership is unclear.

Observability is valuable but expensive. Production logging is strong, but log ingestion includes repetitive workflow events and debug fields that may not need full retention. Staging observability is weaker despite production log growth.

## FinOps Maturity

FinOps ownership is informal. Platform engineering watches Kubernetes and database spend. Finance reviews aggregate monthly bills. Product does not consistently see cost implications of feature decisions. Customer profitability analysis does not include reliable infrastructure allocation.

Tagging is partially implemented across Kubernetes namespaces and AWS resources. Environment tags are common, but product, owner, customer-impact, and compliance-scope tags are inconsistent.

## Optimization Opportunities

- Rightsize Kubernetes resource requests and limits.
- Review autoscaling policies for workflow workers.
- Move more reporting workloads away from primary PostgreSQL.
- Align Kafka retention with data retention policy.
- Reduce noisy log ingestion and tune trace sampling.
- Improve S3 lifecycle policies for audit exports and temporary files.
- Review NAT gateway and cross-AZ traffic patterns.
- Create customer and product-line cost attribution.

The goal should be 10 to 18 percent savings without reducing reliability or compliance evidence.

## Board-Level Risk

The main risk is that cloud spend grows faster than ARR as enterprise customers bring higher transaction volume, longer retention requirements, and more audit artifacts. If pricing does not reflect cost-to-serve, gross margin may compress.

The second risk is cost opacity. Without customer-level attribution, management may underprice large payment workflow customers or misread the profitability of advanced integration features.

## Recommendations

FinTechCo should establish a monthly cloud cost review with finance, platform engineering, product, and the VP Engineering. The company should define cost owners for Kubernetes, PostgreSQL, Kafka, observability, and S3. Architecture reviews should include cost impact for high-volume workflows.

Cloud cost should become a board metric alongside compliance readiness, uptime, and platform risk.

## Overall Assessment

Cloud spend is explainable but needs governance. FinTechCo can support growth if it treats FinOps as an operating discipline rather than a periodic cleanup exercise.

## Diligence Evidence To Request

The diligence team should request the last 12 months of AWS and observability spend, Kubernetes utilization reports, PostgreSQL performance reports, Kafka topic retention settings, S3 lifecycle policies, and the current tagging standard. Management should also provide any pricing analysis that connects customer contract size to workflow volume and cost-to-serve.

The board should pay special attention to enterprise customer economics. A large customer with heavy transaction volume, long retention requirements, and frequent audit exports may be profitable on ARR but expensive on infrastructure. Without customer-level cost attribution, management may not know which accounts are margin-dilutive.

Cloud optimization should not be treated as indiscriminate cost cutting. FinTechCo operates in a compliance-sensitive market, so some spending on observability, audit evidence, redundancy, and security tooling is appropriate. The goal is to remove waste while preserving trust.
