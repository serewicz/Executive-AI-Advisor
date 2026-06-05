from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.advisor.providers.base import LLMError
from app.advisor.schemas import AdvisorAskRequest, AdvisorAskResponse, BoardSummaryRequest, BoardSummaryResponse
from app.advisor.service import (
    AdvisorDocumentNotFoundError,
    AdvisorValidationError,
    answer_executive_question,
    generate_board_summary,
)
from app.db.dependencies import get_db


router = APIRouter(prefix="/advisor", tags=["advisor"])


@router.post("/ask", response_model=AdvisorAskResponse)
def ask_advisor(request: AdvisorAskRequest, db: Session = Depends(get_db)) -> AdvisorAskResponse:
    try:
        return answer_executive_question(
            question=request.question,
            db=db,
            top_k=request.top_k,
            source_type=request.source_type,
            classification=request.classification,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/board-summary", response_model=BoardSummaryResponse)
def board_summary(request: BoardSummaryRequest, db: Session = Depends(get_db)) -> BoardSummaryResponse:
    try:
        return generate_board_summary(
            document_id=request.document_id,
            summary_type=request.summary_type,
            top_k=request.top_k,
            db=db,
        )
    except AdvisorDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AdvisorValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
