from collections.abc import Iterable

from app.advisor.schemas import Confidence
from app.compliance.cra_schemas import CRAReadinessCategory
from app.diligence.schemas import RiskRating
from app.retrieval.vector_search import SearchResult


MISSING_EVIDENCE_BY_CATEGORY: dict[CRAReadinessCategory, list[str]] = {
    "scope": ["EU market analysis", "product classification assessment", "product scope documentation"],
    "secure_by_design": ["secure development lifecycle policy", "threat model", "security requirements"],
    "vulnerability_management": [
        "vulnerability disclosure policy",
        "remediation SLA",
        "exploited vulnerability process",
    ],
    "sbom": ["SBOM policy", "latest SBOM", "dependency inventory", "EOL dependency tracking"],
    "security_updates": ["release/patch process", "support and update policy", "rollback process"],
    "incident_reporting": ["incident reporting runbook", "ENISA/CSIRT reporting process", "escalation path"],
    "technical_documentation": [
        "product security documentation",
        "security design documentation",
        "risk assessment",
        "conformity evidence",
    ],
    "supplier_risk": ["supplier security review", "third-party component inventory", "contractual security obligations"],
    "user_transparency": [
        "secure configuration guidance",
        "vulnerability disclosure channel",
        "update instructions",
    ],
    "lifecycle_support": ["support period policy", "maintenance policy", "end-of-life process"],
}


KEYWORDS_BY_CATEGORY: dict[CRAReadinessCategory, set[str]] = {
    "scope": {"eu", "market", "product", "digital elements", "classification", "customer geography"},
    "secure_by_design": {"secure development", "sdlc", "threat model", "secure defaults", "least privilege", "hardening"},
    "vulnerability_management": {"vulnerability", "cve", "scanning", "remediation", "disclosure", "exploited"},
    "sbom": {"sbom", "software bill of materials", "dependency inventory", "open source", "eol"},
    "security_updates": {"security update", "patch", "release notes", "rollback", "customer notification", "support window"},
    "incident_reporting": {"incident response", "severe incident", "enisa", "csirt", "24-hour", "escalation"},
    "technical_documentation": {"technical documentation", "architecture", "security design", "risk assessment", "conformity"},
    "supplier_risk": {"supplier", "vendor", "third party", "cloud provider", "payment provider", "open source"},
    "user_transparency": {"secure configuration", "known limitations", "support policy", "vulnerability disclosure", "update instructions"},
    "lifecycle_support": {"maintenance", "support lifecycle", "end of life", "security patching", "sunset"},
}

WEAKNESS_TERMS = {
    "absent",
    "missing",
    "manual",
    "ad hoc",
    "incomplete",
    "undefined",
    "unowned",
    "no formal",
    "not documented",
    "immature",
}
MATURITY_TERMS = {
    "defined",
    "documented",
    "repeatable",
    "policy",
    "runbook",
    "sla",
    "review",
    "automated",
    "tested",
    "owned",
}


def readiness_for_category(category: CRAReadinessCategory, results: list[SearchResult]) -> RiskRating:
    if not results:
        return "red"

    text = _combined_text(results)
    keyword_hits = _keyword_hits(category, text)
    weakness_hits = sum(1 for term in WEAKNESS_TERMS if term in text)
    maturity_hits = sum(1 for term in MATURITY_TERMS if term in text)

    if category == "sbom" and not any(term in text for term in {"sbom", "software bill of materials", "dependency inventory"}):
        return "red"
    if category == "vulnerability_management" and not any(term in text for term in {"vulnerability", "cve", "disclosure"}):
        return "red"
    if weakness_hits >= 2 and maturity_hits == 0:
        return "red"
    if keyword_hits >= 3 and maturity_hits >= 2 and weakness_hits == 0:
        return "green"
    return "yellow"


def confidence_for_cra_results(results: list[SearchResult]) -> Confidence:
    if len(results) >= 3 or len({result.document_id for result in results}) >= 2:
        return "high"
    if len(results) >= 1:
        return "medium"
    return "low"


def missing_evidence_for_category(
    category: CRAReadinessCategory,
    results: list[SearchResult],
) -> list[str]:
    text = _combined_text(results)
    missing = []
    for evidence in MISSING_EVIDENCE_BY_CATEGORY[category]:
        evidence_terms = {term for term in evidence.lower().replace("/", " ").split() if len(term) > 3}
        if not any(term in text for term in evidence_terms):
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


def _keyword_hits(category: CRAReadinessCategory, text: str) -> int:
    return sum(1 for term in KEYWORDS_BY_CATEGORY[category] if term in text)
