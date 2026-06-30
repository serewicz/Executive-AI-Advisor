from app.advisor.providers.base import SourceContext


AI_KNOWLEDGE_GOVERNANCE_SYSTEM_PROMPT = """You are preparing a board-level AI Knowledge Governance Assessment.

Use executive language. Use only the provided context. Cite material claims with source labels.
Distinguish observed evidence from missing evidence. Explain business impact, recommended owner,
management questions, board discussion points, and limitations.

Do not provide legal advice. Do not overstate SLMs or private models as fully secure. State that
local/private models reduce some leakage risk but still require access controls, monitoring,
testing, evaluation, and governance. Do not state that a company is legally required to report an
AI incident unless the provided sources establish that requirement. Avoid AI hype.

Return concise JSON with keys: executive_summary, top_gaps, management_questions,
board_discussion_points, recommended_actions, limitations.
"""


def build_ai_knowledge_governance_prompt(sources: list[SourceContext]) -> str:
    source_text = "\n\n".join(
        f"{source.label} {source.document_title} pages {source.page_start}-{source.page_end}\n{source.content}"
        for source in sources
    )
    return f"""Assess AI knowledge governance readiness from the evidence below.

Core message:
Not all knowledge belongs in a public LLM. Organizations should classify information before selecting AI architectures.

Evaluate whether the organization has evidence for:
- knowledge classification
- data lake or document repository readiness
- RAG readiness
- enterprise search
- sensitive IP protection
- SLM/private model readiness
- access controls
- auditability
- vendor/provider risk
- cost governance
- employee enablement
- AI incident response, escalation, board reporting, severe incident handling, and post-incident review

Architecture patterns to consider:
- Public knowledge may use external LLMs with policy controls.
- Internal knowledge should use governed RAG over enterprise data where appropriate.
- Sensitive IP should use private model endpoints, local SLMs, or controlled retrieval paths.
- Regulated data needs controlled environments, auditability, access controls, and legal/compliance review.
- OpenSearch or similar enterprise search can help staff find internal knowledge from a governed data lake or document corpus.
- RAG can retrieve relevant context without retraining a model.
- SLMs/private models can reduce leakage risk and cost for many internal workflows, but still require access controls, monitoring, evaluation, and governance.

Sources:
{source_text}
"""
