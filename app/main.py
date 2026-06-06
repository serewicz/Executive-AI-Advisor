from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
    )

    @app.get("/")
    def root():
        return {
            "name": settings.app_name,
            "status": "ok",
            "api_docs": "/docs",
            "health": "/health",
            "streamlit_ui": "Run `streamlit run ui/streamlit_app.py` and open http://localhost:8501",
        }

    app.include_router(api_router)
    return app


app = create_app()
