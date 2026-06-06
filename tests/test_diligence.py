from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.dependencies import get_db
from app.diligence.scoring import score_assessment
from app.main import app
from app.models.document import Document, DocumentChunk
from app.retrieval.vector_search import SearchResult


class FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeDiligenceSession:
    def __init__(self, document=None, chunks=None):
        self.document = document
        self.chunks = chunks or []

    def get(self, model, object_id):
        if self.document is not None and self.document.id == object_id:
            return self.document
        return None

    def scalars(self, statement):
        return FakeScalarResult(sorted(self.chunks, key=lambda chunk: chunk.chunk_index))


def make_document(status="chunked"):
    return Document(
        id=uuid4(),
        title="Technology Assessment",
        filename="assessment.pdf",
        file_path="data/uploads/assessment.pdf",
        source="assessment.pdf",
        document_type="pdf",
        status=status,
        source_type="technology_assessment",
        classification="confidential",
        document_metadata={},
    )


def make_chunk(document_id, chunk_index=0):
    return DocumentChunk(
        id=uuid4(),
        document_id=document_id,
        chunk_index=chunk_index,
        content="Security controls, cloud architecture, governance, and operational risk require board review.",
        page_start=chunk_index + 1,
        page_end=chunk_index + 1,
        token_count=12,
        chunk_metadata={},
        embedding=None,
    )


def override_db(session):
    def _override_db():
        yield session

    return _override_db


def test_diligence_analyze_returns_assessment():
    document = make_document()
    session = FakeDiligenceSession(document=document, chunks=[make_chunk(document.id)])
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/diligence/analyze",
            json={"document_id": str(document.id), "assessment_type": "architecture"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == str(document.id)
    assert body["assessment_type"] == "architecture"
    assert 1 <= body["score"] <= 5
    assert body["executive_summary"]
    assert body["findings"]
    assert body["risks"]
    assert body["recommendations"]
    assert body["citations"]
    assert body["confidence"] in {"high", "medium", "low"}
    assert body["limitations"]


def test_diligence_invalid_assessment_type_returns_422():
    client = TestClient(app)
    response = client.post(
        "/diligence/analyze",
        json={"document_id": str(uuid4()), "assessment_type": "unsupported"},
    )

    assert response.status_code == 422


def test_diligence_missing_document_returns_404():
    session = FakeDiligenceSession()
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/diligence/analyze",
            json={"document_id": str(uuid4()), "assessment_type": "security"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_diligence_unprocessed_document_returns_400():
    document = make_document(status="uploaded")
    session = FakeDiligenceSession(document=document, chunks=[])
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/diligence/analyze",
            json={"document_id": str(document.id), "assessment_type": "technical_debt"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


def test_diligence_score_is_bounded():
    document_id = uuid4()
    result = SearchResult(
        document_id=document_id,
        document_title="Assessment",
        chunk_id=uuid4(),
        chunk_index=0,
        content="Legacy manual fragile architecture creates outage risk and bottleneck exposure.",
        page_start=1,
        page_end=1,
        similarity_score=0.0,
        source_type="technology_assessment",
        classification="confidential",
    )

    score = score_assessment("architecture", [result])

    assert 1 <= score <= 5
