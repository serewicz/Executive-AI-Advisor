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

RED_EVIDENCE_PATTERNS: dict[TechnologyReportCategory, tuple[str, ...]] = {
    "architecture": (
        "manual production deployment",
        "single point of failure",
        "unplanned outage",
        "fragile architecture",
        "critical platform dependency",
    ),
    "security": (
        "privileged access gap",
        "privileged access gaps",
        "weak data masking",
        "untested backups",
        "unauthorized access",
        "security incident",
    ),
    "technical_debt": (
        "severe technical debt",
        "legacy system blocks",
        "manual release process",
        "untested critical workflow",
    ),
    "engineering_org": (
        "unclear production ownership",
        "no accountable owner",
        "delivery dependency on one person",
    ),
    "key_person_risk": (
        "founder dependency",
        "key-person dependency",
        "key person dependency",
        "vp engineering dependency",
        "knowledge concentration",
        "single engineer",
    ),
    "ai_readiness": (
        "no ai governance",
        "uncontrolled ai use",
        "model risk unmanaged",
        "sensitive data exposure",
    ),
    "cloud_cost": (
        "runaway cloud cost",
        "material cloud cost overrun",
        "unbounded aws spend",
    ),
    "integration_readiness": (
        "integration blocker",
        "identity migration risk",
        "data migration risk",
        "support handoff risk",
    ),
}

YELLOW_EVIDENCE_PATTERNS: dict[TechnologyReportCategory, tuple[str, ...]] = {
    "architecture": (
        "roadmap dependency",
        "platform dependency",
        "partial automation",
        "scalability improvement",
    ),
    "security": (
        "incomplete security governance",
        "incomplete control",
        "partial access review",
        "security governance gap",
    ),
    "technical_debt": (
        "incomplete documentation",
        "technical debt",
        "partial test coverage",
        "manual process",
    ),
    "engineering_org": (
        "unclear ownership",
        "hiring gap",
        "capacity gap",
        "partial accountability",
    ),
    "key_person_risk": (
        "succession planning needed",
        "limited cross-training",
        "knowledge transfer gap",
    ),
    "ai_readiness": (
        "ai governance gap",
        "data governance gap",
        "ai readiness gap",
        "manual ai review",
    ),
    "cloud_cost": (
        "cloud cost visibility gap",
        "cloud cost visibility gaps",
        "tagging gap",
        "limited cost allocation",
        "manual cloud cost management",
    ),
    "integration_readiness": (
        "integration readiness gap",
        "handoff dependency",
        "roadmap dependency",
        "support transition gap",
    ),
}

