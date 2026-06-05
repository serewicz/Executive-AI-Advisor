from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.dependencies import get_db
from app.main import app
from app.models.document import Document, DocumentChunk
from app.retrieval.vector_search import search_similar_chunks


class FakeExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeSearchSession:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, statement):
        return FakeExecuteResult(self.rows)


def make_document(source_type="technology_assessment", classification="confidential"):
    return Document(
        id=uuid4(),
        title="Technology Assessment",
        filename="assessment.pdf",
        file_path="data/uploads/assessment.pdf",
        source="assessment.pdf",
        document_type="pdf",
        status="embedded",
        source_type=source_type,
        classification=classification,
        document_metadata={},
    )


def make_chunk(document_id, chunk_index, content):
    return DocumentChunk(
        id=uuid4(),
        document_id=document_id,
        chunk_index=chunk_index,
        content=content,
        page_start=chunk_index + 1,
        page_end=chunk_index + 1,
        token_count=10,
        chunk_metadata={},
        embedding=[0.1] * 1536,
    )


def make_rows():
    document = make_document()
    first_chunk = make_chunk(document.id, 0, "Main technology risks include vendor lock-in.")
    second_chunk = make_chunk(document.id, 1, "Secondary risks include delivery delays.")
    return [
        (first_chunk, document, 0.18),
        (second_chunk, document, 0.31),
    ]


def test_search_endpoint_returns_ranked_results(monkeypatch):
    rows = make_rows()
    session = FakeSearchSession(rows)
    monkeypatch.setattr(
        "app.retrieval.vector_search.embed_texts",
        lambda texts: [[0.5] * 1536 for _ in texts],
    )

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db

    try:
        client = TestClient(app)
        response = client.post(
            "/search",
            json={"query": "What are the main technology risks?", "top_k": 5},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "What are the main technology risks?"
    assert len(body["results"]) == 2
    assert body["results"][0]["chunk_index"] == 0
    assert body["results"][0]["similarity_score"] == 0.82
    assert body["results"][0]["page_start"] == 1
    assert body["results"][0]["classification"] == "confidential"


def test_search_filters_by_source_type(monkeypatch):
    rows = make_rows()
    session = FakeSearchSession(rows)
    monkeypatch.setattr(
        "app.retrieval.vector_search.embed_texts",
        lambda texts: [[0.5] * 1536 for _ in texts],
    )

    results = search_similar_chunks(
        query="technology risks",
        db=session,
        source_type="technology_assessment",
    )

    assert len(results) == 2
    assert {result.source_type for result in results} == {"technology_assessment"}


def test_search_filters_by_classification(monkeypatch):
    rows = make_rows()
    session = FakeSearchSession(rows)
    monkeypatch.setattr(
        "app.retrieval.vector_search.embed_texts",
        lambda texts: [[0.5] * 1536 for _ in texts],
    )

    results = search_similar_chunks(
        query="technology risks",
        db=session,
        classification="confidential",
    )

    assert len(results) == 2
    assert {result.classification for result in results} == {"confidential"}


def test_invalid_empty_query_returns_422():
    client = TestClient(app)
    response = client.post("/search", json={"query": "", "top_k": 5})

    assert response.status_code == 422
