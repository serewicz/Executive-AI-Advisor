# SampleCo Cloud Cost Analysis

Synthetic diligence document. SampleCo is a fictional company created for Executive AI Advisor testing and demonstration.

## Executive Summary

SampleCo's AWS spend is material but not alarming for a $12M ARR B2B SaaS company. The company spends approximately $86,000 per month on AWS and related observability infrastructure, or about $1.03M annually. This represents approximately 8.6 percent of ARR. Gross margin remains acceptable at approximately 79 percent, but cloud cost growth is outpacing revenue growth in several areas.

The most important cost drivers are Amazon RDS, ECS Fargate compute, observability tooling, data transfer, integration processing, and S3 storage growth. The largest savings opportunities are database rightsizing, reserved commitments, storage lifecycle policies, NAT gateway optimization, improved job scheduling, and reducing unnecessary observability ingestion.

Cloud cost risk is moderate. There is no sign of runaway infrastructure waste, but the company lacks formal FinOps ownership. Cost management is handled reactively by the VP Engineering and platform engineers. This is not sufficient for the next stage of growth.

## Monthly Spend Overview

Estimated average monthly cloud and infrastructure spend:

| Category | Monthly Spend | Notes |
| --- | ---: | --- |
| Amazon RDS PostgreSQL | $22,000 | Primary production database, read replica, backups, provisioned storage |
| ECS Fargate compute | $18,500 | API services, workers, scheduled jobs |
| Datadog and Sentry | $12,000 | Metrics, logs, traces, frontend and backend errors |
| Data transfer and CloudFront | $8,000 | Customer exports, uploaded files, integration traffic |
| S3 storage and requests | $5,500 | Customer documents, exports, event archives |
| ElastiCache Redis | $4,800 | Cache, job coordination, rate limiting |
| NAT gateways and networking | $4,200 | Cross-AZ traffic, private subnet egress |
| AWS Support | $3,800 | Business support plan |
| ECR, CloudWatch, Lambda, misc. | $7,200 | Build artifacts, logs, utility functions, alarms |
| Total | $86,000 | Approximate monthly run rate |

Costs increased approximately 32 percent over the last twelve months while ARR increased approximately 24 percent. The difference is not yet severe, but it indicates the need for stronger cost controls before enterprise data volume increases.

## Unit Economics

At $12M ARR and $1.03M annual cloud and observability spend, infrastructure consumes approximately 8.6 percent of ARR. This is acceptable for a workflow-heavy SaaS platform, but SampleCo should target a steady-state cloud cost ratio closer to 6 to 7 percent of ARR as the business scales.

Infrastructure cost per customer averages approximately $410 per month across 210 customers. This average hides variation. Large customers with heavy integrations, frequent reporting refreshes, and large document storage footprints can cost more than five times the median customer. SampleCo does not yet allocate cloud cost by tenant, which limits pricing and profitability analysis.

Gross margin is approximately 79 percent after hosting, support tooling, customer support payroll, and implementation costs. Management targets 82 to 84 percent gross margin over the next 18 months. Cloud optimization alone will not achieve that target, but it can contribute meaningfully.

## Key Cost Drivers

RDS is the largest single cost category. The production PostgreSQL instance has been scaled up to handle nightly reporting jobs and large integration syncs. Some of this capacity is needed, but analytical workloads are increasing database cost. Storage growth is also notable because large tables retain historical integration logs and usage events longer than necessary.

ECS Fargate spend is driven by always-on API services, background workers, and scheduled jobs. Worker utilization is uneven. Some workers are overprovisioned for peak integration windows and underutilized for much of the day. Batch jobs sometimes run concurrently and compete for database capacity.

Observability costs have increased quickly. Datadog log ingestion includes noisy worker logs, integration debug output, and repetitive application events. Sentry event volume is also elevated because several low-priority frontend errors generate repeated alerts. The engineering team values the tooling, but ingestion policies are not well tuned.

Data transfer costs are rising as customer exports, document downloads, and integration traffic grow. CloudFront helps with static assets, but private networking and NAT gateway costs remain higher than expected due to architecture patterns in worker egress.

S3 storage is growing steadily. Customer-uploaded documents, exports, historical event archives, and integration payload samples are not consistently governed by lifecycle policies. Some temporary exports are retained longer than needed.

## Cost Governance

SampleCo does not have a formal FinOps process. AWS budgets exist for production and staging, but thresholds are broad and alerts usually route to engineering. Product and finance do not receive regular tenant-level cost reporting. Engineering evaluates costs during infrastructure changes, but cost acceptance criteria are not part of every architecture decision.

Tagging coverage is partial. Production resources generally have environment tags, but service, owner, and cost-center tags are inconsistent. Older resources created outside Terraform are the least consistently tagged. This makes it difficult to attribute costs to product areas or customer segments.

The VP Engineering reviews AWS bills monthly. Platform engineers investigate spikes when requested. There is no standing monthly cloud cost review with finance, product, and engineering.

## Optimization Opportunities

SampleCo can likely reduce current monthly spend by 12 to 20 percent without compromising reliability. Recommended actions include:

- Purchase reserved instances or savings plans for stable RDS and compute workloads.
- Review RDS instance sizing and storage configuration after separating reporting workloads.
- Introduce S3 lifecycle policies for temporary exports, old integration payload samples, and historical event archives.
- Tune Datadog log ingestion and reduce noisy debug logs.
- Reduce duplicate Sentry events and improve error grouping.
- Review NAT gateway usage and private egress patterns.
- Schedule heavy worker jobs to reduce concurrency spikes.
- Establish tenant-level cost attribution for large customers.
- Improve tagging coverage across legacy AWS resources.

These actions should be executed carefully. The goal is disciplined efficiency, not cutting reliability investment.

## Growth Scenario

If SampleCo grows from $12M ARR to $25M ARR over the next 24 months, cloud spend could grow to $180,000 to $220,000 per month without governance improvements. With stronger cost management and platform modernization, a more reasonable target would be $125,000 to $150,000 per month at that scale.

The biggest variable is enterprise customer behavior. Larger customers may bring heavier integration volume, more uploaded documents, higher reporting frequency, and stronger retention requirements. Pricing should account for these usage patterns. The current packaging model does not fully align price with infrastructure cost drivers.

## Risk Assessment

Cloud cost risk is moderate. The company is not overspending dramatically today, but it has weak cost observability and limited tenant-level economics. This matters because growth equity investors will expect visibility into gross margin expansion and the cost of serving enterprise customers.

The most important risk is database-driven cost growth. If production PostgreSQL continues supporting both operational and analytical workloads, RDS costs and performance risk will increase together. The second risk is observability cost creep. Logging and tracing costs can grow silently if ingestion policies are not actively managed.

## Recommendations

SampleCo should create a lightweight FinOps operating model. This should include monthly cloud cost review, owner tagging standards, service-level budget tracking, forecast-to-actual reporting, and architecture review for high-cost changes.

The company should also prioritize data lifecycle management. Retention policies should be defined for temporary exports, customer uploads, integration logs, product usage events, and analytics artifacts. This is both a cost control and governance requirement.

Finally, SampleCo should add tenant-level cost attribution. Even approximate cost allocation would help product leadership understand whether large customers and advanced integrations are priced correctly.

## Overall Assessment

SampleCo's cloud economics are acceptable for its current stage, but cloud governance needs to mature before enterprise expansion. A disciplined 6-month optimization program could improve gross margin, reduce operational risk, and give investors more confidence in the scalability of the business model.