GREEN_EVIDENCE_PATTERNS: dict[TechnologyReportCategory, tuple[str, ...]] = {
    "architecture": ("documented architecture", "tested process", "strong monitoring", "clear ownership"),
    "security": ("documented controls", "tested backups", "strong monitoring", "mature compliance practice"),
    "technical_debt": ("automated tests", "documented process", "clear remediation plan", "maintainable"),
    "engineering_org": ("clear ownership", "documented roles", "accountable owner", "stable delivery process"),
    "key_person_risk": ("cross-trained team", "succession plan", "documented runbooks", "distributed ownership"),
    "ai_readiness": ("ai governance", "model monitoring", "data governance", "documented ai controls"),
    "cloud_cost": ("cost allocation", "budget alerts", "tagging discipline", "finops owner"),
    "integration_readiness": ("integration plan", "migration runbook", "handoff plan", "clear roadmap"),
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

    text = _combined_text(results).lower()
    red_hits = _matching_patterns(text, RED_EVIDENCE_PATTERNS[category])
    yellow_hits = _matching_patterns(text, YELLOW_EVIDENCE_PATTERNS[category])
    green_hits = _matching_patterns(text, GREEN_EVIDENCE_PATTERNS[category])

    if red_hits:
        return "red"
    if yellow_hits:
        return "yellow"
    if green_hits:
        return "green"

    tokens = _tokens(text)
    category_hits = len(tokens & TECHNOLOGY_REPORT_RISK_TERMS[category])
    if category_hits >= 3 and len(results) >= 2:
        return "yellow"
    return "green"


def confidence_for_technology_results(
    results: list[SearchResult],
    category: TechnologyReportCategory | None = None,
) -> Confidence:
    document_count = len({result.document_id for result in results})
    direct_evidence_count = _direct_evidence_count(results, category)
    if direct_evidence_count >= 3 or (document_count >= 2 and direct_evidence_count >= 2):
        return "high"
    if 1 <= direct_evidence_count <= 2:
        return "medium"
    return "low"


def risk_rationale_for_category(
    category: TechnologyReportCategory,
    results: list[SearchResult],
) -> str:
    if not results:
        return "No retrieved evidence identified a material issue."

    text = _combined_text(results).lower()
    red_hits = _matching_patterns(text, RED_EVIDENCE_PATTERNS[category])
    yellow_hits = _matching_patterns(text, YELLOW_EVIDENCE_PATTERNS[category])
    green_hits = _matching_patterns(text, GREEN_EVIDENCE_PATTERNS[category])
    category_label = category.replace("_", " ")

    if red_hits:
        return f"{_format_patterns(red_hits)} create material {category_label} risk with operational, security, integration, or business impact."
    if yellow_hits:
        return f"{_format_patterns(yellow_hits)} indicate moderate {category_label} risk requiring management validation or remediation."
    if green_hits:
        return f"{_format_patterns(green_hits)} suggest adequate {category_label} controls based on retrieved evidence."
    return f"Retrieved evidence for {category_label} is limited and does not show a major issue."


def confidence_rationale_for_results(
    results: list[SearchResult],
    category: TechnologyReportCategory | None = None,
) -> str:
    if not results:
        return "No relevant citations were retrieved."

    citation_count = len(results)
    document_count = len({result.document_id for result in results})
    direct_evidence_count = _direct_evidence_count(results, category)

    if direct_evidence_count >= 3:
        return f"High confidence because {direct_evidence_count} directly relevant citations support the finding."
    if document_count >= 2 and direct_evidence_count >= 2:
        return f"High confidence because direct evidence appears across {document_count} documents."
    if direct_evidence_count >= 1:
        return f"Medium confidence because {citation_count} citation(s) provide direct evidence."
    return "Low confidence because the retrieved evidence is weak, indirect, or inferred."


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


def _matching_patterns(text: str, patterns: tuple[str, ...]) -> list[str]:
    normalized = " ".join(text.lower().split())
    return [pattern for pattern in patterns if pattern in normalized]


def _direct_evidence_count(
    results: list[SearchResult],
    category: TechnologyReportCategory | None = None,
) -> int:
    patterns = _patterns_for_category(category)
    return sum(1 for result in results if _matching_patterns(result.content, patterns))


def _patterns_for_category(category: TechnologyReportCategory | None) -> tuple[str, ...]:
    if category is not None:
        return (
            *RED_EVIDENCE_PATTERNS[category],
            *YELLOW_EVIDENCE_PATTERNS[category],
            *GREEN_EVIDENCE_PATTERNS[category],
        )
    return (
        *[pattern for patterns in RED_EVIDENCE_PATTERNS.values() for pattern in patterns],
        *[pattern for patterns in YELLOW_EVIDENCE_PATTERNS.values() for pattern in patterns],
        *[pattern for patterns in GREEN_EVIDENCE_PATTERNS.values() for pattern in patterns],
    )


def _format_patterns(patterns: list[str]) -> str:
    formatted = [pattern.replace("-", " ") for pattern in patterns[:2]]
    if len(formatted) == 1:
        return formatted[0].capitalize()
    return f"{formatted[0].capitalize()} and {formatted[1]}"
