# SampleCo Engineering Organization Review

Synthetic diligence document. SampleCo is a fictional company created for Executive AI Advisor testing and demonstration.

## Organization Overview

SampleCo has a 12-person engineering team within a 75-person company. The engineering organization reports to the VP Engineering, who has been with the company for six years and was the original architect of the current AWS environment, core application architecture, integration framework, and release process.

The team consists of three backend engineers, three frontend engineers, two platform engineers, one data engineer, one QA automation engineer, one engineering manager, and one senior full-stack engineer who operates as an informal technical lead across multiple areas. Product management and design sit in a separate product organization but work closely with engineering through quarterly planning and two-week delivery cycles.

The current organization is productive and committed, but it is stretched. The team supports core product development, customer integrations, production operations, security responses, enterprise sales support, and technical due diligence requests. This broad responsibility set is manageable at $12M ARR but will become a bottleneck as SampleCo moves upmarket.

## Leadership and Decision-Making

The VP Engineering is highly credible and deeply knowledgeable. He understands customer needs, system architecture, cloud infrastructure, security questionnaires, major customer escalations, and the historical reasons behind many technical decisions. This creates strong continuity but also a material key-person dependency.

Many important decisions still route through the VP Engineering. Examples include database schema changes, AWS permission changes, incident response, enterprise integration commitments, security questionnaire responses, major customer escalations, and prioritization of technical debt. Senior engineers can execute independently within known areas, but cross-system architecture decisions are not yet distributed.

The engineering manager owns delivery rituals, sprint health, and team coordination. However, the manager does not yet own technical architecture or production operations. Platform ownership is emerging, but the two platform engineers still rely on the VP Engineering for historical context and final decisions on higher-risk infrastructure changes.

## Team Capability

The engineering team is capable and pragmatic. Backend engineers are strong in Python, PostgreSQL, API design, and integration development. Frontend engineers are strong in React, TypeScript, and product workflow implementation. Platform skills are sufficient for current AWS operations, but the team has limited depth in advanced cloud security, infrastructure governance, data platform architecture, and enterprise compliance.

The data engineering function is underbuilt. One data engineer supports reporting tables, usage rollups, customer analytics requests, and early AI data exploration. This creates bottlenecks for analytics, data quality, and future AI readiness. As the company expands, data ownership will need to become a distinct function rather than a shared engineering side responsibility.

QA automation is also underbuilt. The company relies heavily on developer-owned tests and manual verification for customer-critical workflows. The QA automation engineer has created useful smoke tests, but regression coverage remains limited across integrations, permissions, reporting, and document handling.

## Delivery Process

SampleCo operates on two-week planning cycles with quarterly roadmap themes. Product and engineering leadership review customer commitments, revenue-impacting work, platform improvements, and technical debt. The team uses Jira for planning and GitHub for development.

Production releases occur two to four times per week. The release process is relatively efficient, but rollback discipline is uneven when database migrations are involved. Feature flags are used for selected initiatives, although old flags are not consistently removed. Customer-facing launch coordination is strong for major features and weaker for technical improvements.

The biggest delivery challenge is competing priorities. Engineering frequently shifts between roadmap work, integration issues, support escalations, enterprise sales requests, and technical debt. This leads to a pattern where urgent customer-facing work crowds out platform maturity. The company needs more explicit capacity allocation for reliability, security, and architecture improvements.

## Engineering Metrics

SampleCo tracks sprint completion, pull request throughput, incident counts, deployment frequency, support escalation volume, and selected application performance metrics. These metrics are reviewed informally by the VP Engineering and engineering manager. They are not yet packaged into a board-level operating view.

Useful indicators include:

- Deployment frequency: two to four production releases per week.
- Critical incidents: one severity-1 incident in the last twelve months and five severity-2 incidents.
- Mean time to restore: generally less than four hours for application issues, longer for integration data quality issues.
- Pull request review time: usually less than one business day.
- Automated test coverage: strong in selected backend modules, weak in legacy admin and integration edge cases.
- Technical debt allocation: inconsistent, estimated at 10 to 15 percent of engineering capacity.

These metrics indicate a functioning organization, but not one with mature operational instrumentation.

## Key-Person Risk

The VP Engineering is the central key-person risk. He owns the mental model for the platform, the historical context for major tradeoffs, many AWS operational decisions, and the credibility needed to answer complex technical questions from prospects and investors.

Specific dependency areas include:

- Production incident command and escalation.
- AWS architecture and IAM decisions.
- Integration framework history and customer-specific exceptions.
- Security questionnaire responses and compliance narratives.
- Database scaling decisions.
- Architecture roadmap prioritization.
- Vendor and tooling decisions.

The company has not documented enough of this knowledge. If the VP Engineering were unavailable for 30 days, the team could continue shipping basic product work, but would struggle with major incidents, enterprise diligence requests, infrastructure changes, and cross-system architecture decisions.

## Hiring and Scaling Needs

SampleCo should add leadership and specialist capacity after financing. The highest-impact hires are:

- Director or Head of Platform Engineering to own infrastructure, reliability, DevOps, and cloud governance.
- Security and Compliance Lead to drive SOC 2 readiness, vendor risk, policies, and security operations.
- Senior Data Engineer or Analytics Engineering Lead to separate reporting, data quality, and future AI data foundations from product engineering.
- Staff Backend Engineer to own integration architecture and service boundaries.
- Additional QA automation capability for regression, permissions, and integration testing.

These hires should not be framed as overhead. They are required to support enterprise expansion and reduce operational dependency on the VP Engineering.

## Culture and Operating Model

The engineering culture is customer-oriented, practical, and delivery-focused. Engineers understand the product domain and regularly interact with customer success. This is a strength because it keeps technical work tied to commercial outcomes.

The weakness is that the culture sometimes rewards heroic problem-solving over repeatable operating discipline. Senior engineers and the VP Engineering are accustomed to resolving issues quickly through personal knowledge. As the company scales, this needs to shift toward documented ownership, runbooks, service-level objectives, and clearer escalation paths.

The team appears coachable. There is no sign of resistance to process maturity. The likely challenge is capacity, not attitude.

## Recommendations

SampleCo should create a 12-month engineering operating model that explicitly supports growth equity objectives. Recommended actions include:

- Build a service ownership map with named primary and secondary owners.
- Document production architecture, operational runbooks, and incident response procedures.
- Move recurring cloud and deployment decisions from the VP Engineering to platform owners.
- Allocate at least 20 percent of engineering capacity for reliability, security, automation, and technical debt for the next two quarters.
- Create a board-level technology operating dashboard.
- Establish a hiring plan for platform, security, data, and senior architecture capacity.
- Formalize architecture review for high-risk changes.

## Overall Assessment

SampleCo has a capable engineering team that has built a real product with commercial traction. The organization is not broken, but it is dependent on a small number of senior people and has not yet built the operating structure required for enterprise-scale growth. The most important post-investment priority is moving from founder-era knowledge concentration to distributed technical leadership.
