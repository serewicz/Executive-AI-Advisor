from uuid import uuid4

from fastapi.testclient import TestClient

from app.compliance.cra_scoring import missing_evidence_for_category, readiness_for_category
from app.db.dependencies import get_db
from app.main import app
from app.models.document import DocumentSet
from app.retrieval.vector_search import SearchResult
from ui.streamlit_app import _build_cra_readiness_markdown


class FakeCRAReadinessSession:
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


def make_search_result(document_id=None, content=None, title="SampleCo Security Assessment"):
    return SearchResult(
        document_id=document_id or uuid4(),
        document_title=title,
        chunk_id=uuid4(),
        chunk_index=0,
        content=content
        or (
            "The company has an incident response process and vulnerability scanning, but no formal CRA reporting "
            "runbook, SBOM, dependency inventory, or product security documentation was provided."
        ),
        page_start=1,
        page_end=2,
        similarity_score=0.82,
        source_type="technology_assessment",
        classification="confidential",
        chunk_metadata={},
    )


def test_cra_readiness_endpoint_requires_document_set_id():
    client = TestClient(app)

    response = client.post("/compliance/cra-readiness", json={"top_k": 20})

    assert response.status_code == 422


def test_cra_readiness_invalid_document_set_returns_404():
    session = FakeCRAReadinessSession()
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post("/compliance/cra-readiness", json={"document_set_id": str(uuid4())})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_cra_readiness_response_contains_expected_schema(monkeypatch):
    document_set = make_document_set()
    document_id = uuid4()

    def fake_search_similar_chunks(**kwargs):
        assert kwargs["document_set_id"] == document_set.id
        return [make_search_result(document_id=document_id) for _ in range(3)]

    monkeypatch.setattr("app.compliance.cra_service.search_similar_chunks", fake_search_similar_chunks)
    session = FakeCRAReadinessSession(document_set=document_set)
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/compliance/cra-readiness",
            json={"document_set_id": str(document_set.id), "top_k": 20},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["document_set_id"] == str(document_set.id)
    assert body["assessment_type"] == "cra_readiness"
    assert body["overall_readiness"] in {"red", "yellow", "green"}
    assert body["confidence"] in {"high", "medium", "low"}
    assert body["executive_summary"]
    assert body["findings"]
    assert body["90_day_readiness_plan"]["days_1_30"]
    assert any("legal advice" in limitation.lower() for limitation in body["limitations"])

    finding = body["findings"][0]
    assert finding["readiness"] in {"red", "yellow", "green"}
    assert finding["confidence"] in {"high", "medium", "low"}
    assert "missing_evidence" in finding
    assert finding["recommended_owner"] in {"CTO", "CISO", "VP Engineering", "Product", "Legal", "Compliance", "Board"}


def test_cra_readiness_citations_are_scoped_to_document_set(monkeypatch):
    document_set = make_document_set()
    in_scope_document_id = uuid4()
    unrelated_document_id = uuid4()

    def fake_search_similar_chunks(**kwargs):
        if kwargs["document_set_id"] == document_set.id:
            return [make_search_result(document_id=in_scope_document_id)]
        return [make_search_result(document_id=unrelated_document_id)]

    monkeypatch.setattr("app.compliance.cra_service.search_similar_chunks", fake_search_similar_chunks)
    session = FakeCRAReadinessSession(document_set=document_set)
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/compliance/cra-readiness",
            json={"document_set_id": str(document_set.id), "top_k": 20},
        )
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert {citation["document_id"] for citation in body["citations"]} == {str(in_scope_document_id)}


def test_cra_readiness_mock_provider_works_without_external_api(monkeypatch):
    document_set = make_document_set()
    monkeypatch.setattr(
        "app.compliance.cra_service.search_similar_chunks",
        lambda **kwargs: [make_search_result() for _ in range(2)],
    )
    session = FakeCRAReadinessSession(document_set=document_set)
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post(
            "/compliance/cra-readiness",
            json={"document_set_id": str(document_set.id), "llm_provider": "mock"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["executive_summary"]


def test_missing_sbom_evidence_produces_finding():
    result = make_search_result(content="The company has vulnerability scanning but no component inventory was provided.")

    assert readiness_for_category("sbom", [result]) == "red"
    assert "latest SBOM" in missing_evidence_for_category("sbom", [result])


def test_weak_incident_reporting_produces_finding(monkeypatch):
    document_set = make_document_set()
    monkeypatch.setattr(
        "app.compliance.cra_service.search_similar_chunks",
        lambda **kwargs: [
            make_search_result(content="Incident response exists, but no ENISA CSIRT reporting process is documented.")
        ],
    )
    session = FakeCRAReadinessSession(document_set=document_set)
    app.dependency_overrides[get_db] = override_db(session)

    try:
        client = TestClient(app)
        response = client.post("/compliance/cra-readiness", json={"document_set_id": str(document_set.id)})
    finally:
        app.dependency_overrides.clear()

    incident_finding = next(
        finding for finding in response.json()["findings"] if finding["category"] == "incident_reporting"
    )
    assert incident_finding["readiness"] in {"red", "yellow"}
    assert incident_finding["missing_evidence"]


def test_cra_markdown_export_includes_major_sections():
    report = {
        "document_set_id": str(uuid4()),
        "report_metadata": {
            "investigation": "SampleCo Diligence",
            "report_type": "cra_readiness",
            "provider": "Mock",
            "model": "mock",
            "generated_at": "2026-06-11 10:00",
            "document_set_id": "set-123",
            "included_documents": ["security.pdf"],
        },
        "overall_readiness": "yellow",
        "confidence": "medium",
        "executive_summary": "CRA readiness has partial evidence.",
        "top_gaps": ["SBOM evidence is missing."],
        "findings": [],
        "evidence_needed": ["latest SBOM"],
        "management_questions": ["Who owns CRA readiness?"],
        "board_discussion_points": ["Board should monitor CRA readiness."],
        "recommended_actions": ["Create SBOM process."],
        "90_day_readiness_plan": {
            "days_1_30": ["Confirm scope."],
            "days_31_60": ["Create reporting evidence."],
            "days_61_90": ["Build board roadmap."],
        },
        "limitations": ["This is not legal advice."],
        "citations": [],
        "llm_api_key": "secret-key",
    }

    markdown = _build_cra_readiness_markdown(report)

    for section in [
        "# CRA Readiness Assessment",
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
