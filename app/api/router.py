from fastapi import APIRouter

from app.api.routes.advisor import router as advisor_router
from app.api.routes.diligence import router as diligence_router
from app.api.routes.document_sets import router as document_sets_router
from app.api.routes.documents import router as documents_router
from app.api.routes.evaluation import router as evaluation_router
from app.api.routes.health import router as health_router
from app.api.routes.search import router as search_router


api_router = APIRouter()
api_router.include_router(advisor_router)
api_router.include_router(diligence_router)
api_router.include_router(document_sets_router)
api_router.include_router(documents_router)
api_router.include_router(evaluation_router)
api_router.include_router(health_router)
api_router.include_router(search_router)
