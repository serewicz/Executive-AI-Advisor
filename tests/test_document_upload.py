from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dependencies import get_db
from app.main import app


class FakeSession:
    def __init__(self):
        self.document = None
        self.committed = False
        self.rolled_back = False

    def add(self, document):
        self.document = document

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def test_document_upload_saves_pdf_metadata(monkeypatch, tmp_path):
    fake_session = FakeSession()
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    def override_db():
        yield fake_session

    app.dependency_overrides[get_db] = override_db

    try:
        client = TestClient(app)
        response = client.post(
            "/documents/upload",
            data={
                "source_type": "board_material",
                "classification": "confidential",
            },
            files={
                "file": (
                    "board-pack.pdf",
                    b"%PDF-1.4\nsample",
                    "application/pdf",
                )
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["status"] == "uploaded"
    assert response.json()["document_id"]

    assert fake_session.committed is True
    assert fake_session.document.filename == "board-pack.pdf"
    assert fake_session.document.status == "uploaded"
    assert fake_session.document.source_type == "board_material"
    assert fake_session.document.classification == "confidential"
    assert Path(fake_session.document.file_path).exists()
    assert Path(fake_session.document.file_path).parent == tmp_path


def test_document_upload_rejects_non_pdf():
    client = TestClient(app)
    response = client.post(
        "/documents/upload",
        data={
            "source_type": "board_material",
            "classification": "confidential",
        },
        files={
            "file": (
                "notes.txt",
                b"not a pdf",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Only PDF uploads are supported."}
