from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.advisor.providers.base import LLMError
from app.db.dependencies import get_db
from app.diligence.service import DiligenceDocumentSetNotFoundError, DiligenceValidationError
from app.executive.schemas import (
    AIGovernanceAssessmentRequest,
    AIGovernanceAssessmentResponse,
    AIReplicabilityRiskAssessmentRequest,
    AIReplicabilityRiskAssessmentResponse,
    BoardBriefRequest,
    BoardBriefResponse,
    ExecutiveHundredDayPlanRequest,
    ExecutiveHundredDayPlanResponse,
    RiskScorecardRequest,
    TechnologyRiskScorecardResponse,
)
from app.executive.service import (
    generate_ai_governance_assessment,
    generate_ai_replicability_risk_assessment,
    generate_board_brief,
    generate_executive_100_day_plan,
    generate_risk_scorecard,
)


router = APIRouter(prefix="/executive", tags=["executive"])


@router.post("/risk-scorecard", response_model=TechnologyRiskScorecardResponse)
def risk_scorecard(
    request: RiskScorecardRequest,
    db: Session = Depends(get_db),
) -> TechnologyRiskScorecardResponse:
    try:
        return generate_risk_scorecard(
            document_set_id=request.document_set_id,
            db=db,
            top_k=request.top_k,
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


@router.post("/board-brief", response_model=BoardBriefResponse)
def board_brief(
    request: BoardBriefRequest,
    db: Session = Depends(get_db),
) -> BoardBriefResponse:
    try:
        return generate_board_brief(
            document_set_id=request.document_set_id,
            db=db,
            top_k=request.top_k,
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


@router.post("/100-day-plan", response_model=ExecutiveHundredDayPlanResponse)
def hundred_day_plan(
    request: ExecutiveHundredDayPlanRequest,
    db: Session = Depends(get_db),
) -> ExecutiveHundredDayPlanResponse:
    try:
        return generate_executive_100_day_plan(
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


@router.post("/ai-governance-assessment", response_model=AIGovernanceAssessmentResponse)
def ai_governance_assessment(
    request: AIGovernanceAssessmentRequest,
    db: Session = Depends(get_db),
) -> AIGovernanceAssessmentResponse:
    try:
        return generate_ai_governance_assessment(
            document_set_id=request.document_set_id,
            db=db,
            top_k=request.top_k,
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


@router.post("/ai-replicability-risk", response_model=AIReplicabilityRiskAssessmentResponse)
def ai_replicability_risk_assessment(
    request: AIReplicabilityRiskAssessmentRequest,
    db: Session = Depends(get_db),
) -> AIReplicabilityRiskAssessmentResponse:
    try:
        return generate_ai_replicability_risk_assessment(
            document_set_id=request.document_set_id,
            db=db,
            top_k=request.top_k,
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
