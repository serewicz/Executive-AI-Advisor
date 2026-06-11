from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.advisor.providers.base import LLMError
from app.compliance.cra_schemas import CRAReadinessRequest, CRAReadinessResponse
from app.compliance.cra_service import (
    CRADocumentSetNotFoundError,
    CRAValidationError,
    generate_cra_readiness_assessment,
)
from app.db.dependencies import get_db


router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.post("/cra-readiness", response_model=CRAReadinessResponse)
def generate_cra_readiness(
    request: CRAReadinessRequest,
    db: Session = Depends(get_db),
) -> CRAReadinessResponse:
    try:
        return generate_cra_readiness_assessment(
            document_set_id=request.document_set_id,
            top_k=request.top_k,
            db=db,
            llm_provider=request.llm_provider,
            llm_model=request.llm_model,
            llm_api_key=request.llm_api_key,
        )
    except CRADocumentSetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CRAValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
