from uuid import uuid4

from fastapi.testclient import TestClient

from app.advisor.providers.base import LLMError
from app.advisor.providers.factory import get_llm_provider
from app.advisor.providers.openai_provider import OpenAIChatProvider
from app.core.config import settings
from app.db.dependencies import get_db
from app.main import app
from app.models.document import Document, DocumentSet
from app.retrieval.vector_search import SearchResult


class FakeSession:
    def __init__(self, document=None, document_set=None):
        self.document = document
        self.document_set = document_set

    def get(self, model, object_id):
        if model is Document and self.document is not None and self.document.id == object_id:
            return self.document
        if model is DocumentSet and self.document_set is not None and self.document_set.id == object_id:
            return self.document_set
        return None


def make_document(filename="assessment.pdf"):
    return Document(
        id=uuid4(),
        title="Technology Assessment",
        filename=filename,
        file_path=f"data/uploads/{filename}",
        source=filename,
        document_type="pdf",
        status="embedded",
        source_type="technology_assessment",
        classification="confidential",
        document_metadata={},
    )


def make_document_set():
    return DocumentSet(id=uuid4(), name="SampleCo Diligence", description="Synthetic diligence")


def make_search_result(content="Cloud governance and security risks are material.", document_id=None):
    return SearchResult(
        document_id=document_id or uuid4(),
        document_title="Technology Assessment",
        chunk_id=uuid4(),
        chunk_index=0,
        content=content,
        page_start=1,
        page_end=2,
        similarity_score=0.82,
        source_type="technology_assessment",
        classification="confidential",
    )


def override_db():
    yield FakeSession()


def override_db_with(session):
    def _override_db():
        yield session

    return _override_db


