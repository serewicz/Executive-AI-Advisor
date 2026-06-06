from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.diligence.schemas import DiligenceAnalyzeRequest, DiligenceAssessmentResponse
from app.diligence.service import (
    DiligenceDocumentNotFoundError,
    DiligenceValidationError,
    analyze_document,
)


router = APIRouter(prefix="/diligence", tags=["diligence"])


@router.post("/analyze", response_model=DiligenceAssessmentResponse)
def analyze_diligence(
    request: DiligenceAnalyzeRequest,
    db: Session = Depends(get_db),
) -> DiligenceAssessmentResponse:
    try:
        return analyze_document(
            document_id=request.document_id,
            assessment_type=request.assessment_type,
            top_k=request.top_k,
            db=db,
        )
    except DiligenceDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DiligenceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
