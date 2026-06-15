from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.dependencies import get_db
from app.diligence.schemas import (
    RiskHeatmapRow,
    TechnologyDiligenceCitation,
    TechnologyDiligenceFinding,
    TechnologyDiligencePlan,
    TechnologyDiligenceReport,
)
from app.main import app
from app.planning.schemas import (
    BoardCheckpoint,
    ExecutiveOnePager,
    HundredDayPlanAction,
    HundredDayPlanResponse,
    PlanAtAGlanceRow,
    TimelineSummaryRow,
)


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
        excerpt="Evidence supports the executive module output.",
        relevance_reason="Evidence supports the finding.",
        full_source_text="Evidence supports the executive module output.",
    )


def make_finding(category, risk_rating, owner="CTO"):
    return TechnologyDiligenceFinding(
        category=category,
        title=f"{category} risk",
        risk_rating=risk_rating,
        confidence="medium",
        risk_rationale=f"{category} risk rationale.",
        confidence_rationale="Supported by cited evidence.",
        business_impact=f"{category} creates business impact.",
        evidence_summary=f"{category} evidence summary.",
        recommended_action=f"Address {category} with owner, timeline, and success metric.",
        recommended_owner=owner,
        citations=[make_citation()],
    )


def make_report(document_set_id):
    findings = [
        make_finding("security", "red", "CISO"),
        make_finding("ai_readiness", "yellow", "CTO"),
        make_finding("key_person_risk", "red", "CEO"),
        make_finding("technical_debt", "yellow", "VP Engineering"),
        make_finding("cloud_cost", "green", "CFO"),
    ]
    return TechnologyDiligenceReport(
        document_set_id=document_set_id,
        executive_summary="The company has technology risks that require board visibility and accountable owners.",
        overall_risk_rating="red",
        confidence="medium",
        risk_heatmap=[
            RiskHeatmapRow(
                category=finding.category,
                risk_rating=finding.risk_rating,
                confidence=finding.confidence,
                evidence_count=len(finding.citations),
                primary_recommended_action=finding.recommended_action,
            )
            for finding in findings
        ],
        findings=findings,
        top_5_risks=["Security and key-person risks require immediate action."],
        management_questions=["Who owns remediation?"],
        board_discussion_points=["Review technology risk progress."],
        recommended_actions=["Assign owners and timelines."],
        thirty_sixty_ninety_day_plan=TechnologyDiligencePlan(
            days_1_30=["Address red risks."],
            days_31_60=["Address yellow risks."],
            days_61_90=["Monitor green risks."],
        ),
        limitations=["Limited to selected investigation."],
        citations=[make_citation()],
    )


def install_report(monkeypatch, document_set_id):
    monkeypatch.setattr(
        "app.executive.service.generate_technology_due_diligence_report",
        lambda **kwargs: make_report(document_set_id),
    )
    app.dependency_overrides[get_db] = override_db(FakeSession())


