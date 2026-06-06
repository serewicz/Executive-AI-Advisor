# SampleCo AI Readiness Assessment

Synthetic diligence document. SampleCo is a fictional company created for Executive AI Advisor testing and demonstration.

## Executive Summary

SampleCo has meaningful AI opportunity but low formal AI readiness. The company has valuable customer operations data, a product workflow where summarization and decision support could create customer value, and a leadership team interested in AI-enabled features. However, SampleCo has no formal AI governance program, no approved model inventory, no data handling policy specific to AI, no evaluation process for AI outputs, and no documented customer disclosure framework.

The most likely near-term AI use cases are account summary generation, renewal risk explanations, executive briefing notes, support escalation summarization, and customer success playbook recommendations. These use cases are commercially plausible and aligned with SampleCo's product strategy. They also involve confidential customer data, which creates governance and trust requirements.

SampleCo should not launch customer-facing AI features until it has implemented a basic AI governance framework. The company can safely continue internal prototyping if it restricts sensitive data, uses approved tools, and logs experiments.

## Current AI Usage

AI usage today is informal. Engineers use coding assistants for development productivity. Product managers use generative AI tools to draft requirements, summarize customer interviews, and create release note drafts. Sales and customer success teams use AI to draft emails, account plans, and meeting summaries. These workflows are common and not inherently problematic, but they are not governed consistently.

There is no central record of which AI tools are approved, which data types may be used, or whether customer confidential information can be entered into third-party systems. Employees have received general security reminders but no AI-specific policy. The company has not completed a vendor review for AI tools beyond standard procurement review for one enterprise productivity suite.

Engineering has built two internal prototypes. The first generates customer account summaries from account notes, renewal dates, support tickets, and usage trends. The second drafts renewal risk explanations for customer success managers. Both prototypes are promising, but they have not been evaluated for accuracy, data leakage, hallucination risk, bias, or customer disclosure requirements.

## Data Foundation

SampleCo has useful data for AI-enabled workflows. Core data includes account attributes, stakeholders, contract dates, usage events, support tickets, product adoption milestones, customer success notes, tasks, renewal forecasts, and integration metadata. Much of this data is structured enough to support retrieval and summarization.

The challenge is governance and quality. Data definitions are inconsistent across integration sources. Some customer notes are free-form and may include sensitive commercial context. Product usage event names are not fully standardized. Historical integration mappings vary by customer. Customer-uploaded documents are not consistently classified, retained, or tagged.

The company does not yet maintain a formal data catalog. There is no standard classification of fields by sensitivity, no AI-specific data retention policy, and no customer-level configuration for AI feature enablement. Without these controls, AI features could create trust risk even if the underlying models perform well.

## AI Use Case Assessment

The strongest near-term AI use case is executive account summary generation. This would summarize recent support issues, product adoption, stakeholder changes, upcoming renewal dates, and recommended next actions. The value is clear because customer success managers currently prepare these summaries manually.

The second strongest use case is renewal risk explanation. SampleCo already calculates health scores using rules and usage patterns. AI could explain why an account is flagged, cite source events, and suggest follow-up actions. This is useful, but it requires careful grounding and citations because unsupported risk explanations could mislead customer teams.

The third use case is support escalation summarization. AI could summarize open issues and recent support history before executive review meetings. This use case is lower risk if outputs are clearly labeled as drafts and reviewed by humans.

Higher-risk use cases include automated customer communication, autonomous renewal recommendations, pricing guidance, and predictive customer health scoring without explainability. These should not be prioritized until the governance foundation is stronger.

## Governance Gaps

SampleCo has no formal AI governance framework. Specific gaps include:

- No approved AI provider list.
- No prohibited data policy for AI tools.
- No model inventory.
- No prompt and output logging standard.
- No process for testing groundedness, accuracy, or citation quality.
- No defined human review requirement for customer-facing outputs.
- No customer disclosure language for AI-enabled features.
- No vendor risk process specific to model providers.
- No incident response procedure for AI output errors or data exposure.
- No board-level AI risk reporting.

These gaps are significant because SampleCo handles confidential customer information and plans to serve larger enterprise customers.

## Security and Confidentiality Considerations

AI features will likely process customer confidential information. SampleCo should assume that account notes, support tickets, uploaded documents, and renewal forecasts may contain sensitive information. The company should classify this information before allowing it into AI workflows.

For early AI features, SampleCo should use retrieval-grounded generation rather than open-ended generation. The product should retrieve relevant customer records, provide them as bounded context, require citations, and instruct the model not to speculate beyond provided evidence. Outputs should include limitations and confidence indicators.

The company should consider local or private model options for highly sensitive workflows, but it does not need to default to fully local AI for every use case. The decision should be based on data sensitivity, cost, latency, customer requirements, and vendor contractual protections.

## Operating Model

SampleCo should create an AI governance group with representatives from product, engineering, security, legal, customer success, and executive leadership. This does not need to be bureaucratic. A lightweight governance council can approve use cases, review risks, define required controls, and track model inventory.

Each AI-enabled feature should have an owner, intended use statement, allowed data sources, evaluation criteria, fallback behavior, customer disclosure approach, and monitoring plan. Model outputs should be evaluated before release and periodically after release.

For internal employee AI usage, the company should define approved tools, acceptable data, prohibited data, retention expectations, and escalation guidance. Employees should know when they may use AI and when they may not.

## Recommendations

SampleCo should implement an AI readiness plan in three phases.

Phase 1 should establish policy and inventory. Create an AI acceptable use policy, define approved providers, prohibit unapproved customer data entry, document internal prototypes, and assign governance ownership.

Phase 2 should prepare customer-facing AI controls. Build data classification, retrieval-grounding patterns, citation requirements, human review rules, prompt and output logging, and evaluation tests for accuracy and groundedness.

Phase 3 should launch controlled AI features. Start with account summaries and support summaries for internal users, then expand to customer-facing features after customer disclosure, legal review, and monitoring are in place.

## Overall Assessment

SampleCo has a strong business case for AI but a weak governance foundation. AI readiness score would be low to moderate today. The opportunity is real, but the company should sequence governance before broad launch. Done correctly, AI can become a product differentiator and a diligence strength. Done informally, it could become a trust and compliance risk.
