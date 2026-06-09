from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.advisor.providers.base import LLMError
from app.db.dependencies import get_db
from app.diligence.schemas import (
    DiligenceAnalyzeRequest,
    DiligenceAssessmentResponse,
    TechnologyDiligenceReport,
    TechnologyDiligenceRequest,
)
from app.diligence.service import (
    DiligenceDocumentSetNotFoundError,
    DiligenceDocumentNotFoundError,
    DiligenceValidationError,
    analyze_document,
    generate_technology_due_diligence_report,
)
from app.planning.schemas import HundredDayPlanRequest, HundredDayPlanResponse
from app.planning.service import generate_100_day_plan


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


@router.post("/technology-report", response_model=TechnologyDiligenceReport)
def generate_technology_report(
    request: TechnologyDiligenceRequest,
    db: Session = Depends(get_db),
) -> TechnologyDiligenceReport:
    try:
        return generate_technology_due_diligence_report(
            document_set_id=request.document_set_id,
            top_k=request.top_k,
            include_100_day_plan=request.include_100_day_plan,
            db=db,
            llm_provider=request.llm_provider,
            llm_model=request.llm_model,
            llm_api_key=request.llm_api_key,
        )
    except DiligenceDocumentSetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DiligenceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/100-day-plan", response_model=HundredDayPlanResponse)
def generate_hundred_day_plan(
    request: HundredDayPlanRequest,
    db: Session = Depends(get_db),
) -> HundredDayPlanResponse:
    try:
        return generate_100_day_plan(
            document_set_id=request.document_set_id,
            plan_type=request.plan_type,
            db=db,
            llm_provider=request.llm_provider,
            llm_model=request.llm_model,
            llm_api_key=request.llm_api_key,
        )
    except DiligenceDocumentSetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DiligenceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
