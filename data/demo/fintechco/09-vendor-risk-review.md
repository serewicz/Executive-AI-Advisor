# FinTechCo Vendor Risk Review

Synthetic demo document for Executive AI Advisor. Not based on any real company.

## Executive Summary

FinTechCo has material vendor concentration risk around its primary payment processor and KYC provider. These vendors support core customer workflows, and interruption or adverse commercial changes would create operational and revenue risk. The company has vendor review practices, but redundancy planning is incomplete.

Vendor risk is especially important because FinTechCo is preparing for Series C or growth equity investment. Investors and enterprise customers will expect evidence that critical third parties are reviewed, monitored, contractually protected, and included in business continuity planning.

## Critical Vendors

| Vendor Type | Business Role | Risk |
| --- | --- | --- |
| Primary payment processor | Payment execution and transaction status | High concentration and switching complexity. |
| KYC provider | Customer onboarding and identity verification support | High operational dependency. |
| Cloud provider | AWS infrastructure and managed services | Standard cloud concentration, mitigated by managed services. |
| Observability platform | Production monitoring and incident diagnostics | Medium operational dependency. |
| Customer support platform | Support workflow and customer communication | Medium data and continuity risk. |

Vendor names are intentionally fictionalized or generalized in this demo dataset.

## Payment Processor Risk

The payment processor is deeply integrated into transaction workflows, payment status updates, exception handling, and reconciliation events. Kafka topics and workflow services depend on processor event formats. Customer support also relies on processor dashboard access during payment investigations.

There is no near-term active redundancy. The company has discussed secondary processor support, but implementation has not started. Switching would require contract review, API integration, workflow testing, reconciliation changes, support training, and customer communication.

## KYC Provider Risk

The KYC provider supports onboarding checks and risk review workflows. Delays or outages affect new customer onboarding and selected customer operations. The vendor relationship is commercially stable, but operational contingency planning is limited.

KYC data handling should be reviewed as part of AI governance. No AI prototype should use KYC-related data unless explicitly approved by compliance, legal, and security.

## Vendor Governance

FinTechCo reviews critical vendors annually and during procurement. SOC reports and security documentation are collected for major vendors. However, review evidence is not consistently tied to business continuity planning, access review, data retention, or exit strategy.

Vendor portal access is included in some quarterly access reviews but not documented as consistently as AWS and GitHub access. This matters because payment processor and KYC portals provide sensitive operational visibility.

## Business Continuity

Business continuity plans mention vendor outages but lack technical playbooks for payment processor or KYC provider failure. Customer communication templates exist in draft form. There is no recent tabletop exercise covering vendor outage scenarios.

The company should create vendor-specific continuity plans that identify customer impact, technical response, escalation contacts, legal obligations, and workaround options.

## Recommendations

- Define critical vendor tiers and board-level reporting.
- Create payment processor redundancy or exit plan.
- Create KYC provider contingency plan.
- Add vendor portal access to standardized privileged access reviews.
- Link vendor reviews to SOC 2 evidence and business continuity planning.
- Include vendor outage scenarios in incident tabletop exercises.
- Review AI data restrictions for vendor-derived data.

## Overall Assessment

Vendor concentration is one of FinTechCo's clearest board-level risks. The issue is not that the company uses critical vendors. It is that redundancy, exit planning, and evidence are not mature enough for the next stage of regulated growth.

## Diligence Questions For Management

Management should be prepared to answer how long the platform could operate if the payment processor degraded, what customer commitments would be affected by KYC provider downtime, and what contractual remedies exist for vendor outages. The company should also explain whether vendor data can be exported quickly and whether alternate providers have been technically assessed.

The diligence team should request vendor contracts, service-level agreements, SOC reports, support escalation paths, outage history, and exit provisions for the primary payment processor and KYC provider. The team should also review which employees have privileged vendor portal access and whether those permissions are included in quarterly access reviews.

Vendor risk should connect directly to the 100-day plan. If no active redundancy is practical, FinTechCo should still create tested playbooks, executive escalation contacts, customer communication templates, and commercial fallback options.
