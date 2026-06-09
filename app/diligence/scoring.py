import re

from app.diligence.schemas import AssessmentType, Confidence, RiskRating, TechnologyReportCategory
from app.retrieval.vector_search import SearchResult


POSITIVE_TERMS: dict[AssessmentType, set[str]] = {
    "architecture": {"scalable", "resilient", "modern", "modular", "reliable", "cloud", "automated"},
    "security": {"controls", "encryption", "monitoring", "mfa", "compliance", "governance", "incident"},
    "technical_debt": {"modernization", "maintainable", "tests", "automation", "roadmap", "refactor"},
    "key_person_risk": {"documentation", "cross-training", "succession", "team", "process", "handoff"},
    "ai_readiness": {"governance", "data", "controls", "monitoring", "infrastructure", "model", "readiness"},
}

RISK_TERMS: dict[AssessmentType, set[str]] = {
    "architecture": {"legacy", "outage", "fragile", "manual", "single", "monolith", "bottleneck"},
    "security": {"breach", "vulnerability", "incident", "weak", "unauthorized", "exposure", "risk"},
    "technical_debt": {"debt", "legacy", "obsolete", "defect", "manual", "fragile", "delay"},
    "key_person_risk": {"single", "key", "dependency", "concentration", "tribal", "attrition", "vacancy"},
    "ai_readiness": {"unstructured", "silo", "quality", "privacy", "bias", "manual", "immature"},
}

TECHNOLOGY_REPORT_RISK_TERMS: dict[TechnologyReportCategory, set[str]] = {
    "architecture": {"legacy", "fragile", "outage", "scalability", "dependency", "manual", "bottleneck"},
    "security": {"incomplete", "weak", "vulnerability", "incident", "access", "governance", "compliance"},
    "technical_debt": {"debt", "legacy", "manual", "testing", "documentation", "maintainability", "defect"},
    "engineering_org": {"hiring", "ownership", "accountability", "gap", "capacity", "process", "delivery"},
    "key_person_risk": {"key", "dependency", "concentration", "single", "succession", "founder", "vp engineering"},
    "ai_readiness": {"governance", "data", "privacy", "model", "quality", "readiness", "risk"},
    "cloud_cost": {"cost", "spend", "aws", "optimization", "tagging", "allocation", "growth"},
    "integration_readiness": {"integration", "migration", "identity", "handoff", "roadmap", "interruption", "support"},
}

MATERIAL_IMPACT_TERMS = {
    "security",
    "incident",
    "customer",
    "revenue",
    "compliance",
    "availability",
    "outage",
    "cost",
    "manual",
    "dependency",
    "growth",
    "enterprise",
}


def score_assessment(assessment_type: AssessmentType, results: list[SearchResult]) -> int:
    text = _combined_text(results)
    if not text:
        return 1

    positive_hits = len(_tokens(text) & POSITIVE_TERMS[assessment_type])
    risk_hits = len(_tokens(text) & RISK_TERMS[assessment_type])
    score = 3 + min(2, positive_hits // 2) - min(2, risk_hits // 2)
    return max(1, min(5, score))


def confidence_for_results(results: list[SearchResult]) -> Confidence:
    if len(results) >= 5:
        return "medium"
    if len(results) >= 2:
        return "medium"
    return "low"


def risk_rating_for_category(
    category: TechnologyReportCategory,
    results: list[SearchResult],
) -> RiskRating:
    if not results:
        return "green"

    text = _combined_text(results)
    tokens = _tokens(text)
    category_hits = len(tokens & TECHNOLOGY_REPORT_RISK_TERMS[category])
    impact_hits = len(tokens & MATERIAL_IMPACT_TERMS)

    if len(results) >= 3 and category_hits >= 3 and impact_hits >= 2:
        return "red"
    if len(results) >= 1 and (category_hits >= 1 or impact_hits >= 1):
        return "yellow"
    return "green"


def confidence_for_technology_results(results: list[SearchResult]) -> Confidence:
    document_count = len({result.document_id for result in results})
    if len(results) >= 4 and document_count >= 2:
        return "high"
    if len(results) >= 2:
        return "medium"
    return "low"


def overall_risk_rating(ratings: list[RiskRating]) -> RiskRating:
    if "red" in ratings:
        return "red"
    if "yellow" in ratings:
        return "yellow"
    return "green"


def overall_confidence(confidences: list[Confidence]) -> Confidence:
    if confidences.count("high") >= 2:
        return "high"
    if "medium" in confidences or "high" in confidences:
        return "medium"
    return "low"


def _combined_text(results: list[SearchResult]) -> str:
    return " ".join(result.content for result in results)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower()))
