from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.dependencies import get_db
from app.main import app
from app.models.document import Document, DocumentChunk


class FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeBoardSummarySession:
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


def make_chunk(document_id, chunk_index=0, content="Cloud governance and security controls need review."):
    return DocumentChunk(
        id=uuid4(),
        document_id=document_id,
        chunk_index=chunk_index,
        content=content,
        page_start=chunk_index + 1,
        page_end=chunk_index + 1,
        token_count=10,
        chunk_metadata={},
        embedding=None,
    )


def override_db(session):
    def _override_db():
        yield session

    return _override_db


def test_board_summary_returns_structured_memo():
    document = make_document()
    session = FakeBoardSummarySession(document=document, chunks=[make_chunk(document.id)])
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/advisor/board-summary",
            json={
                "document_id": str(document.id),
                "summary_type": "technology_risk",
                "top_k": 3,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == str(document.id)
    assert body["summary_type"] == "technology_risk"
    assert body["confidence"] == "medium"
    assert body["memo"]["executive_summary"]
    assert body["memo"]["key_risks"]
    assert body["memo"]["board_questions"]
    assert body["memo"]["recommended_actions"]


def test_board_summary_includes_citations():
    document = make_document()
    chunk = make_chunk(document.id, content="Identity governance gaps create operational risk.")
    session = FakeBoardSummarySession(document=document, chunks=[chunk])
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/advisor/board-summary",
            json={"document_id": str(document.id), "summary_type": "security_governance"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    citation = response.json()["citations"][0]
    assert citation["source_label"] == "S1"
    assert citation["document_id"] == str(document.id)
    assert citation["document_title"] == "Technology Assessment"
    assert citation["chunk_id"] == str(chunk.id)
    assert citation["page_start"] == 1
    assert citation["page_end"] == 1
    assert citation["excerpt"] == "Identity governance gaps create operational risk."
    assert citation["full_source_text"] == "Identity governance gaps create operational risk."


def test_invalid_document_id_returns_404():
    session = FakeBoardSummarySession()
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/advisor/board-summary",
            json={"document_id": str(uuid4()), "summary_type": "board_brief"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_no_chunks_returns_400():
    document = make_document()
    session = FakeBoardSummarySession(document=document, chunks=[])
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/advisor/board-summary",
            json={"document_id": str(document.id), "summary_type": "diligence_summary"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "no chunks" in response.json()["detail"].lower()


def test_unsupported_summary_type_returns_422():
    document_id = uuid4()
    client = TestClient(app)
    response = client.post(
        "/advisor/board-summary",
        json={"document_id": str(document_id), "summary_type": "unsupported"},
    )

    assert response.status_code == 422


def test_top_k_over_max_returns_422():
    document_id = uuid4()
    client = TestClient(app)
    response = client.post(
        "/advisor/board-summary",
        json={"document_id": str(document_id), "summary_type": "ai_readiness", "top_k": 26},
    )

    assert response.status_code == 422


def test_mock_provider_does_not_call_external_apis(monkeypatch):
    called = False

    def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("OpenAI should not be called by the mock provider.")

    monkeypatch.setattr("openai.resources.chat.completions.Completions.create", fail_if_called)
    document = make_document()
    session = FakeBoardSummarySession(document=document, chunks=[make_chunk(document.id)])
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/advisor/board-summary",
            json={"document_id": str(document.id), "summary_type": "board_brief"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert called is False


def test_board_summary_evidence_cites_source_labels():
    document = make_document()
    session = FakeBoardSummarySession(document=document, chunks=[make_chunk(document.id)])
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/advisor/board-summary",
            json={"document_id": str(document.id), "summary_type": "ai_readiness"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "[S1]" in response.json()["memo"]["evidence"][0]


def test_board_summary_skips_table_of_contents_chunk():
    document = make_document()
    toc_chunk = make_chunk(
        document.id,
        chunk_index=0,
        content="Contents Executive Summary ........ 1 Security Assessment ........ 4 Cloud Cost ........ 8",
    )
    toc_chunk.chunk_metadata = {"low_value": True}
    useful_chunk = make_chunk(
        document.id,
        chunk_index=1,
        content="Security governance gaps create board-level access review risk.",
    )
    session = FakeBoardSummarySession(document=document, chunks=[toc_chunk, useful_chunk])
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/advisor/board-summary",
            json={"document_id": str(document.id), "summary_type": "security_governance"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    citation = response.json()["citations"][0]
    assert citation["chunk_id"] == str(useful_chunk.id)
    assert "Contents" not in citation["excerpt"]


def test_board_summary_citations_use_extracted_excerpts():
    document = make_document()
    content = (
        "This opening background sentence is intentionally long and describes general company history "
        "without discussing the diligence issue. "
        + "x " * 300
        + "Security governance gaps create access control risk for the board. "
        "The board should monitor privileged access reviews and incident readiness. "
        "Commercial updates and unrelated roadmap notes follow after the risk discussion."
    )
    chunk = make_chunk(document.id, content=content)
    session = FakeBoardSummarySession(document=document, chunks=[chunk])
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/advisor/board-summary",
            json={"document_id": str(document.id), "summary_type": "security_governance"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    citation = response.json()["citations"][0]
    assert len(citation["excerpt"]) < len(content)
    assert "Security governance" in citation["excerpt"]
    assert "access control risk" in citation["excerpt"]
