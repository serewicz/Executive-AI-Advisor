from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dependencies import get_db
from app.main import app


class FakeSession:
    def __init__(self, fail_on_commit=False):
        self.document = None
        self.committed = False
        self.fail_on_commit = fail_on_commit
        self.rolled_back = False

    def add(self, document):
        self.document = document

    def commit(self):
        if self.fail_on_commit:
            raise RuntimeError("database unavailable")
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
    response_body = response.json()
    assert response_body["document_id"]
    assert response_body["filename"] == "board-pack.pdf"
    assert response_body["status"] == "uploaded"
    assert response_body["source_type"] == "board_material"
    assert response_body["classification"] == "confidential"

    assert fake_session.committed is True
    assert fake_session.document.filename == "board-pack.pdf"
    assert fake_session.document.file_path
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


def test_document_upload_rejects_fake_pdf(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    client = TestClient(app)
    response = client.post(
        "/documents/upload",
        data={
            "source_type": "board_material",
            "classification": "confidential",
        },
        files={
            "file": (
                "fake.pdf",
                b"not actually a pdf",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Uploaded file is not a valid PDF."}
    assert list(tmp_path.iterdir()) == []


def test_document_upload_rejects_oversized_pdf(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    monkeypatch.setattr(settings, "max_upload_mb", 0)

    client = TestClient(app)
    response = client.post(
        "/documents/upload",
        data={
            "source_type": "board_material",
            "classification": "confidential",
        },
        files={
            "file": (
                "too-large.pdf",
                b"%PDF-1.4\nsample",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "Uploaded file exceeds the 0 MB limit."}
    assert list(tmp_path.iterdir()) == []


def test_document_upload_removes_file_when_metadata_persistence_fails(monkeypatch, tmp_path):
    fake_session = FakeSession(fail_on_commit=True)
    monkeypatch.setattr(settings, "upload_dir", tmp_path)

    def override_db():
        yield fake_session

    app.dependency_overrides[get_db] = override_db

    try:
        client = TestClient(app, raise_server_exceptions=False)
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

    assert response.status_code == 500
    assert fake_session.rolled_back is True
    assert list(tmp_path.iterdir()) == []
