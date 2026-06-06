from app.advisor.providers.base import SourceContext
from app.diligence.schemas import AssessmentType


DILIGENCE_SYSTEM_PROMPT = """You are Executive AI Advisor performing technology due diligence.
Use only the supplied sources.
Do not speculate.
Cite every material claim with labels like [S1].
Assess business impact for executives and investors.
Return structured sections: executive summary, score, findings, risks, recommendations, confidence, and limitations.
Do not provide legal, financial, investment, or regulatory advice."""


ASSESSMENT_QUERIES: dict[AssessmentType, str] = {
    "architecture": "technology architecture scalability reliability cloud infrastructure platform integration legacy systems",
    "security": "cybersecurity security controls access management incidents compliance vulnerability third party risk",
    "technical_debt": "technical debt legacy code maintainability reliability defects platform modernization engineering velocity",
    "key_person_risk": "key person risk dependency knowledge concentration staffing leadership engineering operations continuity",
    "ai_readiness": "AI readiness data governance model risk infrastructure controls machine learning analytics automation",
}


ASSESSMENT_FOCUS: dict[AssessmentType, str] = {
    "architecture": "architecture scalability, resilience, integration complexity, and platform maturity",
    "security": "security governance, controls, access management, vulnerabilities, and third-party exposure",
    "technical_debt": "technical debt, maintainability, modernization needs, and delivery risk",
    "key_person_risk": "knowledge concentration, staffing dependencies, leadership continuity, and operational resilience",
    "ai_readiness": "data maturity, AI governance, infrastructure readiness, model risk, and operational adoption",
}


def build_diligence_prompt(assessment_type: AssessmentType, sources: list[SourceContext]) -> str:
    return "\n\n".join(
        [
            f"Assessment type:\n{assessment_type}",
            f"Assessment focus:\n{ASSESSMENT_FOCUS[assessment_type]}",
            "Sources:\n" + _format_sources(sources),
            (
                "Response requirements:\n"
                "- Use only the sources above.\n"
                "- Cite material claims with source labels like [S1].\n"
                "- Score from 1 to 5 where 5 is strongest diligence posture.\n"
                "- Separate findings, risks, and recommendations.\n"
                "- State confidence and limitations.\n"
                "- Return structured JSON only."
            ),
        ]
    )


def _format_sources(sources: list[SourceContext]) -> str:
    if not sources:
        return "No sources were retrieved."

    return "\n\n".join(
        (
            f"{source.label} {source.document_title} "
            f"(pages {source.page_start}-{source.page_end})\n"
            f"{source.content}"
        )
        for source in sources
    )
