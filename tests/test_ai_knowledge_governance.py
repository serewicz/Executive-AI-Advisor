from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.dependencies import get_db
from app.governance.ai_knowledge_scoring import (
    missing_evidence_for_category,
    readiness_for_category,
)
from app.main import app
from app.models.document import DocumentSet
from app.retrieval.vector_search import SearchResult
from ui.streamlit_app import _build_ai_knowledge_governance_markdown


class FakeAIKnowledgeSession:
    def __init__(self, document_set=None):
        self.document_set = document_set

    def get(self, model, object_id):
        if model is DocumentSet and self.document_set is not None and self.document_set.id == object_id:
            return self.document_set
        return None


def override_db(session):
    def _override_db():
        yield session

    return _override_db


def make_document_set():
    return DocumentSet(id=uuid4(), name="SampleCo Diligence", description="Synthetic diligence package")


def make_search_result(document_id=None, content=None, title="SampleCo AI Readiness Assessment"):
    return SearchResult(
        document_id=document_id or uuid4(),
        document_title=title,
        chunk_id=uuid4(),
        chunk_index=0,
        content=content
        or (
            "SampleCo maintains an internal knowledge repository and is evaluating RAG for support documents. "
            "SSO and RBAC are documented for internal tools. Teams have discussed OpenSearch for enterprise "
            "search, but formal governance artifacts for AI knowledge use remain incomplete."
        ),
        page_start=1,
        page_end=2,
        similarity_score=0.83,
        source_type="technology_assessment",
        classification="confidential",
        chunk_metadata={},
    )


def test_ai_knowledge_governance_endpoint_requires_document_set_id():
    client = TestClient(app)

    response = client.post("/governance/ai-knowledge", json={"top_k": 20})

    assert response.status_code == 422


def test_ai_knowledge_governance_invalid_document_set_returns_404():
    session = FakeAIKnowledgeSession()
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post("/governance/ai-knowledge", json={"document_set_id": str(uuid4())})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_ai_knowledge_governance_response_contains_expected_schema(monkeypatch):
    document_set = make_document_set()
    document_id = uuid4()

    def fake_search_similar_chunks(**kwargs):
        return [make_search_result(document_id=document_id) for _ in range(3)]

    monkeypatch.setattr("app.governance.ai_knowledge_service.search_similar_chunks", fake_search_similar_chunks)
    session = FakeAIKnowledgeSession(document_set=document_set)
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/governance/ai-knowledge",
            json={"document_set_id": str(document_set.id), "top_k": 20},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["document_set_id"] == str(document_set.id)
    assert body["assessment_type"] == "ai_knowledge_governance"
    assert body["overall_readiness"] in {"red", "yellow", "green"}
    assert body["confidence"] in {"high", "medium", "low"}
    assert body["executive_summary"]
    assert body["findings"]
    assert body["90_day_readiness_plan"]["days_1_30"]
    assert any("legal advice" in limitation.lower() for limitation in body["limitations"])
    assert any("local slms" in limitation.lower() for limitation in body["limitations"])

    finding = body["findings"][0]
    assert finding["readiness"] in {"red", "yellow", "green"}
    assert finding["confidence"] in {"high", "medium", "low"}
    assert "missing_evidence" in finding
    assert finding["recommended_owner"] in {
        "CTO",
        "CISO",
        "VP Engineering",
        "Data Leader",
        "Legal",
        "Compliance",
        "Product",
        "Operations",
        "Board",
    }


def test_ai_knowledge_governance_citations_are_scoped_to_document_set(monkeypatch):
    document_set = make_document_set()
    in_scope_document_id = uuid4()
    unrelated_document_id = uuid4()
    observed_document_set_ids = []

    def fake_search_similar_chunks(**kwargs):
        observed_document_set_ids.append(kwargs.get("document_set_id"))
        if kwargs.get("document_set_id") == document_set.id:
            return [make_search_result(document_id=in_scope_document_id)]
        return [make_search_result(document_id=unrelated_document_id)]

    monkeypatch.setattr("app.governance.ai_knowledge_service.search_similar_chunks", fake_search_similar_chunks)
    session = FakeAIKnowledgeSession(document_set=document_set)
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/governance/ai-knowledge",
            json={"document_set_id": str(document_set.id), "top_k": 20},
        )
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert response.status_code == 200
    assert observed_document_set_ids
    assert set(observed_document_set_ids) == {document_set.id}
    assert {citation["document_id"] for citation in body["citations"]} == {str(in_scope_document_id)}


