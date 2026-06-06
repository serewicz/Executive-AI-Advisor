from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.advisor.service import answer_executive_question
from app.evaluation.schemas import EvaluationQuestion, EvaluationResult, EvaluationRunResponse
from app.evaluation.scoring import score_advisor_response
from app.models.document import Document
from app.models.evaluation import EvaluationRun


def run_document_evaluation(
    document_id: UUID,
    questions: list[EvaluationQuestion],
    db: Session,
    evaluation_type: str = "advisor_qa",
) -> EvaluationRunResponse:
    if db.get(Document, document_id) is None:
        raise ValueError("Document not found.")

    results = [_evaluate_question(document_id=document_id, question=question, db=db) for question in questions]
    average_score = _average_score(results)

    evaluation_run = EvaluationRun(
        id=uuid4(),
        document_id=document_id,
        evaluation_type=evaluation_type,
        questions=[question.model_dump(mode="json") for question in questions],
        results=[result.model_dump(mode="json") for result in results],
        average_score=average_score,
    )
    db.add(evaluation_run)
    db.commit()
    db.refresh(evaluation_run)

    return EvaluationRunResponse(
        evaluation_run_id=evaluation_run.id,
        document_id=evaluation_run.document_id,
        evaluation_type=evaluation_run.evaluation_type,
        average_score=evaluation_run.average_score,
        results=results,
    )


def _evaluate_question(document_id: UUID, question: EvaluationQuestion, db: Session) -> EvaluationResult:
    advisor_response = answer_executive_question(
        question=question.question,
        db=db,
        top_k=5,
        document_id=document_id,
    )
    return score_advisor_response(
        question=question,
        answer=advisor_response.answer,
        citations=[citation.model_dump(mode="json") for citation in advisor_response.citations],
        limitations=advisor_response.limitations,
    )


def _average_score(results: list[EvaluationResult]) -> float:
    if not results:
        return 0.0
    return round(sum(result.overall_score for result in results) / len(results), 3)
