from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.dependencies import get_db
from app.main import app
from app.models.document import DocumentSet
from app.retrieval.vector_search import SearchResult
from ui.streamlit_app import _build_technology_report_markdown


class FakeTechnologyDiligenceSession:
    def __init__(self, document_set=None):
        self.document_set = document_set

    def get(self, model, object_id):
        if model is DocumentSet and self.document_set is not None and self.document_set.id == object_id:
            return self.document_set
        return None


def make_document_set():
    return DocumentSet(id=uuid4(), name="SampleCo Diligence", description="Synthetic diligence package")


def make_search_result(document_id=None, content=None):
    return SearchResult(
        document_id=document_id or uuid4(),
        document_title="SampleCo Technology Assessment",
        chunk_id=uuid4(),
        chunk_index=0,
        content=content
        or (
            "SampleCo has incomplete security governance, manual cloud cost management, "
            "technical debt, VP Engineering key person dependency, and AI governance gaps."
        ),
        page_start=1,
        page_end=2,
        similarity_score=0.82,
        source_type="technology_assessment",
        classification="confidential",
        chunk_metadata={},
    )


def override_db(session):
    def _override_db():
        yield session

    return _override_db


def test_technology_report_endpoint_requires_document_set_id():
    client = TestClient(app)

    response = client.post("/diligence/technology-report", json={"top_k": 20})

    assert response.status_code == 422


def test_technology_report_invalid_document_set_returns_404():
    session = FakeTechnologyDiligenceSession()
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/diligence/technology-report",
            json={"document_set_id": str(uuid4())},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_technology_report_returns_expected_schema(monkeypatch):
    document_set = make_document_set()
    document_id = uuid4()

    def fake_search_similar_chunks(**kwargs):
        assert kwargs["document_set_id"] == document_set.id
        return [make_search_result(document_id=document_id) for _ in range(3)]

    monkeypatch.setattr("app.diligence.service.search_similar_chunks", fake_search_similar_chunks)
    session = FakeTechnologyDiligenceSession(document_set=document_set)
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/diligence/technology-report",
            json={
                "document_set_id": str(document_set.id),
                "top_k": 20,
                "include_100_day_plan": True,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["document_set_id"] == str(document_set.id)
    assert body["report_type"] == "technology_due_diligence"
    assert body["executive_summary"]
    assert body["overall_risk_rating"] in {"red", "yellow", "green"}
    assert body["confidence"] in {"high", "medium", "low"}
    assert body["findings"]
    assert body["top_5_risks"]
    assert body["management_questions"]
    assert body["board_discussion_points"]
    assert body["recommended_actions"]
    assert body["thirty_sixty_ninety_day_plan"]["days_1_30"]
    assert body["limitations"]
    assert body["citations"]


def test_technology_report_findings_include_risk_rating_and_confidence(monkeypatch):
    document_set = make_document_set()
    monkeypatch.setattr(
        "app.diligence.service.search_similar_chunks",
        lambda **kwargs: [make_search_result() for _ in range(2)],
    )
    session = FakeTechnologyDiligenceSession(document_set=document_set)
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/diligence/technology-report",
            json={"document_set_id": str(document_set.id), "top_k": 20},
        )
    finally:
        app.dependency_overrides.clear()

    finding = response.json()["findings"][0]
    assert finding["risk_rating"] in {"red", "yellow", "green"}
    assert finding["confidence"] in {"high", "medium", "low"}
    assert finding["citations"]


def test_technology_report_citations_are_scoped_to_document_set(monkeypatch):
    document_set = make_document_set()
    in_scope_document_id = uuid4()
    unrelated_document_id = uuid4()

    def fake_search_similar_chunks(**kwargs):
        if kwargs["document_set_id"] == document_set.id:
            return [make_search_result(document_id=in_scope_document_id) for _ in range(2)]
        return [make_search_result(document_id=unrelated_document_id)]

    monkeypatch.setattr("app.diligence.service.search_similar_chunks", fake_search_similar_chunks)
    session = FakeTechnologyDiligenceSession(document_set=document_set)
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/diligence/technology-report",
            json={"document_set_id": str(document_set.id), "top_k": 20},
        )
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert {citation["document_id"] for citation in body["citations"]} == {str(in_scope_document_id)}


def test_technology_report_top_k_validation():
    client = TestClient(app)

    low_response = client.post(
        "/diligence/technology-report",
        json={"document_set_id": str(uuid4()), "top_k": 4},
    )
    high_response = client.post(
        "/diligence/technology-report",
        json={"document_set_id": str(uuid4()), "top_k": 41},
    )

    assert low_response.status_code == 422
    assert high_response.status_code == 422


def test_technology_report_markdown_export_includes_main_sections():
    report = {
        "document_set_id": str(uuid4()),
        "report_type": "technology_due_diligence",
        "executive_summary": "SampleCo has moderate technology diligence risk.",
        "overall_risk_rating": "yellow",
        "confidence": "medium",
        "top_5_risks": ["Security governance requires validation."],
        "findings": [
            {
                "category": "security",
                "title": "Moderate Security Risk",
                "risk_rating": "yellow",
                "confidence": "medium",
                "recommended_owner": "CISO",
                "business_impact": "Security gaps may affect enterprise trust.",
                "evidence_summary": "Evidence was retrieved from security documents.",
                "recommended_action": "Validate security controls.",
                "citations": [],
            }
        ],
        "management_questions": ["What security evidence exists?"],
        "board_discussion_points": ["Discuss security governance."],
        "recommended_actions": ["CISO: Validate controls."],
        "thirty_sixty_ninety_day_plan": {
            "days_1_30": ["Validate evidence."],
            "days_31_60": ["Create remediation plan."],
            "days_61_90": ["Track progress."],
        },
        "limitations": ["Limited to selected investigation."],
        "citations": [],
    }

    markdown = _build_technology_report_markdown(report)

    assert "# Technology Due Diligence Report" in markdown
    assert "## Executive Summary" in markdown
    assert "## Overall Risk Rating" in markdown
    assert "## Top 5 Risks" in markdown
    assert "## Findings" in markdown
    assert "## Management Questions" in markdown
    assert "## Board Discussion Points" in markdown
    assert "## Recommended Actions" in markdown
    assert "## 30/60/90-Day Plan" in markdown
    assert "## Limitations" in markdown
    assert "## Citations" in markdown
