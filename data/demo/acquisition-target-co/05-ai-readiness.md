# AcquisitionTargetCo AI Readiness

Synthetic demo document for Executive AI Advisor. Not based on any real company.

## Executive Summary

AcquisitionTargetCo has low AI readiness. The company has potential AI use cases in customer support, workflow summarization, report drafting, and operational analytics, but the data foundation and governance model are not ready for production AI features.

The most important blockers are incomplete documentation, inconsistent data quality, weak staging data controls, lack of AI governance, and limited engineering capacity.

## Current AI Usage

AI usage is informal. Employees use general-purpose AI tools for drafting emails, summarizing notes, and creating support responses. There is no formal AI policy, approved tool list, model inventory, or customer data restriction specific to AI.

The product does not currently include customer-facing AI features. Management has discussed AI-generated workflow summaries and support response drafts but has not funded implementation.

## Data Readiness

The Django application contains valuable domain data, including customer workflows, tasks, comments, attachments, reports, and status history. However, data quality varies by customer. Some fields are overloaded, older records contain inconsistent values, and customer-specific configuration affects interpretation.

Customer data is duplicated into staging with weak masking, which is a major governance gap. Before AI work begins, the company should improve data classification, masking, retention, and access controls.

## Governance Gaps

There is no AI governance process. The company has not defined approved providers, prohibited data, human review requirements, evaluation criteria, customer disclosure, or incident response for AI outputs.

Because the engineering team is small, AI governance should likely be inherited from the acquirer after close rather than built independently.

## Potential Use Cases

| Use Case | Readiness | Notes |
| --- | --- | --- |
| Internal support summarization | Medium | Useful if customer data handling is controlled. |
| Customer workflow summary | Low | Requires data quality and citation controls. |
| Report drafting | Low to medium | Could help operations but needs human review. |
| Acquisition knowledge assistant | Medium | Could help integration if scoped to approved documents. |

## Recommendations

- Do not launch customer-facing AI before integration.
- Apply acquirer AI governance standards after close.
- Classify and mask sensitive data.
- Create model and tool inventory.
- Start with internal support use cases only.
- Require human review and citations for generated outputs.

## Overall Assessment

AI readiness is low. This is not a critical acquisition blocker because AI is not central to current value, but it matters for future product modernization. AI should follow security, documentation, and data governance remediation.

## Post-Close AI Path

The acquirer should treat AI as a later-stage modernization opportunity. The first step is not model selection. The first step is data hygiene: classify sensitive fields, remove production customer data from staging, document workflow semantics, and define which data is safe for retrieval or summarization.

Once data governance improves, the safest use case is an internal support assistant grounded in approved documentation and support history. Customer-facing workflow summaries should wait until the company has citation controls, human review, customer disclosure, and output monitoring.

AI diligence should ask whether employees currently put customer data into public AI tools, whether any support team has adopted unofficial AI workflows, and whether customer contracts restrict automated processing or third-party model providers.