def test_ai_knowledge_governance_mock_provider_works_without_external_api(monkeypatch):
    document_set = make_document_set()
    monkeypatch.setattr(
        "app.governance.ai_knowledge_service.search_similar_chunks",
        lambda **kwargs: [make_search_result() for _ in range(2)],
    )
    session = FakeAIKnowledgeSession(document_set=document_set)
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/governance/ai-knowledge",
            json={"document_set_id": str(document_set.id), "llm_provider": "mock"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["executive_summary"]


def test_missing_ai_usage_policy_or_classification_evidence_produces_finding():
    result = make_search_result(
        content=(
            "Teams exchange internal documents through shared folders and are considering governed retrieval. "
            "No formal rules define which knowledge can be used by AI systems."
        )
    )

    missing = missing_evidence_for_category("knowledge_classification", [result])

    assert readiness_for_category("knowledge_classification", [result]) == "red"
    assert "AI usage policy" in missing
    assert "data classification policy" in missing


def test_missing_auditability_evidence_produces_finding():
    result = make_search_result(
        content="The AI knowledge prototype can retrieve support documents, but traceability is not defined."
    )

    missing = missing_evidence_for_category("auditability", [result])

    assert readiness_for_category("auditability", [result]) == "red"
    assert "audit logging design" in missing
    assert "prompt/retrieval/output logs" in missing


def test_missing_ai_cost_tracking_produces_finding():
    result = make_search_result(
        content="The team is evaluating local model options for sensitive product knowledge."
    )

    missing = missing_evidence_for_category("cost_governance", [result])

    assert readiness_for_category("cost_governance", [result]) == "yellow"
    assert "AI cost tracking report" in missing
    assert "budget owner" in missing


def test_ai_knowledge_governance_markdown_export_includes_major_sections():
    report = {
        "document_set_id": str(uuid4()),
        "report_metadata": {
            "investigation": "SampleCo Diligence",
            "report_type": "ai_knowledge_governance",
            "provider": "Mock",
            "model": "mock",
            "generated_at": "2026-06-18 10:00",
            "document_set_id": "set-123",
            "included_documents": ["ai-readiness.pdf"],
        },
        "overall_readiness": "yellow",
        "confidence": "medium",
        "executive_summary": "SampleCo has partial AI knowledge governance readiness.",
        "top_gaps": ["Knowledge classification evidence is missing."],
        "findings": [],
        "evidence_needed": ["AI usage policy"],
        "management_questions": ["Which knowledge can use public LLMs?"],
        "board_discussion_points": ["Board should monitor AI knowledge governance."],
        "recommended_actions": ["Define AI knowledge handling rules."],
        "90_day_readiness_plan": {
            "days_1_30": ["Inventory enterprise knowledge sources."],
            "days_31_60": ["Pilot governed retrieval."],
            "days_61_90": ["Report governance status to the board."],
        },
        "limitations": [
            "This framework is not legal advice.",
            "Local SLMs and private model endpoints still require governance.",
        ],
        "citations": [],
        "llm_api_key": "secret-key",
    }

    markdown = _build_ai_knowledge_governance_markdown(report)

    for section in [
        "# AI Knowledge Governance Assessment",
        "## Executive Summary",
        "## Overall Readiness",
        "## Top Gaps",
        "## Findings",
        "## Missing Evidence",
        "## Management Questions",
        "## Board Discussion Points",
        "## Recommended Actions",
        "## 90-Day Readiness Plan",
        "## Limitations",
        "## Citations",
    ]:
        assert section in markdown
    assert "secret-key" not in markdown
