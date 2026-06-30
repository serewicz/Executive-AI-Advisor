from collections.abc import Iterable

from app.advisor.schemas import Confidence
from app.diligence.schemas import RiskRating
from app.governance.ai_knowledge_schemas import AIKnowledgeGovernanceCategory
from app.retrieval.vector_search import SearchResult


MISSING_EVIDENCE_BY_CATEGORY: dict[AIKnowledgeGovernanceCategory, list[str]] = {
    "knowledge_classification": [
        "AI usage policy",
        "data classification policy",
        "classification-specific AI handling rules",
        "approved AI tool list",
    ],
    "data_lake_readiness": [
        "data lake architecture",
        "knowledge source inventory",
        "metadata catalog",
        "retention and lifecycle rules",
    ],
    "rag_readiness": [
        "RAG evaluation results",
        "retrieval permissions design",
        "citation/grounding requirements",
        "stale content handling process",
    ],
    "enterprise_search": [
        "OpenSearch or search architecture",
        "permissions-aware search design",
        "internal knowledge discovery workflow",
        "search relevance/auditability approach",
    ],
    "sensitive_ip_protection": [
        "sensitive IP handling policy",
        "prompt/data handling policy",
        "restricted retrieval/model path",
        "redaction or masking process",
    ],
    "slm_private_model_readiness": [
        "local SLM/private model decision record",
        "private model deployment environment",
        "model ownership",
        "model evaluation plan",
    ],
    "access_controls": [
        "RBAC design",
        "document-level access control",
        "identity integration",
        "least privilege access review",
    ],
    "auditability": [
        "audit logging design",
        "prompt/retrieval/output logs",
        "model/provider logging",
        "incident investigation workflow",
    ],
    "vendor_and_provider_risk": [
        "AI provider/vendor review",
        "SaaS AI usage inventory",
        "data retention terms",
        "contractual AI protections",
    ],
    "cost_governance": [
        "AI cost tracking report",
        "token/inference cost controls",
        "budget owner",
        "chargeback/showback model",
    ],
    "employee_enablement": [
        "employee AI training material",
        "approved tool guidance",
        "AI usage policy",
        "shadow AI reduction plan",
    ],
    "ai_incident_response": [
        "AI incident definition",
        "AI incident response runbook",
        "AI escalation path",
        "board notification criteria",
        "post-incident review process",
    ],
}


KEYWORDS_BY_CATEGORY: dict[AIKnowledgeGovernanceCategory, set[str]] = {
    "knowledge_classification": {"classification", "public", "internal", "confidential", "restricted", "regulated", "proprietary"},
    "data_lake_readiness": {"data lake", "document repository", "metadata catalog", "knowledge source", "retention", "ownership"},
    "rag_readiness": {"rag", "retrieval", "vector", "citation", "grounding", "chunking", "embedding", "evaluation"},
    "enterprise_search": {"opensearch", "enterprise search", "internal knowledge search", "permissions search", "discovery"},
    "sensitive_ip_protection": {"sensitive ip", "proprietary", "public llm", "leakage", "prompt policy", "redaction", "masking"},
    "slm_private_model_readiness": {"slm", "small language model", "local model", "private model", "private endpoint", "data residency"},
    "access_controls": {"rbac", "access control", "permissions", "least privilege", "identity", "sso"},
    "auditability": {"audit", "logs", "prompt logs", "retrieved sources", "monitoring", "review trail"},
    "vendor_and_provider_risk": {"llm provider", "vendor risk", "saas ai", "data retention", "contractual", "third party"},
    "cost_governance": {"ai cost", "token cost", "inference cost", "usage", "chargeback", "showback", "budget"},
    "employee_enablement": {"approved ai tools", "training", "usage policy", "shadow ai", "knowledge discovery"},
    "ai_incident_response": {"ai incident", "incident response", "escalation", "board notification", "post-incident", "legal", "compliance"},
}

WEAKNESS_TERMS = {
    "absent",
    "missing",
    "ad hoc",
    "informal",
    "incomplete",
    "undefined",
    "unowned",
    "no formal",
    "not documented",
    "immature",
    "without policy",
    "shadow ai",
}
MATURITY_TERMS = {
    "defined",
    "documented",
    "repeatable",
    "policy",
    "approved",
    "runbook",
    "review",
    "audit",
    "logged",
    "owned",
    "rbac",
    "sso",
}


def readiness_for_category(
    category: AIKnowledgeGovernanceCategory,
    results: list[SearchResult],
) -> RiskRating:
    if not results:
        return "red"

    text = _combined_text(results)
    keyword_hits = _keyword_hits(category, text)
    weakness_hits = sum(1 for term in WEAKNESS_TERMS if term in text)
    maturity_hits = sum(1 for term in MATURITY_TERMS if term in text)

    if category == "knowledge_classification" and not any(
        term in text for term in {"classification", "confidential", "restricted", "regulated", "proprietary"}
    ):
        return "red"
    if category == "auditability" and not any(term in text for term in {"audit", "log", "monitoring", "review trail"}):
        return "red"
    if category == "cost_governance" and not any(term in text for term in {"cost", "token", "inference", "usage", "budget"}):
        return "yellow"
    if category == "ai_incident_response" and not any(
        term in text for term in {"ai incident", "incident response", "escalation", "board notification", "post-incident"}
    ):
        return "red"
    if weakness_hits >= 2 and maturity_hits == 0:
        return "red"
    if keyword_hits >= 3 and maturity_hits >= 2 and weakness_hits == 0:
        return "green"
    return "yellow"


def confidence_for_results(results: list[SearchResult]) -> Confidence:
    if len(results) >= 3 or len({result.document_id for result in results}) >= 2:
        return "high"
    if len(results) >= 1:
        return "medium"
    return "low"


def missing_evidence_for_category(
    category: AIKnowledgeGovernanceCategory,
    results: list[SearchResult],
) -> list[str]:
    text = _combined_text(results)
    missing = []
    for evidence in MISSING_EVIDENCE_BY_CATEGORY[category]:
        if not _has_evidence(text, evidence):
            missing.append(evidence)
    return missing[:4]


def overall_readiness(readiness_values: Iterable[RiskRating]) -> RiskRating:
    values = list(readiness_values)
    if not values:
        return "red"
    if "red" in values:
        return "red"
    if "yellow" in values:
        return "yellow"
    return "green"


def overall_confidence(confidences: Iterable[Confidence]) -> Confidence:
    values = list(confidences)
    if not values:
        return "low"
    if values.count("high") >= max(1, len(values) // 2):
        return "high"
    if "medium" in values or "high" in values:
        return "medium"
    return "low"


def _combined_text(results: list[SearchResult]) -> str:
    return " ".join(result.content.lower() for result in results)


def _keyword_hits(category: AIKnowledgeGovernanceCategory, text: str) -> int:
    return sum(1 for term in KEYWORDS_BY_CATEGORY[category] if term in text)


def _has_evidence(text: str, evidence: str) -> bool:
    phrase = evidence.lower().replace("/", " ").replace("-", " ")
    terms = [term for term in phrase.split() if len(term) > 3]
    if phrase in text:
        return not _has_negative_context(text, phrase)
    if terms and all(term in text for term in terms):
        return not any(_has_negative_context(text, term) for term in terms)
    return False


def _has_negative_context(text: str, term: str) -> bool:
    index = text.find(term)
    if index == -1:
        return False
    context = text[max(0, index - 40) : index + len(term) + 40]
    return any(
        marker in context
        for marker in (
            "no ",
            "not ",
            "without ",
            "missing ",
            "absent ",
            "undefined ",
            "incomplete ",
            "informal ",
        )
    )
