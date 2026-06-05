from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dependencies import get_db
from app.ingestion.embedder import EmbeddingError, embed_texts
from app.ingestion.embeddings.factory import get_embedding_provider
from app.ingestion.embeddings.local import LocalEmbeddingProvider
from app.ingestion.embeddings.openai_provider import OpenAIEmbeddingProvider
from app.ingestion.pipeline import InvalidDocumentStatusError, embed_document_chunks
from app.main import app
from app.models.document import Document, DocumentChunk


class FakeSession:
    def __init__(self, document=None, chunks=None):
        self.document = document
        self.chunks = chunks or []
        self.commits = []
        self.rollbacks = 0

    def get(self, model, identifier):
        if model is Document and self.document and self.document.id == identifier:
            return self.document
        return None

    def scalars(self, statement):
        class Result:
            def __init__(self, items):
                self._items = items

            def all(self):
                return self._items

        return Result(sorted(self.chunks, key=lambda chunk: chunk.chunk_index))

    def commit(self):
        if self.document:
            self.commits.append(self.document.status)

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, document):
        return None


def make_document(status="chunked"):
    return Document(
        id=uuid4(),
        title="sample.pdf",
        filename="sample.pdf",
        file_path="data/uploads/sample.pdf",
        source="sample.pdf",
        document_type="pdf",
        status=status,
        source_type="technology_assessment",
        classification="confidential",
        document_metadata={},
    )


def make_chunk(document_id, chunk_index=0, content="technology risk"):
    return DocumentChunk(
        document_id=document_id,
        chunk_index=chunk_index,
        content=content,
        page_start=1,
        page_end=1,
        token_count=2,
        chunk_metadata={},
    )


def test_embed_endpoint_updates_document_status_to_embedded(monkeypatch):
    document = make_document()
    session = FakeSession(document=document, chunks=[make_chunk(document.id)])
    monkeypatch.setattr(
        "app.ingestion.pipeline.embed_texts",
        lambda texts: [[0.1] * 1536 for _ in texts],
    )

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db

    try:
        client = TestClient(app)
        response = client.post(f"/documents/{document.id}/embed")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "embedded"
    assert response.json()["chunks_embedded"] == 1
    assert document.status == "embedded"


def test_chunks_receive_embeddings(monkeypatch):
    document = make_document()
    chunk = make_chunk(document.id)
    session = FakeSession(document=document, chunks=[chunk])
    monkeypatch.setattr("app.ingestion.pipeline.embed_texts", lambda texts: [[0.2] * 1536])

    embed_document_chunks(document.id, session)

    assert chunk.embedding == [0.2] * 1536
    assert document.document_metadata["chunks_embedded"] == 1


def test_embed_endpoint_rejects_unchunked_documents():
    document = make_document(status="parsed")
    session = FakeSession(document=document)

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db

    try:
        client = TestClient(app)
        response = client.post(f"/documents/{document.id}/embed")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert "cannot be embedded" in response.json()["detail"]


def test_unchunked_document_cannot_be_embedded():
    document = make_document(status="uploaded")
    session = FakeSession(document=document)

    try:
        embed_document_chunks(document.id, session)
    except InvalidDocumentStatusError as exc:
        assert "cannot be embedded" in str(exc)
    else:
        raise AssertionError("Expected InvalidDocumentStatusError")


def test_embed_endpoint_rejects_documents_over_chunk_limit(monkeypatch):
    document = make_document()
    session = FakeSession(
        document=document,
        chunks=[
            make_chunk(document.id, chunk_index=0, content="first"),
            make_chunk(document.id, chunk_index=1, content="second"),
        ],
    )
    monkeypatch.setattr(settings, "max_embedding_chunks_per_request", 1)

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db

    try:
        client = TestClient(app)
        response = client.post(f"/documents/{document.id}/embed")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert "per-request limit" in response.json()["detail"]
    assert document.status == "failed"


def test_embed_texts_rejects_oversized_input(monkeypatch):
    monkeypatch.setattr(settings, "max_embedding_text_chars", 10)

    try:
        embed_texts(["x" * 11])
    except EmbeddingError as exc:
        assert "character limit" in str(exc)
    else:
        raise AssertionError("Expected EmbeddingError")


def test_default_embedding_provider_is_local(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "local")
    get_embedding_provider.cache_clear()

    provider = get_embedding_provider()

    assert isinstance(provider, LocalEmbeddingProvider)


def test_embedding_provider_can_use_openai(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "openai")
    get_embedding_provider.cache_clear()

    provider = get_embedding_provider()

    assert isinstance(provider, OpenAIEmbeddingProvider)


def test_embed_texts_uses_configured_provider(monkeypatch):
    class FakeProvider:
        def embed_texts(self, texts):
            return [[0.3] * settings.embedding_dimensions for _ in texts]

        def embedding_dimension(self):
            return settings.embedding_dimensions

    monkeypatch.setattr("app.ingestion.embedder.get_embedding_provider", lambda: FakeProvider())

    embeddings = embed_texts(["  local   embedding  "])

    assert embeddings == [[0.3] * settings.embedding_dimensions]


def test_embedding_provider_exposes_dimension(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "local")
    get_embedding_provider.cache_clear()

    provider = get_embedding_provider()

    assert provider.embedding_dimension() == settings.embedding_dimensions
