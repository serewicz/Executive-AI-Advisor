# AcquisitionTargetCo Executive Summary

Synthetic demo document for Executive AI Advisor. Not based on any real company.

## Business Context

AcquisitionTargetCo is an $8M ARR founder-led vertical B2B SaaS company serving a specialized operational workflow market. The product is profitable, customers value it, and retention is high because the application supports daily work that customers do not want to disrupt. The company has 48 employees, including a 6-person engineering team.

The business is being evaluated as a potential acquisition target for a PE-backed platform company. The acquisition thesis is based on strong retention, a niche customer base, cross-sell opportunity, and operating leverage. Technology diligence should focus less on whether the product is useful and more on whether the architecture, team, and operating model can be safely integrated and scaled.

## Technology Summary

The core application is a monolithic Django system hosted on AWS EC2. PostgreSQL runs on Amazon RDS with limited read-replica usage. S3 stores customer attachments, exports, and report files. Legacy cron jobs support reporting, invoice exports, nightly notifications, and customer data syncs.

The architecture has served the business well, but it is aging. Deployment is manual and founder-approved. There is no formal architecture decision record process. Automated test coverage is minimal. Documentation is incomplete. Backups exist, but restore testing is not recent.

## Investment View

AcquisitionTargetCo is a viable acquisition candidate if the buyer prices and plans for remediation. The product has customer value and profitability, but technology risk is moderate to high due to key-person dependency, informal security ownership, limited documentation, and manual operations.

The target should not be viewed as a plug-and-play platform asset. It should be viewed as a stable niche product that requires a structured post-close technology stabilization plan.

## Key Strengths

- Product is profitable and valued by customers.
- High customer retention indicates workflow importance.
- Django monolith is understandable and not overengineered.
- AWS footprint is relatively simple.
- Engineering team is capable and pragmatic.
- Cloud spend is stable.

## Key Risks

The largest risk is key-person dependency. One founder and one senior engineer hold most operational knowledge, including deployment, database recovery, major customer configuration, and legacy job behavior. If either person became unavailable, the company would struggle with complex incidents and integration planning.

The second risk is operational maturity. Deployment is manual, founder-approved, and not supported by a mature rollback process. Documentation is incomplete, backups have not been recently restore-tested, and legacy cron jobs are not fully observable.

The third risk is security basics. Security ownership is informal. MFA is enabled for most systems but not all administrative tools. There is no formal vulnerability management process. Customer data is duplicated into staging with weak masking.

## Board-Level Monitoring Priorities

- Key-person risk reduction.
- Security basics and vulnerability management.
- Deployment reliability and rollback.
- Documentation and architecture decision records.
- Backup restore testing.
- Customer data masking in staging.
- M&A integration readiness.

## First 100 Days Post-Close

The acquirer should protect customer stability first. Immediate work should include access review, MFA completion, staging data masking, backup restore testing, deployment documentation, inventory of cron jobs, and knowledge transfer from the founder and senior engineer.

The buyer should avoid starting a broad rewrite in the first 100 days. The better move is stabilization, documentation, security remediation, and integration planning.

## Overall Assessment

AcquisitionTargetCo is commercially attractive but operationally fragile. It can be integrated successfully if the buyer recognizes that the value creation plan must include hands-on technology remediation. The product is durable; the operating model is the risk.

## Diligence Evidence To Review

The buyer should request deployment notes, database schema documentation, backup settings, support escalation history, customer-specific configuration lists, administrative access lists, and the latest customer retention analysis. The most useful diligence conversations will be with the founder, senior engineer, support lead, and customer success lead because the product's value is embedded in operational knowledge.

Management should be asked to demonstrate a release, explain how a failed cron job is detected, walk through a database restore, and identify the top customer-specific customizations. These sessions will quickly reveal whether the business can be operated without founder intervention.

The acquisition thesis should include a protected stabilization budget. Without it, the acquirer may inherit a profitable product but struggle to integrate, secure, or modernize it without disrupting customers.
