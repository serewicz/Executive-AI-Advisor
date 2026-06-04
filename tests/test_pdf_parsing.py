from uuid import uuid4

from fastapi.testclient import TestClient
from pgvector.sqlalchemy import Vector
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgresUUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.db.dependencies import get_db
from app.db.session import Base
from app.ingestion.parser import PDFParsingError, ParsedPage, parse_pdf
from app.ingestion.pipeline import parse_uploaded_document
from app.main import app
from app.models.document import Document, ParsedDocumentPage


@compiles(JSONB, "sqlite")
def compile_jsonb_for_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(PostgresUUID, "sqlite")
def compile_uuid_for_sqlite(type_, compiler, **kw):
    return "CHAR(32)"


@compiles(Vector, "sqlite")
def compile_vector_for_sqlite(type_, compiler, **kw):
    return "JSON"


class FakeSession:
    def __init__(self, document=None, pages=None):
        self.document = document
        self.pages = pages or []
        self.added_pages = []
        self.commits = []
        self.rollbacks = 0

    def get(self, model, identifier):
        if model is Document and self.document and self.document.id == identifier:
            return self.document
        return None

    def execute(self, statement):
        self.pages = []

    def add_all(self, pages):
        self.added_pages.extend(pages)
        self.pages.extend(pages)

    def commit(self):
        if self.document:
            self.commits.append(self.document.status)

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, document):
        return None

    def scalars(self, statement):
        class Result:
            def __init__(self, pages):
                self._pages = pages

            def all(self):
                return self._pages

        return Result(sorted(self.pages, key=lambda page: page.page_number))


def make_document(status="uploaded"):
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


def test_successful_parse_updates_document_status_to_parsed(monkeypatch):
    document = make_document()
    session = FakeSession(document=document)

    monkeypatch.setattr(
        "app.ingestion.pipeline.parse_pdf",
        lambda document_id, file_path: [
            ParsedPage(page_number=1, text="First page", metadata={"parser": "test"}),
            ParsedPage(page_number=2, text="Second page", metadata={"parser": "test"}),
        ],
    )

    parsed_document = parse_uploaded_document(document.id, session)

    assert parsed_document.status == "parsed"
    assert session.commits == ["parsing", "parsed"]
    assert parsed_document.document_metadata["pages_parsed"] == 2


def test_parsed_pages_are_stored(monkeypatch):
    document = make_document()
    session = FakeSession(document=document)

    monkeypatch.setattr(
        "app.ingestion.pipeline.parse_pdf",
        lambda document_id, file_path: [
            ParsedPage(page_number=3, text="Board memo", metadata={"parser": "test"}),
        ],
    )

    parse_uploaded_document(document.id, session)

    assert len(session.added_pages) == 1
    assert session.added_pages[0].document_id == document.id
    assert session.added_pages[0].page_number == 3
    assert session.added_pages[0].text == "Board memo"


def test_parse_persists_pages_with_real_sqlalchemy_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
    document = make_document()

    monkeypatch.setattr(
        "app.ingestion.pipeline.parse_pdf",
        lambda document_id, file_path: [
            ParsedPage(page_number=2, text="Second page", metadata={"parser": "test"}),
            ParsedPage(page_number=1, text="First page", metadata={"parser": "test"}),
        ],
    )

    with TestingSession() as session:
        session.add(document)
        session.commit()

        parsed_document = parse_uploaded_document(document.id, session)

        pages = session.scalars(
            select(ParsedDocumentPage)
            .where(ParsedDocumentPage.document_id == document.id)
            .order_by(ParsedDocumentPage.page_number)
        ).all()

    assert parsed_document.status == "parsed"
    assert [page.page_number for page in pages] == [1, 2]
    assert [page.text for page in pages] == ["First page", "Second page"]


def test_empty_pages_are_skipped(monkeypatch, tmp_path):
    sample_pdf = tmp_path / "sample.pdf"
    sample_pdf.write_bytes(b"%PDF-1.4\nsample")

    monkeypatch.setattr(
        "app.ingestion.parser._parse_with_docling",
        lambda path: [
            ParsedPage(page_number=1, text="", metadata={"parser": "test"}),
            ParsedPage(page_number=2, text="Useful text", metadata={"parser": "test"}),
        ],
    )

    pages = parse_pdf(uuid4(), str(sample_pdf))

    assert pages == [ParsedPage(page_number=2, text="Useful text", metadata={"parser": "test"})]


def test_invalid_document_id_returns_404():
    missing_document_id = uuid4()
    session = FakeSession()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db

    try:
        client = TestClient(app)
        response = client.post(f"/documents/{missing_document_id}/parse")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_parser_failure_sets_document_status_to_failed(monkeypatch):
    document = make_document()
    session = FakeSession(document=document)

    def fail_parse(document_id, file_path):
        raise PDFParsingError("parser failed")

    monkeypatch.setattr("app.ingestion.pipeline.parse_pdf", fail_parse)

    try:
        parse_uploaded_document(document.id, session)
    except PDFParsingError:
        pass

    assert document.status == "failed"
    assert "parser failed" in document.document_metadata["parse_error"]
    assert session.commits == ["parsing", "failed"]
    assert session.rollbacks == 1


def test_zero_parsed_pages_sets_document_status_to_failed(monkeypatch):
    document = make_document()
    session = FakeSession(document=document)

    monkeypatch.setattr("app.ingestion.pipeline.parse_pdf", lambda document_id, file_path: [])

    try:
        parse_uploaded_document(document.id, session)
    except PDFParsingError:
        pass

    assert document.status == "failed"
    assert "No text pages" in document.document_metadata["parse_error"]
    assert session.commits == ["parsing", "failed"]
    assert session.rollbacks == 1


def test_get_document_pages_returns_text_previews():
    document = make_document(status="parsed")
    session = FakeSession(
        document=document,
        pages=[
            ParsedDocumentPage(document_id=document.id, page_number=1, text="a" * 1200, page_metadata={}),
            ParsedDocumentPage(document_id=document.id, page_number=2, text="short text", page_metadata={}),
        ],
    )

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db

    try:
        client = TestClient(app)
        response = client.get(f"/documents/{document.id}/pages")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == str(document.id)
    assert len(body["pages"][0]["text_preview"]) == 1000
    assert body["pages"][1]["text_preview"] == "short text"
