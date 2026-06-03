from fastapi.testclient import TestClient

from app.main import app


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
