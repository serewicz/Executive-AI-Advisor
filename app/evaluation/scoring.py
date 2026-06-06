import re
from typing import Any

from app.evaluation.schemas import EvaluationQuestion, EvaluationResult


EXECUTIVE_TERMS = {
    "risk",
    "risks",
    "action",
    "actions",
    "recommend",
    "recommendation",
    "recommendations",
    "board",
    "monitor",
    "governance",
    "control",
    "controls",
    "confidence",
    "limitation",
    "limitations",
}
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "of",
    "or",
    "the",
    "to",
    "what",
}


def score_advisor_response(
    question: EvaluationQuestion,
    answer: str,
    citations: list[dict[str, Any]],
    limitations: list[str] | None = None,
) -> EvaluationResult:
    normalized_answer = " ".join(answer.split())
    citation_score = score_citations(normalized_answer, citations)
    groundedness_score = score_groundedness(normalized_answer, citations, limitations or [])
    relevance_score = score_relevance(question, normalized_answer, citations)
    executive_usefulness_score = score_executive_usefulness(normalized_answer, limitations or [])
    overall_score = round(
        (citation_score + groundedness_score + relevance_score + executive_usefulness_score) / 4,
        3,
    )

    return EvaluationResult(
        question=question.question,
        answer=answer,
        citations=citations,
        citation_score=citation_score,
        groundedness_score=groundedness_score,
        relevance_score=relevance_score,
        executive_usefulness_score=executive_usefulness_score,
        overall_score=overall_score,
        notes=_build_notes(citation_score, groundedness_score, relevance_score, executive_usefulness_score),
    )


def score_citations(answer: str, citations: list[dict[str, Any]]) -> float:
    if not citations:
        return 0.0

    labels = [
        str(citation.get("source_label") or f"S{index}")
        for index, citation in enumerate(citations, start=1)
    ]
    if any(f"[{label}]" in answer or label in answer for label in labels):
        return 1.0
    return 0.5


def score_groundedness(answer: str, citations: list[dict[str, Any]], limitations: list[str]) -> float:
    if not answer.strip():
        return 0.0
    if citations and limitations:
        return 1.0
    if citations:
        return 0.7
    return 0.3


def score_relevance(question: EvaluationQuestion, answer: str, citations: list[dict[str, Any]]) -> float:
    context = " ".join(str(citation.get("excerpt", "")) for citation in citations)
    expected_themes = " ".join(question.expected_themes or [])
    expected_tokens = _keywords(f"{question.question} {expected_themes}")
    observed_tokens = _keywords(f"{answer} {context}")

    if not expected_tokens or not observed_tokens:
        return 0.0

    overlap = expected_tokens & observed_tokens
    return round(min(1.0, len(overlap) / len(expected_tokens)), 3)


def score_executive_usefulness(answer: str, limitations: list[str]) -> float:
    tokens = _keywords(answer)
    matched_terms = tokens & EXECUTIVE_TERMS
    score = min(0.8, len(matched_terms) * 0.16)
    if limitations:
        score += 0.2
    return round(min(1.0, score), 3)


def _keywords(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower())
        if token not in STOP_WORDS
    }


def _build_notes(
    citation_score: float,
    groundedness_score: float,
    relevance_score: float,
    executive_usefulness_score: float,
) -> list[str]:
    notes = []
    if citation_score < 1.0:
        notes.append("Citation quality could be improved.")
    if groundedness_score < 0.7:
        notes.append("Grounding appears weak or unsupported.")
    if relevance_score < 0.5:
        notes.append("Answer has limited keyword overlap with the question or expected themes.")
    if executive_usefulness_score < 0.5:
        notes.append("Answer could be more useful for executive decision-making.")
    if not notes:
        notes.append("Answer is cited, grounded, relevant, and executive-oriented.")
    return notes