def test_risk_scorecard_endpoint_returns_all_categories(monkeypatch):
    document_set_id = uuid4()
    install_report(monkeypatch, document_set_id)

    try:
        response = TestClient(app).post(
            "/executive/risk-scorecard",
            json={"document_set_id": str(document_set_id)},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    categories = {item["category"] for item in body["scorecard"]}
    assert categories == {
        "architecture",
        "security",
        "ai_governance",
        "data_handling",
        "cloud_infrastructure",
        "delivery_predictability",
        "key_person_risk",
        "technical_debt",
        "compliance_readiness",
    }
    security = next(item for item in body["scorecard"] if item["category"] == "security")
    assert security["status"] == "red"
    assert security["business_impact"]
    assert security["recommended_owner"] == "CISO"
    assert security["recommended_timeline"] == "Days 1-30"
    assert security["success_metric"]
    assert security["evidence"]


def test_board_brief_endpoint_returns_board_ready_structure(monkeypatch):
    document_set_id = uuid4()
    install_report(monkeypatch, document_set_id)

    try:
        response = TestClient(app).post(
            "/executive/board-brief",
            json={"document_set_id": str(document_set_id)},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["executive_summary"]
    assert len(body["top_5_technology_risks"]) == 5
    first_risk = body["top_5_technology_risks"][0]
    assert first_risk["business_impact"]
    assert first_risk["recommended_action"]
    assert body["recommended_board_level_actions"]
    assert body["key_decisions_needed"]
    assert body["questions_for_management"]
    assert body["confidence"] == "medium"
    assert body["citations"]


def test_executive_100_day_plan_endpoint_reuses_planning_pipeline(monkeypatch):
    document_set_id = uuid4()
    monkeypatch.setattr(
        "app.executive.service.generate_100_day_plan",
        lambda **kwargs: make_hundred_day_plan(document_set_id),
    )
    app.dependency_overrides[get_db] = override_db(FakeSession())

    try:
        response = TestClient(app).post(
            "/executive/100-day-plan",
            json={"document_set_id": str(document_set_id), "plan_type": "turnaround"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["plan_type"] == "turnaround"
    assert body["days_1_30"]
    assert body["days_31_60"]
    assert body["days_61_90"]
    assert body["success_metrics"]
    assert body["board_checkpoints"]


def test_ai_governance_assessment_endpoint_returns_executive_controls(monkeypatch):
    document_set_id = uuid4()
    install_report(monkeypatch, document_set_id)

    try:
        response = TestClient(app).post(
            "/executive/ai-governance-assessment",
            json={"document_set_id": str(document_set_id)},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["executive_summary"]
    assert len(body["items"]) == 9
    categories = {item["category"] for item in body["items"]}
    assert "ai_use_case_clarity" in categories
    assert "compliance_policy_readiness" in categories
    for item in body["items"]:
        assert item["maturity_level"] in {"low", "medium", "high"}
        assert item["risk_level"] in {"red", "yellow", "green"}
        assert item["business_impact"]
        assert item["recommended_next_step"]
        assert item["owner"]
        assert item["timeline"]


def make_hundred_day_plan(document_set_id):
    action = HundredDayPlanAction(
        priority="high",
        action="Assign owners for red technology risks.",
        business_rationale="Risk rationale and business impact require immediate owner accountability.",
        owner="CTO",
        risk_reduction="Reduces execution and governance risk.",
        deliverables=["Risk register with owner, due date, and board metric."],
        success_metric="Red risks have owners and dated remediation milestones.",
        citations=[make_citation()],
    )
    return HundredDayPlanResponse(
        document_set_id=document_set_id,
        plan_type="turnaround",
        overall_priority="high",
        executive_summary="100-day plan summary.",
        executive_one_pager=ExecutiveOnePager(
            executive_summary="One-pager summary.",
            current_state="Current state.",
            target_state="Target state.",
            overall_risk="Red",
            top_5_priorities=["Assign owners."],
            first_30_days=["Address red risks."],
            days_31_60=["Align priorities."],
            days_61_90=["Measure execution."],
            board_decisions_required=["Approve remediation cadence."],
            success_metrics=["Owners assigned."],
            key_dependencies=["Management evidence."],
        ),
        risk_heatmap=[
            RiskHeatmapRow(
                category="security",
                risk_rating="red",
                confidence="medium",
                evidence_count=1,
                primary_recommended_action="Address security risk.",
            )
        ],
        timeline_summary=[
            TimelineSummaryRow(
                phase="Days 1-30: Assess and stabilize",
                primary_objective="Stabilize red risks.",
                key_actions="Assign owners.",
                expected_outcomes="Risks have owners.",
                risk_reduced="Security risk.",
                board_checkpoint="30-day progress review.",
            )
        ],
        plan_at_a_glance=[
            PlanAtAGlanceRow(
                timeframe="Days 1-30",
                primary_objective="Assess and stabilize",
                key_actions="Assign owners.",
                success_measures="Owners assigned.",
                risk_reduced="Red risk.",
            )
        ],
        days_1_30=[action],
        days_31_60=[action],
        days_61_90=[action],
        days_91_100=[action],
        success_metrics=["Owners assigned."],
        board_checkpoints=[
            BoardCheckpoint(
                timeframe="30 days",
                question="Are red risks assigned?",
                evidence_requested="Risk register.",
                decision_needed="Approve cadence.",
            )
        ],
        dependencies=["Management evidence."],
        limitations=["Limited to selected investigation."],
    )
