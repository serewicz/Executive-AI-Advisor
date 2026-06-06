# SampleCo Technology Assessment

Synthetic diligence document. SampleCo is a fictional company created for Executive AI Advisor testing and demonstration.

## Scope and Context

This assessment reviews SampleCo's product architecture, infrastructure, data platform, software delivery practices, technical debt, resilience, and scalability readiness. SampleCo is a $12M ARR B2B SaaS company with 75 employees and a 12-person engineering team. The company is preparing for growth equity investment and expects to move from mid-market customers toward larger enterprise accounts over the next 18 to 24 months.

The technology platform has supported current growth, but it was built under the practical constraints of a lean engineering organization. The resulting architecture is serviceable and commercially useful, but it includes areas of accumulated complexity that will become more visible as transaction volume, customer data volume, compliance expectations, and integration load increase.

## Architecture Overview

The product is a multi-tenant SaaS application hosted on AWS. The customer-facing web application is built in React and TypeScript. The primary API layer is Python FastAPI, with a legacy Django administration application still used for billing support, tenant configuration, internal customer operations, and several back-office workflows. PostgreSQL on Amazon RDS is the system of record. Redis on ElastiCache is used for caching, background job coordination, and rate limiting. S3 stores uploaded documents, customer export files, and long-retention event archives.

Application services are deployed to Amazon ECS Fargate. CI/CD runs through GitHub Actions and deploys container images through AWS Elastic Container Registry. The environment model includes development, staging, and production accounts, though some IAM roles and deployment permissions overlap more than ideal. Infrastructure is mostly defined in Terraform, but several legacy resources were created manually and have not been fully imported into infrastructure as code.

Asynchronous processing is handled through a combination of Celery workers, scheduled ECS tasks, and several older cron-style jobs. These jobs support Salesforce and Zendesk synchronization, product usage rollups, renewal risk calculations, and nightly reporting refreshes. The worker model is functional but unevenly observable. Some jobs emit structured logs and metrics, while older jobs rely on log inspection and Slack alerts.

## Data Architecture

PostgreSQL contains tenant configuration, users, accounts, opportunities, tasks, health scores, notes, integration metadata, and summarized product usage. The schema has grown organically. The core account and workspace tables are well understood, but several integration tables contain mixed semantics and fields used differently by different customers.

SampleCo stores large customer files and exports in S3. Access is mediated by signed URLs generated through the application. Lifecycle rules exist for temporary exports, but customer-uploaded documents and historical event archives have inconsistent retention rules. The company has not yet implemented a complete data classification scheme across database fields, S3 prefixes, logs, and analytics exports.

Analytics are currently produced through scheduled jobs that write denormalized reporting tables back into PostgreSQL. Leadership has discussed introducing a warehouse, likely Snowflake or Redshift, but no formal migration has started. This creates pressure on the production database because operational and analytical workloads are not fully separated.

## Scalability Assessment

The platform should support the next stage of growth with targeted investment. There is no immediate indication that the core application will hit a hard scalability wall. The main risk is that growth will amplify operational friction in integrations, reporting, and tenant-level performance variability.

The current RDS instance has headroom during normal operating periods, but nightly reporting jobs and large integration syncs create spikes in CPU and query latency. Some customer-facing pages depend on complex joins across account, task, usage, and integration tables. Indexing has improved over the last two quarters, but query review is reactive rather than systematic.

The integration framework is the largest scaling concern. Salesforce and Zendesk connectors are business-critical, but retry behavior, backoff strategy, and customer-specific error handling are inconsistent. A small number of large tenants can generate disproportionately high sync volume. Engineering has introduced per-tenant rate limits, but the limits are not visible to customer success teams and are not always reflected in customer communications.

## Reliability and Operations

SampleCo reports approximately 99.8 percent availability over the last six months. The most common incidents are degraded integration syncs, delayed reporting refreshes, and intermittent dashboard latency. There have been no known data loss incidents, but post-incident documentation is inconsistent.

Production monitoring uses Datadog for infrastructure and application metrics, Sentry for frontend and backend exceptions, and CloudWatch for AWS service logs. Dashboards exist for API latency, error rate, database CPU, queue depth, and worker failures. However, runbooks are incomplete and many alerts route to the VP Engineering before being triaged by service owners.

Backup practices are reasonable for the current stage. RDS automated backups are retained for 14 days, point-in-time recovery is enabled, and S3 versioning is enabled for several critical buckets. Disaster recovery has not been formally tested end to end. The recovery time objective is informally stated as less than 8 hours, but there is no board-approved recovery objective or tested recovery plan.

## Software Delivery

Engineering releases production changes two to four times per week. Pull requests require review, and critical paths run automated unit tests in GitHub Actions. The strongest test coverage is in the FastAPI service layer and selected business logic modules. The weakest coverage is in the legacy Django admin, frontend regression tests, and integration sync edge cases.

The team uses feature flags for selected customer-facing features, but feature flag hygiene is inconsistent. Several flags are long-lived and not clearly owned. Release notes are written for customer-facing changes, while internal platform changes are tracked in Jira and Slack.

Deployment rollback is possible by redeploying the previous container image, but database migrations can complicate rollback. Migration review is not yet formalized, and long-running migrations have caused operational concern in the past. A more disciplined migration process will be important as the database grows.

## Technical Debt

Technical debt is moderate and manageable if addressed intentionally. The highest-priority debt areas are:

- Legacy Django administrative workflows that duplicate logic now handled by FastAPI services.
- Integration sync framework with inconsistent retry and failure semantics.
- Reporting jobs that mix operational processing and analytics.
- Test coverage gaps in frontend workflows and customer-specific integration paths.
- Incomplete infrastructure-as-code coverage for older AWS resources.
- Manual operational knowledge concentrated in the VP Engineering and two senior engineers.

This debt does not require a rewrite. It requires service ownership, architecture documentation, selective refactoring, and better operational controls.

## Architecture Risks

The main architecture risk is complexity without formal ownership. The current system has several patterns that were reasonable at the time they were created, but ownership has not kept pace. Some business capabilities live partly in FastAPI, partly in Django, partly in scheduled workers, and partly in SQL rollup tables. This makes onboarding slower and incident response more dependent on senior engineers.

The second risk is tenant isolation at scale. SampleCo uses logical tenant isolation in shared databases. This is common for SaaS platforms, but it requires strong access controls, query discipline, and testing. There is no current evidence of tenant data leakage, but automated tenant isolation tests are limited.

The third risk is data growth. Product usage events, integration logs, customer notes, and uploaded documents are growing faster than ARR. Data lifecycle management needs to mature before large enterprise customers materially increase volume.

## Recommendations

SampleCo should prioritize architecture documentation, integration reliability, database performance management, and service ownership. The first 100 days after investment should produce an architecture decision record library, production runbooks, a critical service ownership map, and a technical debt register ranked by customer risk and revenue impact.

The company should separate operational and analytical workloads over time. A warehouse or lakehouse architecture would reduce production database pressure and support future AI and analytics use cases. This should be sequenced after immediate security and operational maturity work, not treated as an urgent rewrite.

SampleCo should formalize migration review, improve automated regression coverage, and complete infrastructure-as-code coverage for legacy resources. These improvements would reduce deployment risk and support enterprise customer due diligence.

## Overall Assessment

SampleCo's technology foundation is commercially viable and suitable for continued growth, but it is not yet enterprise-mature. Architecture risk is moderate. The company should be able to scale through the next ARR stage if it invests in platform maturity, security governance, and distributed technical leadership.
