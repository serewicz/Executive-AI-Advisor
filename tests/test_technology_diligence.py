from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.dependencies import get_db
from app.diligence.schemas import TechnologyDiligenceCitation, TechnologyDiligenceFinding
from app.diligence.scoring import (
    confidence_for_technology_results,
    confidence_rationale_for_results,
    risk_rating_for_category,
    risk_rationale_for_category,
)
from app.diligence.service import build_risk_heatmap
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


def make_technology_citation(index=1):
    return TechnologyDiligenceCitation(
        source_label=f"S{index}",
        document_id=uuid4(),
        document_title="Technology Assessment",
        chunk_id=uuid4(),
        page_start=index,
        page_end=index,
        excerpt="Evidence excerpt.",
        relevance_reason="Supports the heatmap row.",
        full_source_text="Evidence excerpt.",
    )


def make_technology_finding(category, risk_rating, confidence, citation_count):
    return TechnologyDiligenceFinding(
        category=category,
        title=f"{category} finding",
        risk_rating=risk_rating,
        confidence=confidence,
        risk_rationale=f"{category} risk rationale.",
        confidence_rationale=f"{category} confidence rationale.",
        business_impact=f"{category} business impact.",
        evidence_summary=f"{category} evidence summary.",
        recommended_action=f"Remediate {category}.",
        recommended_owner="CTO",
        citations=[make_technology_citation(index) for index in range(1, citation_count + 1)],
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
    assert body["risk_heatmap"]
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
    assert finding["risk_rationale"]
    assert finding["confidence_rationale"]
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
        "risk_heatmap": [
            {
                "category": "security",
                "risk_rating": "yellow",
                "confidence": "medium",
                "evidence_count": 2,
                "primary_recommended_action": "Validate security controls.",
            }
        ],
        "top_5_risks": ["Security governance requires validation."],
        "findings": [
            {
                "category": "security",
                "title": "Moderate Security Risk",
                "risk_rating": "yellow",
                "confidence": "medium",
                "risk_rationale": "Incomplete security governance indicates moderate risk.",
                "confidence_rationale": "Medium confidence because one citation provides direct evidence.",
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
    assert "## Executive Risk Heatmap" in markdown
    assert "## Top 5 Risks" in markdown
    assert "## Findings" in markdown
    assert "## Management Questions" in markdown
    assert "## Board Discussion Points" in markdown
    assert "## Recommended Actions" in markdown
    assert "## 30/60/90-Day Plan" in markdown
    assert "## Limitations" in markdown
    assert "## Citations" in markdown


def test_risk_heatmap_aggregates_category_findings():
    findings = [
        make_technology_finding("architecture", "red", "high", citation_count=3),
        make_technology_finding("security", "yellow", "medium", citation_count=2),
        make_technology_finding("cloud_cost", "green", "low", citation_count=0),
    ]

    heatmap = build_risk_heatmap(findings)

    assert [row.category for row in heatmap] == ["architecture", "security", "cloud_cost"]
    assert [row.risk_rating for row in heatmap] == ["red", "yellow", "green"]
    assert [row.confidence for row in heatmap] == ["high", "medium", "low"]
    assert [row.evidence_count for row in heatmap] == [3, 2, 0]
    assert heatmap[0].primary_recommended_action == "Remediate architecture."


def test_founder_dependency_scores_red_with_medium_confidence():
    result = make_search_result(
        content="Founder dependency and key person dependency concentrate production knowledge in one executive."
    )

    assert risk_rating_for_category("key_person_risk", [result]) == "red"
    assert confidence_for_technology_results([result]) == "medium"
    assert "material key person risk" in risk_rationale_for_category("key_person_risk", [result])


def test_manual_deployment_scores_red():
    result = make_search_result(
        content="Manual production deployment creates release risk and a single point of failure."
    )

    assert risk_rating_for_category("architecture", [result]) == "red"


def test_incomplete_documentation_scores_yellow():
    result = make_search_result(content="Incomplete documentation slows onboarding and operational handoff.")

    assert risk_rating_for_category("technical_debt", [result]) == "yellow"


def test_cloud_cost_visibility_gap_scores_yellow():
    result = make_search_result(content="Cloud cost visibility gaps make AWS spend harder to allocate by customer.")

    assert risk_rating_for_category("cloud_cost", [result]) == "yellow"


def test_adequate_monitoring_controls_score_green():
    result = make_search_result(content="Strong monitoring and documented controls support reliable operations.")

    assert risk_rating_for_category("security", [result]) == "green"


def test_weak_evidence_scores_low_confidence():
    result = make_search_result(content="The team discussed future improvements.")

    assert confidence_for_technology_results([result]) == "low"
    assert "weak, indirect, or inferred" in confidence_rationale_for_results([result])


def test_three_relevant_citations_score_high_confidence():
    results = [
        make_search_result(content="Incomplete documentation affects operational handoff."),
        make_search_result(content="Technical debt slows roadmap delivery."),
        make_search_result(content="Partial test coverage increases regression risk."),
    ]

    assert confidence_for_technology_results(results) == "high"
