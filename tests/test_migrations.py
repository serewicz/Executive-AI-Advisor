from pathlib import Path

from app.db.session import Base
from app.db import base as model_imports


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_alembic_env_uses_project_metadata():
    env_py = PROJECT_ROOT / "migrations" / "env.py"

    content = env_py.read_text()

    assert "from app.db.session import Base" in content
    assert "target_metadata = Base.metadata" in content
    assert "from app.db import base" in content
    assert model_imports


def test_migrations_cover_current_model_tables():
    migration_text = "\n".join(
        path.read_text()
        for path in sorted((PROJECT_ROOT / "migrations" / "versions").glob("*.py"))
    )

    for table_name in Base.metadata.tables:
        assert table_name in migration_text


def test_initial_migration_creates_pgvector_extension():
    migration_text = (PROJECT_ROOT / "migrations" / "versions" / "20260603_0001_initial_document_tables.py").read_text()

    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration_text


def test_application_startup_does_not_create_schema_directly():
    app_text = "\n".join(
        path.read_text()
        for path in (PROJECT_ROOT / "app").rglob("*.py")
        if "__pycache__" not in path.parts
    )

    assert "create_all" not in app_text
