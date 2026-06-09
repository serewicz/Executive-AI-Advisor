from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.dependencies import get_db
from app.diligence.schemas import (
    TechnologyDiligenceCitation,
    TechnologyDiligenceFinding,
    TechnologyDiligencePlan,
    TechnologyDiligenceReport,
    RiskHeatmapRow,
)
from app.main import app
from app.planning.service import generate_100_day_plan
from ui.streamlit_app import _build_hundred_day_one_pager_markdown, _build_hundred_day_plan_markdown


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
    findings = [
        make_finding("key_person_risk", "red", "CEO"),
        make_finding("cloud_cost", "yellow", "CFO"),
        make_finding("security", "green", "CISO"),
    ]
    return TechnologyDiligenceReport(
        document_set_id=document_set_id,
        executive_summary="Technology diligence report summary.",
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
    assert body["executive_one_pager"]["executive_summary"]
    assert body["executive_one_pager"]["top_5_priorities"]
    assert body["risk_heatmap"]
    assert body["plan_at_a_glance"]
    assert body["days_1_30"]
    assert body["days_31_60"]
    assert body["days_61_90"]
    assert body["days_91_100"]
    assert body["board_checkpoints"][0]["question"]
    assert body["board_checkpoints"][0]["evidence_requested"]


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

    assert any("key person risk" in action.action for action in plan.days_1_30)
    assert any("cloud cost" in action.action for action in plan.days_31_60)
    assert any("security" in action.action for action in plan.days_61_90)
    assert all(action.priority == "high" for action in plan.days_1_30)
    assert all(action.priority == "medium" for action in plan.days_31_60)
    assert all(action.priority == "low" for action in plan.days_61_90)


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


def test_100_day_plan_actions_include_deliverables_and_success_metric(monkeypatch):
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

    all_actions = [*plan.days_1_30, *plan.days_31_60, *plan.days_61_90, *plan.days_91_100]
    assert all(action.deliverables for action in all_actions)
    assert all(action.success_metric for action in all_actions)


def test_100_day_plan_rejects_generic_business_rationale_language(monkeypatch):
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

    generic_phrases = [
        "supports growth equity",
        "supports acquisition integration",
        "supports turnaround",
        "improves technology posture",
        "supports the growth equity focus",
        "supports the acquisition integration focus",
    ]
    all_actions = [*plan.days_1_30, *plan.days_31_60, *plan.days_61_90, *plan.days_91_100]
    rationales = [action.business_rationale.lower() for action in all_actions]

    assert not any(phrase in rationale for phrase in generic_phrases for rationale in rationales)
    assert any("business impact" in rationale for rationale in rationales)
    assert any("risk rationale" in rationale for rationale in rationales)


def test_100_day_plan_deliverables_are_concrete_and_verifiable(monkeypatch):
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

    weak_phrases = [
        "define scope and owner",
        "create milestone plan",
        "identify evidence required",
        "publish status metric",
    ]
    all_actions = [*plan.days_1_30, *plan.days_31_60, *plan.days_61_90, *plan.days_91_100]
    deliverables = [deliverable.lower() for action in all_actions for deliverable in action.deliverables]

    assert not any(phrase in deliverable for phrase in weak_phrases for deliverable in deliverables)
    assert any("register" in deliverable for deliverable in deliverables)
    assert any("owner" in deliverable for deliverable in deliverables)
    assert any("due date" in deliverable or "launch date" in deliverable for deliverable in deliverables)


def test_100_day_plan_owner_assignments_are_varied(monkeypatch):
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

    all_actions = [*plan.days_1_30, *plan.days_31_60, *plan.days_61_90, *plan.days_91_100]
    owners = {action.owner for action in all_actions}

    assert len(owners) >= 5
    assert "CTO" in owners
    assert "Finance" in owners
    assert "CISO / Security Lead" in owners
    assert "Engineering Manager" in owners
    assert len([action for action in all_actions if action.owner == "CTO"]) < len(all_actions)


def test_turnaround_plan_includes_quick_wins_and_stabilization_language(monkeypatch):
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

    assert plan.quick_wins
    assert any("Freeze non-critical technology spend" in win for win in plan.quick_wins)
    assert "stop uncontrolled technology spend" in plan.executive_summary
    assert any("Freeze non-critical technology spend" in action.action for action in plan.days_1_30)


def test_growth_equity_plan_includes_scaling_and_delivery_predictability(monkeypatch):
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

    assert "improve delivery predictability" in plan.executive_summary
    assert any("feature flag" in action.action.lower() for action in plan.days_1_30)
    assert any("architecture scalability review" in action.action.lower() for action in plan.days_31_60)
    assert any("Deployment frequency improves" in metric for metric in plan.success_metrics)


def test_acquisition_integration_plan_includes_acquirer_coordination(monkeypatch):
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

    assert "transfer critical knowledge" in plan.executive_summary
    assert any("acquirer" in action.action.lower() for action in plan.days_1_30)
    assert any("Knowledge transfer" in metric for metric in plan.success_metrics)
    assert any("acquirer-side" in dependency for dependency in plan.dependencies)


def test_plan_at_a_glance_and_board_checkpoints_are_structured(monkeypatch):
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

    assert len(plan.plan_at_a_glance) == 4
    assert plan.plan_at_a_glance[0].timeframe == "Days 1-30"
    assert all(checkpoint.question for checkpoint in plan.board_checkpoints)
    assert all(checkpoint.evidence_requested for checkpoint in plan.board_checkpoints)
    assert all(checkpoint.decision_needed for checkpoint in plan.board_checkpoints)


def test_executive_one_pager_exists_for_all_plan_types(monkeypatch):
    document_set_id = uuid4()
    monkeypatch.setattr(
        "app.planning.service.generate_technology_due_diligence_report",
        lambda **kwargs: make_report(document_set_id),
    )

    for plan_type in ["growth_equity", "acquisition_integration", "turnaround"]:
        plan = generate_100_day_plan(
            document_set_id=document_set_id,
            plan_type=plan_type,
            db=FakeSession(),
        )

        one_pager = plan.executive_one_pager
        assert one_pager.executive_summary
        assert one_pager.current_state
        assert one_pager.target_state
        assert one_pager.overall_risk
        assert one_pager.top_5_priorities
        assert one_pager.first_30_days
        assert one_pager.days_31_60
        assert one_pager.days_61_90
        assert one_pager.board_decisions_required
        assert one_pager.success_metrics
        assert one_pager.key_dependencies


def test_executive_one_pager_is_concise_and_board_readable(monkeypatch):
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

    one_pager = plan.executive_one_pager

    assert len(one_pager.executive_summary) <= 520
    assert len(one_pager.top_5_priorities) <= 5
    assert len(one_pager.first_30_days) <= 5
    assert "Current" not in one_pager.executive_summary


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
    assert "## Executive Risk Heatmap" in markdown
    assert "## Days 1-30" in markdown
    assert "## Days 31-60" in markdown
    assert "## Days 61-90" in markdown
    assert "## Days 91-100 / Board Readout" in markdown
    assert "## 100-Day Plan at a Glance" in markdown
    assert "## Success Metrics" in markdown
    assert "## Board Checkpoints" in markdown
    assert "## Dependencies" in markdown
    assert "## Limitations" in markdown


def test_100_day_plan_one_pager_markdown_export_works(monkeypatch):
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

    markdown = _build_hundred_day_one_pager_markdown(plan.model_dump(mode="json"))

    assert "# Executive One-Pager: 100-Day Technology Plan" in markdown
    assert "## Executive Summary" in markdown
    assert "## Current State" in markdown
    assert "## Target State" in markdown
    assert "## Overall Risk" in markdown
    assert "## Executive Risk Heatmap" in markdown
    assert "## Top 5 Priorities" in markdown
    assert "## First 30 Days" in markdown
    assert "## Days 31-60" in markdown
    assert "## Days 61-90" in markdown
    assert "## Board Decisions Required" in markdown
    assert "## Success Metrics" in markdown
    assert "## Key Dependencies" in markdown


def test_100_day_plan_markdown_includes_quick_wins_for_turnaround(monkeypatch):
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

    markdown = _build_hundred_day_plan_markdown(plan.model_dump(mode="json"))

    assert "## Quick Wins" in markdown
    assert "Freeze non-critical technology spend" in markdown
