from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dependencies import get_db
from app.main import app
from app.models.document import Document, DocumentSet, DocumentSetDocument


class FakeExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeDocumentSetSession:
    def __init__(self):
        self.document_sets = {}
        self.documents = {}
        self.links = set()
        self.commits = 0
        self.rollbacks = 0

    def add(self, instance):
        if isinstance(instance, DocumentSet):
            if instance.id is None:
                instance.id = uuid4()
            instance.created_at = instance.created_at or datetime.now(UTC)
            self.document_sets[instance.id] = instance
        elif isinstance(instance, Document):
            self.documents[instance.id] = instance
        elif isinstance(instance, DocumentSetDocument):
            self.links.add((instance.document_set_id, instance.document_id))

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, instance):
        return None

    def get(self, model, object_id):
        if model is DocumentSet:
            return self.document_sets.get(object_id)
        if model is Document:
            return self.documents.get(object_id)
        if model is DocumentSetDocument:
            key = (object_id["document_set_id"], object_id["document_id"])
            if key in self.links:
                return DocumentSetDocument(document_set_id=key[0], document_id=key[1])
        return None

    def execute(self, statement):
        statement_text = str(statement)
        if "DELETE FROM document_set_documents" in statement_text:
            self.links.clear()
            return FakeExecuteResult([])
        if "count" in statement_text.lower():
            return FakeExecuteResult(
                [
                    (
                        document_set,
                        sum(1 for document_set_id, _document_id in self.links if document_set_id == document_set.id),
                    )
                    for document_set in self.document_sets.values()
                ]
            )
        return FakeExecuteResult([])

    def scalars(self, statement):
        return FakeScalarResult(
            [
                document
                for document_set_id, document_id in self.links
                for document in [self.documents[document_id]]
                if document_set_id in self.document_sets
            ]
        )


def override_db(session):
    def _override_db():
        yield session

    return _override_db


def make_document(filename="sample.pdf"):
    return Document(
        id=uuid4(),
        title=filename,
        filename=filename,
        file_path=f"data/uploads/{filename}",
        source=filename,
        document_type="pdf",
        status="uploaded",
        source_type="technology_assessment",
        classification="confidential",
        document_metadata={},
    )


def test_create_document_set():
    session = FakeDocumentSetSession()
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/document-sets",
            json={"name": "SampleCo Diligence", "description": "Synthetic package"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["document_set_id"]
    assert body["name"] == "SampleCo Diligence"
    assert len(session.document_sets) == 1


def test_upload_document_into_document_set(monkeypatch, tmp_path):
    session = FakeDocumentSetSession()
    document_set = DocumentSet(id=uuid4(), name="SampleCo Diligence", description=None)
    session.add(document_set)
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/documents/upload",
            data={
                "source_type": "board_material",
                "classification": "confidential",
                "document_set_id": str(document_set.id),
            },
            files={"file": ("sample.pdf", b"%PDF-1.4\nsample", "application/pdf")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    document_id = next(iter(session.documents))
    assert (document_set.id, document_id) in session.links
    assert Path(session.documents[document_id].file_path).exists()


def test_retrieve_document_set_with_documents():
    session = FakeDocumentSetSession()
    document_set = DocumentSet(id=uuid4(), name="SampleCo Diligence", description="Synthetic")
    document = make_document()
    session.add(document_set)
    session.add(document)
    session.add(DocumentSetDocument(document_set_id=document_set.id, document_id=document.id))
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.get(f"/document-sets/{document_set.id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["document_set_id"] == str(document_set.id)
    assert body["documents"][0]["document_id"] == str(document.id)


def test_multiple_uploads_append_documents_to_document_set(monkeypatch, tmp_path):
    session = FakeDocumentSetSession()
    document_set = DocumentSet(id=uuid4(), name="SampleCo Diligence", description=None)
    session.add(document_set)
    monkeypatch.setattr(settings, "upload_dir", tmp_path)
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        for filename in ["one.pdf", "two.pdf"]:
            response = client.post(
                "/documents/upload",
                data={
                    "source_type": "board_material",
                    "classification": "confidential",
                    "document_set_id": str(document_set.id),
                },
                files={"file": (filename, b"%PDF-1.4\nsample", "application/pdf")},
            )
            assert response.status_code == 201
    finally:
        app.dependency_overrides.clear()

    assert len(session.documents) == 2
    assert len(session.links) == 2
