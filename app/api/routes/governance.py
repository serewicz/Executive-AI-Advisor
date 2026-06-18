from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.advisor.providers.base import LLMError
from app.db.dependencies import get_db
from app.governance.ai_knowledge_schemas import (
    AIKnowledgeGovernanceRequest,
    AIKnowledgeGovernanceResponse,
)
from app.governance.ai_knowledge_service import (
    AIKnowledgeGovernanceDocumentSetNotFoundError,
    AIKnowledgeGovernanceValidationError,
    generate_ai_knowledge_governance_assessment,
)


router = APIRouter(prefix="/governance", tags=["governance"])


@router.post("/ai-knowledge", response_model=AIKnowledgeGovernanceResponse)
def generate_ai_knowledge_governance(
    request: AIKnowledgeGovernanceRequest,
    db: Session = Depends(get_db),
) -> AIKnowledgeGovernanceResponse:
    try:
        return generate_ai_knowledge_governance_assessment(
            document_set_id=request.document_set_id,
            top_k=request.top_k,
            db=db,
            llm_provider=request.llm_provider,
            llm_model=request.llm_model,
            llm_api_key=request.llm_api_key,
        )
    except AIKnowledgeGovernanceDocumentSetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AIKnowledgeGovernanceValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
