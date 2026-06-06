from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.main import app


def test_root_endpoint_points_to_api_and_streamlit_ui():
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["api_docs"] == "/docs"
    assert response.json()["health"] == "/health"
    assert "streamlit run ui/streamlit_app.py" in response.json()["streamlit_ui"]


def test_health_endpoint_returns_status(monkeypatch):
    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def execute(self, statement):
            return None

    monkeypatch.setattr("app.api.routes.health.SessionLocal", lambda: FakeSession())

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_endpoint_handles_database_failure(monkeypatch):
    class FailingSession:
        def __enter__(self):
            raise SQLAlchemyError("database unavailable")

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr("app.api.routes.health.SessionLocal", lambda: FailingSession())

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "unavailable"}
