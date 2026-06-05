from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.dependencies import get_db
from app.ingestion.chunker import chunk_document_pages
from app.ingestion.pipeline import InvalidDocumentStatusError, chunk_parsed_document
from app.main import app
from app.models.document import Document, DocumentChunk, ParsedDocumentPage


class FakeSession:
    def __init__(self, document=None, pages=None, chunks=None):
        self.document = document
        self.pages = pages or []
        self.chunks = chunks or []
        self.added_chunks = []
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

        if "document_chunks" in str(statement):
            return Result(sorted(self.chunks, key=lambda chunk: chunk.chunk_index))
        return Result(sorted(self.pages, key=lambda page: page.page_number))

    def execute(self, statement):
        self.chunks = []

    def add_all(self, chunks):
        self.added_chunks.extend(chunks)
        self.chunks.extend(chunks)

    def commit(self):
        if self.document:
            self.commits.append(self.document.status)

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, document):
        return None


def make_document(status="parsed"):
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


def make_page(document_id, page_number, text):
    return ParsedDocumentPage(
        document_id=document_id,
        page_number=page_number,
        text=text,
        page_metadata={},
    )


def test_parsed_document_chunks_successfully():
    document = make_document()
    session = FakeSession(
        document=document,
        pages=[
            make_page(document.id, 1, "alpha beta gamma"),
            make_page(document.id, 2, "delta epsilon zeta"),
        ],
    )

    chunked_document = chunk_parsed_document(document.id, session)

    assert chunked_document.status == "chunked"
    assert chunked_document.document_metadata["chunks_created"] == 1
    assert len(session.added_chunks) == 1
    assert session.added_chunks[0].page_start == 1
    assert session.added_chunks[0].page_end == 2


def test_document_status_updates_to_chunked():
    document = make_document()
    session = FakeSession(document=document, pages=[make_page(document.id, 1, "alpha beta")])

    chunk_parsed_document(document.id, session)

    assert document.status == "chunked"
    assert session.commits == ["chunked"]


def test_existing_chunks_are_replaced_on_rechunk():
    document = make_document(status="chunked")
    existing_chunk = DocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="old chunk",
        page_start=1,
        page_end=1,
        token_count=2,
        chunk_metadata={},
    )
    session = FakeSession(
        document=document,
        pages=[make_page(document.id, 1, "new chunk text")],
        chunks=[existing_chunk],
    )

    chunk_parsed_document(document.id, session)

    assert len(session.chunks) == 1
    assert session.chunks[0].content == "new chunk text"
    assert session.added_chunks[0].content == "new chunk text"


def test_empty_parsed_pages_are_skipped():
    document = make_document()
    chunks = chunk_document_pages(
        [
            make_page(document.id, 1, ""),
            make_page(document.id, 2, "useful text"),
        ],
        target_tokens=10,
        overlap_tokens=2,
    )

    assert len(chunks) == 1
    assert chunks[0].page_start == 2
    assert chunks[0].content == "useful text"


def test_invalid_document_id_returns_404():
    missing_document_id = uuid4()
    session = FakeSession()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db

    try:
        client = TestClient(app)
        response = client.post(f"/documents/{missing_document_id}/chunk")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_unparsed_document_cannot_be_chunked():
    document = make_document(status="uploaded")
    session = FakeSession(document=document)

    try:
        chunk_parsed_document(document.id, session)
    except InvalidDocumentStatusError as exc:
        assert "cannot be chunked" in str(exc)
    else:
        raise AssertionError("Expected InvalidDocumentStatusError")


def test_get_document_chunks_returns_previews():
    document = make_document(status="chunked")
    session = FakeSession(
        document=document,
        chunks=[
            DocumentChunk(
                document_id=document.id,
                chunk_index=0,
                content="a" * 1200,
                page_start=1,
                page_end=2,
                token_count=100,
                chunk_metadata={},
            )
        ],
    )

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db

    try:
        client = TestClient(app)
        response = client.get(f"/documents/{document.id}/chunks")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == str(document.id)
    assert body["chunks"][0]["chunk_index"] == 0
    assert body["chunks"][0]["page_start"] == 1
    assert body["chunks"][0]["page_end"] == 2
    assert body["chunks"][0]["token_count"] == 100
    assert len(body["chunks"][0]["content_preview"]) == 1000
