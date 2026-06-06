from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.evaluation.schemas import EvaluationRunRequest, EvaluationRunResponse
from app.evaluation.service import run_document_evaluation
from app.db.dependencies import get_db


router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("/run", response_model=EvaluationRunResponse)
def run_evaluation(request: EvaluationRunRequest, db: Session = Depends(get_db)) -> EvaluationRunResponse:
    if request.evaluation_type != "advisor_qa":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only advisor_qa evaluation is supported.",
        )

    try:
        return run_document_evaluation(
            document_id=request.document_id,
            questions=request.questions,
            db=db,
            evaluation_type=request.evaluation_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