def test_advisor_endpoint_returns_answer(monkeypatch):
    monkeypatch.setattr(
        "app.advisor.service.search_similar_chunks",
        lambda **kwargs: [make_search_result()],
    )
    app.dependency_overrides[get_db] = override_db

    try:
        client = TestClient(app)
        response = client.post(
            "/advisor/ask",
            json={"question": "What are the main technology risks?", "top_k": 5},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["question"] == "What are the main technology risks?"
    assert "[S1]" in body["answer"]
    assert body["confidence"] == "medium"
    assert body["scope"] == "global"
    assert body["document_id"] is None


def test_advisor_response_includes_citations(monkeypatch):
    result = make_search_result()
    monkeypatch.setattr("app.advisor.service.search_similar_chunks", lambda **kwargs: [result])
    app.dependency_overrides[get_db] = override_db

    try:
        client = TestClient(app)
        response = client.post("/advisor/ask", json={"question": "Summarize the risks."})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    citation = response.json()["citations"][0]
    assert citation["document_id"] == str(result.document_id)
    assert citation["document_title"] == "Technology Assessment"
    assert citation["chunk_id"] == str(result.chunk_id)
    assert citation["page_start"] == 1
    assert citation["page_end"] == 2
    assert citation["excerpt"]


def test_advisor_with_document_id_only_returns_citations_from_that_document(monkeypatch):
    selected_document = make_document("sampleco.pdf")
    other_document_id = uuid4()

    def scoped_search(**kwargs):
        assert kwargs["document_id"] == selected_document.id
        all_results = [
            make_search_result("SampleCo technical debt requires attention.", document_id=selected_document.id),
            make_search_result("Snowflake 10-K risk should not appear.", document_id=other_document_id),
        ]
        return [result for result in all_results if result.document_id == kwargs["document_id"]]

    monkeypatch.setattr("app.advisor.service.search_similar_chunks", scoped_search)
    app.dependency_overrides[get_db] = override_db_with(FakeSession(selected_document))

    try:
        client = TestClient(app)
        response = client.post(
            "/advisor/ask",
            json={
                "question": "What are the main technology risks?",
                "top_k": 5,
                "document_id": str(selected_document.id),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "document"
    assert body["document_id"] == str(selected_document.id)
    assert {citation["document_id"] for citation in body["citations"]} == {str(selected_document.id)}


def test_advisor_without_document_id_can_search_globally(monkeypatch):
    selected_document_id = uuid4()
    other_document_id = uuid4()

    def global_search(**kwargs):
        assert kwargs["document_id"] is None
        return [
            make_search_result("SampleCo technical debt requires attention.", document_id=selected_document_id),
            make_search_result("Snowflake 10-K risk can appear in global mode.", document_id=other_document_id),
        ]

    monkeypatch.setattr("app.advisor.service.search_similar_chunks", global_search)
    app.dependency_overrides[get_db] = override_db

    try:
        client = TestClient(app)
        response = client.post("/advisor/ask", json={"question": "What are the main technology risks?"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "global"
    assert body["document_id"] is None
    assert {citation["document_id"] for citation in body["citations"]} == {
        str(selected_document_id),
        str(other_document_id),
    }


def test_advisor_with_document_set_id_only_returns_set_citations(monkeypatch):
    document_set = make_document_set()
    included_document_id = uuid4()
    unrelated_document_id = uuid4()

    def scoped_search(**kwargs):
        assert kwargs["document_id"] is None
        assert kwargs["document_set_id"] == document_set.id
        return [
            make_search_result("SampleCo architecture risk requires review.", document_id=included_document_id),
        ]

    monkeypatch.setattr("app.advisor.service.search_similar_chunks", scoped_search)
    app.dependency_overrides[get_db] = override_db_with(FakeSession(document_set=document_set))

    try:
        client = TestClient(app)
        response = client.post(
            "/advisor/ask",
            json={
                "question": "What are the main technology risks?",
                "document_set_id": str(document_set.id),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "document_set"
    assert body["document_set_id"] == str(document_set.id)
    assert {citation["document_id"] for citation in body["citations"]} == {str(included_document_id)}
    assert str(unrelated_document_id) not in {citation["document_id"] for citation in body["citations"]}


def test_advisor_invalid_document_id_returns_404(monkeypatch):
    called = False

    def search_should_not_run(**kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr("app.advisor.service.search_similar_chunks", search_should_not_run)
    app.dependency_overrides[get_db] = override_db_with(FakeSession())

    try:
        client = TestClient(app)
        response = client.post(
            "/advisor/ask",
            json={"question": "What are the risks?", "document_id": str(uuid4())},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert called is False


def test_mock_provider_does_not_call_external_apis(monkeypatch):
    called = False

    def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("OpenAI should not be called by the mock provider.")

    monkeypatch.setattr("openai.resources.chat.completions.Completions.create", fail_if_called)
    monkeypatch.setattr("app.advisor.service.search_similar_chunks", lambda **kwargs: [make_search_result()])
    app.dependency_overrides[get_db] = override_db

    try:
        client = TestClient(app)
        response = client.post("/advisor/ask", json={"question": "What risks are present?"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert called is False


def test_empty_question_is_rejected():
    client = TestClient(app)
    response = client.post("/advisor/ask", json={"question": ""})

    assert response.status_code == 422


def test_no_search_results_returns_low_confidence_with_limitations(monkeypatch):
    monkeypatch.setattr("app.advisor.service.search_similar_chunks", lambda **kwargs: [])
    app.dependency_overrides[get_db] = override_db

    try:
        client = TestClient(app)
        response = client.post("/advisor/ask", json={"question": "What are the risks?"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["confidence"] == "low"
    assert body["citations"] == []
    assert body["limitations"] == ["No relevant source chunks were retrieved."]


def test_openai_provider_missing_api_key_raises_only_when_selected(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "llm_provider", "mock")
    get_llm_provider.cache_clear()

    mock_provider = get_llm_provider()

    assert mock_provider.__class__.__name__ == "MockLLMProvider"

    monkeypatch.setattr(settings, "llm_provider", "openai")
    get_llm_provider.cache_clear()
    openai_provider = get_llm_provider()

    try:
        openai_provider.answer_question(
            question="What are the risks?",
            sources=[],
            system_prompt="system",
            user_prompt="user",
        )
    except LLMError as exc:
        assert "OPENAI_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected LLMError")
    finally:
        get_llm_provider.cache_clear()

    assert isinstance(openai_provider, OpenAIChatProvider)
