from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import SessionLocal


router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    database_status = "ok"

    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        database_status = "unavailable"

    return {
        "status": "ok",
        "database": database_status,
    }
