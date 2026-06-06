import re

from app.diligence.schemas import AssessmentType, Confidence
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


def _combined_text(results: list[SearchResult]) -> str:
    return " ".join(result.content for result in results)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower()))
