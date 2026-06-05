from uuid import uuid4

from fastapi.testclient import TestClient

from app.advisor.providers.base import LLMError
from app.advisor.providers.factory import get_llm_provider
from app.advisor.providers.openai_provider import OpenAIChatProvider
from app.core.config import settings
from app.db.dependencies import get_db
from app.main import app
from app.retrieval.vector_search import SearchResult


class FakeSession:
    pass


def make_search_result(content="Cloud governance and security risks are material."):
    document_id = uuid4()
    return SearchResult(
        document_id=document_id,
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
