from app.advisor.providers.base import SourceContext


CRA_READINESS_SYSTEM_PROMPT = """You are preparing a board-level Cyber Resilience Act readiness assessment.

Use only provided context. Do not speculate beyond evidence. Distinguish observed evidence from missing evidence.
Cite material claims with [S1], [S2], and similar source labels. Include business impact, recommended owner,
limitations, and a clear statement that this is not legal advice. Call out September 2026 reporting readiness
and December 2027 full-readiness planning as planning milestones without overclaiming legal obligations."""


def build_cra_readiness_prompt(sources: list[SourceContext]) -> str:
    source_text = "\n\n".join(
        (
            f"{source.label} {source.document_title}, pages {source.page_start}-{source.page_end}\n"
            f"{source.content}"
        )
        for source in sources
    )
    return (
        "Prepare a concise CRA readiness assessment using only these sources. "
        "Return JSON with keys: executive_summary, top_gaps, management_questions, "
        "board_discussion_points, recommended_actions, limitations.\n\n"
        f"Sources:\n{source_text}"
    )
