from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.dependencies import get_db
from app.diligence.schemas import (
    TechnologyDiligenceCitation,
    TechnologyDiligenceFinding,
    TechnologyDiligencePlan,
    TechnologyDiligenceReport,
)
from app.main import app
from app.planning.service import generate_100_day_plan
from ui.streamlit_app import _build_hundred_day_plan_markdown


class FakeSession:
    pass


def override_db(session):
    def _override_db():
        yield session

    return _override_db


def make_citation():
    return TechnologyDiligenceCitation(
        source_label="S1",
        document_id=uuid4(),
        document_title="Technology Assessment",
        chunk_id=uuid4(),
        page_start=1,
        page_end=2,
        excerpt="Manual production deployment and key-person dependency require remediation.",
        relevance_reason="Evidence supports the plan action.",
        full_source_text="Manual production deployment and key-person dependency require remediation.",
    )


def make_finding(category, risk_rating, recommended_owner="CTO"):
    return TechnologyDiligenceFinding(
        category=category,
        title=f"{category} finding",
        risk_rating=risk_rating,
        confidence="medium",
        risk_rationale=f"{category} rationale",
        confidence_rationale="Supported by direct evidence.",
        business_impact=f"{category} business impact.",
        evidence_summary=f"{category} evidence summary.",
        recommended_action=f"Remediate {category}.",
        recommended_owner=recommended_owner,
        citations=[make_citation()],
    )


def make_report(document_set_id):
    return TechnologyDiligenceReport(
        document_set_id=document_set_id,
        executive_summary="Technology diligence report summary.",
        overall_risk_rating="red",
        confidence="medium",
        findings=[
            make_finding("key_person_risk", "red", "CEO"),
            make_finding("cloud_cost", "yellow", "CFO"),
            make_finding("security", "green", "CISO"),
        ],
        top_5_risks=["Key person risk requires immediate action."],
        management_questions=["Who owns remediation?"],
        board_discussion_points=["Review risk progress."],
        recommended_actions=["Assign owners."],
        thirty_sixty_ninety_day_plan=TechnologyDiligencePlan(
            days_1_30=["Address red risks."],
            days_31_60=["Address yellow risks."],
            days_61_90=["Monitor green risks."],
        ),
        limitations=["Limited to selected investigation."],
        citations=[make_citation()],
    )


def test_100_day_plan_endpoint_works(monkeypatch):
    document_set_id = uuid4()
    monkeypatch.setattr(
        "app.planning.service.generate_technology_due_diligence_report",
        lambda **kwargs: make_report(document_set_id),
    )
    app.dependency_overrides[get_db] = override_db(FakeSession())

    try:
        client = TestClient(app)
        response = client.post(
            "/diligence/100-day-plan",
            json={"document_set_id": str(document_set_id), "plan_type": "growth_equity"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["document_set_id"] == str(document_set_id)
    assert body["plan_type"] == "growth_equity"
    assert body["overall_priority"] == "high"
    assert body["days_1_30"]
    assert body["days_31_60"]
    assert body["days_61_90"]


def test_100_day_plan_document_set_required():
    client = TestClient(app)

    response = client.post("/diligence/100-day-plan", json={"plan_type": "growth_equity"})

    assert response.status_code == 422


def test_100_day_plan_plan_type_validation():
    client = TestClient(app)

    response = client.post(
        "/diligence/100-day-plan",
        json={"document_set_id": str(uuid4()), "plan_type": "unsupported"},
    )

    assert response.status_code == 422


def test_100_day_plan_prioritizes_risks(monkeypatch):
    document_set_id = uuid4()
    monkeypatch.setattr(
        "app.planning.service.generate_technology_due_diligence_report",
        lambda **kwargs: make_report(document_set_id),
    )

    plan = generate_100_day_plan(
        document_set_id=document_set_id,
        plan_type="acquisition_integration",
        db=FakeSession(),
    )

    assert "key person risk" in plan.days_1_30[0].action
    assert "cloud cost" in plan.days_31_60[0].action
    assert "security" in plan.days_61_90[0].action
    assert plan.days_1_30[0].priority == "high"
    assert plan.days_31_60[0].priority == "medium"
    assert plan.days_61_90[0].priority == "low"


def test_100_day_plan_actions_include_citations(monkeypatch):
    document_set_id = uuid4()
    monkeypatch.setattr(
        "app.planning.service.generate_technology_due_diligence_report",
        lambda **kwargs: make_report(document_set_id),
    )

    plan = generate_100_day_plan(
        document_set_id=document_set_id,
        plan_type="turnaround",
        db=FakeSession(),
    )

    assert plan.days_1_30[0].citations


def test_100_day_plan_markdown_export_works(monkeypatch):
    document_set_id = uuid4()
    monkeypatch.setattr(
        "app.planning.service.generate_technology_due_diligence_report",
        lambda **kwargs: make_report(document_set_id),
    )
    plan = generate_100_day_plan(
        document_set_id=document_set_id,
        plan_type="growth_equity",
        db=FakeSession(),
    )

    markdown = _build_hundred_day_plan_markdown(plan.model_dump(mode="json"))

    assert "# 100-Day Technology Plan" in markdown
    assert "## Executive Summary" in markdown
    assert "## Days 1-30" in markdown
    assert "## Days 31-60" in markdown
    assert "## Days 61-90" in markdown
    assert "## Success Metrics" in markdown
    assert "## Board Checkpoints" in markdown
    assert "## Dependencies" in markdown
    assert "## Limitations" in markdown
