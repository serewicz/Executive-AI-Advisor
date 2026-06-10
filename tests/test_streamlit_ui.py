import streamlit as st

from ui.streamlit_app import (
    _build_hundred_day_plan_markdown,
    _build_technology_report_markdown,
    _build_qa_payload,
    _all_documents_ready,
    _clear_local_ui_state,
    _download_key,
    _evaluation_missing_requirements,
    _evaluation_questions_from_text,
    _evaluation_questions_to_text,
    _evaluation_ready_documents,
    _export_filename,
    _processing_status_rows,
    _risk_counts,
    _remove_document_from_local_state,
    _sync_active_document_set_state,
    build_export_filename,
    get_processing_summary,
    render_confidence_badge,
    render_risk_badge,
)


def setup_function():
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def test_qa_payload_includes_document_id_by_default_if_selected():
    payload = _build_qa_payload(
        question="What are the main technology risks?",
        top_k=5,
        document_id="document-123",
        search_globally=False,
    )

    assert payload["document_id"] == "document-123"


def test_qa_payload_omits_document_id_when_global_search_selected():
    payload = _build_qa_payload(
        question="What are the main technology risks?",
        top_k=5,
        document_id="document-123",
        search_globally=True,
    )

    assert "document_id" not in payload


def test_qa_payload_prefers_document_set_scope():
    payload = _build_qa_payload(
        question="What are the main technology risks?",
        top_k=5,
        document_id="document-123",
        document_set_id="set-456",
        search_globally=False,
    )

    assert payload["document_set_id"] == "set-456"
    assert "document_id" not in payload


def test_sync_active_document_set_removes_stale_document_ids():
    st.session_state.document_id = "stale-document"
    st.session_state.active_document_id = "stale-document"
    st.session_state.summary_document_id = "stale-document"
    st.session_state.selected_documents = ["stale-document", "valid-document"]
    st.session_state.uploaded_documents = [{"document_id": "stale-document"}]

    _sync_active_document_set_state(
        {
            "document_set_id": "set-123",
            "name": "SampleCo Diligence",
            "documents": [
                {
                    "document_id": "valid-document",
                    "filename": "sampleco.pdf",
                    "status": "uploaded",
                }
            ],
        }
    )

    assert st.session_state.document_id == "valid-document"
    assert st.session_state.active_document_id == "valid-document"
    assert st.session_state.summary_document_id == "valid-document"
    assert st.session_state.selected_documents == ["valid-document"]
    assert st.session_state.uploaded_documents[0]["document_id"] == "valid-document"


def test_remove_document_from_local_state_clears_cached_results():
    st.session_state.document_id = "document-123"
    st.session_state.active_document_id = "document-123"
    st.session_state.summary_document_id = "document-123"
    st.session_state.selected_documents = ["document-123"]
    st.session_state.uploaded_documents = [{"document_id": "document-123"}]
    st.session_state.qa_response = {"answer": "stale"}
    st.session_state.board_summary = {"memo": "stale"}
    st.session_state.evaluation_response = {"results": []}

    _remove_document_from_local_state("document-123")

    assert st.session_state.document_id == ""
    assert st.session_state.active_document_id == ""
    assert st.session_state.summary_document_id == ""
    assert st.session_state.selected_documents == []
    assert st.session_state.uploaded_documents == []
    assert st.session_state.qa_response is None
    assert st.session_state.board_summary is None
    assert st.session_state.evaluation_response is None


def test_clear_local_ui_state_does_not_require_backend_delete():
    st.session_state.active_document_set_id = "set-123"
    st.session_state.document_id = "document-123"
    st.session_state.uploaded_documents = [{"document_id": "document-123"}]
    st.session_state.selected_documents = ["document-123"]
    st.session_state.qa_response = {"answer": "stale"}
    st.session_state.evaluation_questions_text = "stale"
    st.session_state.evaluation_questions_initialized = True

    _clear_local_ui_state()

    assert st.session_state.active_document_set_id == ""
    assert st.session_state.document_id == ""
    assert st.session_state.uploaded_documents == []
    assert st.session_state.selected_documents == []
    assert st.session_state.qa_response is None
    assert st.session_state.evaluation_questions_text == ""
    assert st.session_state.evaluation_questions_initialized is False


def test_evaluation_questions_round_trip_defaults_to_editable_text():
    default_questions = [
        {"question": "What cybersecurity risks are disclosed?", "expected_themes": ["security"]},
        {"question": "What should the board monitor?", "expected_themes": ["board"]},
    ]

    question_text = _evaluation_questions_to_text(default_questions)
    questions = _evaluation_questions_from_text(question_text, default_questions)

    assert "What cybersecurity risks are disclosed?" in question_text
    assert questions == default_questions


def test_evaluation_questions_from_text_accepts_custom_questions():
    questions = _evaluation_questions_from_text(
        "What matters most?\n\nWhat should the board monitor?",
        [{"question": "What should the board monitor?", "expected_themes": ["board"]}],
    )

    assert questions == [
        {"question": "What matters most?", "expected_themes": None},
        {"question": "What should the board monitor?", "expected_themes": ["board"]},
    ]


def test_evaluation_ready_documents_filters_unprocessed_documents():
    documents = [
        {"document_id": "uploaded", "status": "uploaded"},
        {"document_id": "chunked", "status": "chunked"},
        {"document_id": "embedded", "status": "embedded"},
    ]

    ready_documents = _evaluation_ready_documents(documents)

    assert [document["document_id"] for document in ready_documents] == ["chunked", "embedded"]


def test_evaluation_missing_requirements_reports_exact_blockers():
    missing = _evaluation_missing_requirements(
        scope="Active Investigation / Document Set",
        document_id="",
        questions=[],
        active_document_set_id="",
        available_documents=[],
    )

    assert "Select or create an investigation." in missing
    assert "Upload and process at least one document." in missing
    assert "Enter at least one evaluation question." in missing


def test_risk_and_confidence_badges_render_executive_labels():
    assert "Risk: Red" in render_risk_badge("red")
    assert "Risk: Yellow" in render_risk_badge("yellow")
    assert "Risk: Green" in render_risk_badge("green")
    assert "High Confidence" in render_confidence_badge("high")
    assert "Medium Confidence" in render_confidence_badge("medium")
    assert "Low Confidence" in render_confidence_badge("low")


def test_risk_counts_summarize_findings():
    counts = _risk_counts(
        [
            {"risk_rating": "red"},
            {"risk_rating": "yellow"},
            {"risk_rating": "yellow"},
            {"risk_rating": "green"},
            {"risk_rating": "unknown"},
        ]
    )

    assert counts == {"red": 1, "yellow": 2, "green": 1}


def test_processing_status_rows_show_text_lifecycle_labels():
    rows = _processing_status_rows(
        [
            {"document_id": "a1b2c3d4-1111", "filename": "01-executive-summary.pdf", "status": "embedded"},
            {"document_id": "e5f6g7h8-2222", "filename": "02-technology-assessment.pdf", "status": "uploaded"},
            {
                "document_id": "f1f2f3f4-3333",
                "filename": "03-security-assessment.pdf",
                "status": "failed",
                "error": "Chunking error",
            },
        ]
    )

    assert rows == [
        {
            "File": "01-executive-summary.pdf",
            "ID": "a1b2c3d4",
            "Status": "Embedded",
            "Ready?": "Yes",
            "Notes": "Ready",
        },
        {
            "File": "02-technology-assessment.pdf",
            "ID": "e5f6g7h8",
            "Status": "Uploaded",
            "Ready?": "No",
            "Notes": "Needs processing",
        },
        {
            "File": "03-security-assessment.pdf",
            "ID": "f1f2f3f4",
            "Status": "Failed",
            "Ready?": "No",
            "Notes": "Chunking error",
        },
    ]


def test_processing_summary_prioritizes_failed_documents():
    summary = get_processing_summary(
        [
            {"status": "embedded"},
            {"status": "failed"},
        ]
    )

    assert summary.status_level == "error"
    assert summary.status_message == "One or more documents failed. Review the Notes column."
    assert summary.has_failed is True


def test_processing_summary_reports_complete_when_all_ready():
    summary = get_processing_summary(
        [
            {"status": "embedded"},
            {"status": "indexed"},
        ]
    )

    assert summary.status_level == "success"
    assert "Processing complete" in summary.status_message
    assert summary.all_ready is True


def test_processing_summary_reports_pending_without_complete_message():
    summary = get_processing_summary(
        [
            {"status": "embedded"},
            {"status": "uploaded"},
        ]
    )

    assert summary.status_level == "info"
    assert summary.status_message == "Some documents still need processing."
    assert summary.has_pending is True
    assert summary.all_ready is False
    assert "Processing complete" not in summary.status_message


def test_processing_summary_reports_no_documents():
    summary = get_processing_summary([])

    assert summary.total_documents == 0
    assert summary.status_message == "No documents uploaded."
    assert summary.status_level == "info"


def test_processing_rows_keep_duplicate_filenames_when_ids_differ():
    rows = _processing_status_rows(
        [
            {"document_id": "11111111-aaaa", "filename": "assessment.pdf", "status": "embedded"},
            {"document_id": "22222222-bbbb", "filename": "assessment.pdf", "status": "uploaded"},
        ]
    )

    assert len(rows) == 2
    assert rows[0]["ID"] == "11111111"
    assert rows[1]["ID"] == "22222222"


def test_processing_rows_drop_duplicate_document_ids():
    rows = _processing_status_rows(
        [
            {"document_id": "11111111-aaaa", "filename": "assessment.pdf", "status": "embedded"},
            {"document_id": "11111111-aaaa", "filename": "assessment.pdf", "status": "uploaded"},
        ]
    )

    assert len(rows) == 1
    assert rows[0]["Status"] == "Embedded"


def test_all_documents_ready_only_for_embedded_or_indexed_documents():
    assert _all_documents_ready([{"status": "embedded"}, {"status": "indexed"}]) is True
    assert _all_documents_ready([{"status": "embedded"}, {"status": "uploaded"}]) is False
    assert _all_documents_ready([]) is False


def test_export_filename_sanitizes_investigation_and_variant():
    filename = build_export_filename("SampleCo Diligence / Q2", "100 day plan", "growth equity")

    assert filename.startswith("SampleCo_Diligence_Q2_100_day_plan_growth_equity_")
    assert filename.endswith(".md")
    assert "/" not in filename


def test_export_filename_differs_by_plan_type():
    growth = build_export_filename("AcquisitionTargetCo", "100_day_plan", "growth_equity")
    turnaround = build_export_filename("AcquisitionTargetCo", "100_day_plan", "turnaround")

    assert growth != turnaround
    assert "growth_equity" in growth
    assert "turnaround" in turnaround


def test_markdown_export_metadata_excludes_api_keys():
    report = {
        "document_set_id": "set-123",
        "report_metadata": {
            "investigation": "SampleCo Diligence",
            "report_type": "technology_due_diligence",
            "provider": "OpenAI",
            "model": "gpt-4o-mini",
            "generated_at": "2026-06-10 14:32",
            "document_set_id": "set-123",
            "included_documents": ["technology.pdf"],
        },
        "executive_summary": "SampleCo has moderate diligence risk.",
        "overall_risk_rating": "yellow",
        "confidence": "medium",
        "risk_heatmap": [],
        "top_5_risks": [],
        "findings": [],
        "management_questions": [],
        "board_discussion_points": [],
        "recommended_actions": [],
        "thirty_sixty_ninety_day_plan": {},
        "limitations": [],
        "citations": [],
        "llm_api_key": "sk-secret",
        "openai_api_key": "sk-secret",
    }

    markdown = _build_technology_report_markdown(report)

    assert "- Investigation: SampleCo Diligence" in markdown
    assert "- Provider: OpenAI" in markdown
    assert "- Model: gpt-4o-mini" in markdown
    assert "technology.pdf" in markdown
    assert "sk-secret" not in markdown


def test_hundred_day_markdown_export_uses_plan_metadata_without_keys():
    plan = {
        "document_set_id": "set-123",
        "plan_type": "turnaround",
        "report_metadata": {
            "investigation": "AcquisitionTargetCo Diligence",
            "report_type": "100_day_plan",
            "plan_type": "turnaround",
            "provider": "Anthropic",
            "model": "claude-3-5-sonnet-latest",
            "generated_at": "2026-06-10 14:32",
            "document_set_id": "set-123",
            "included_documents": ["security.pdf"],
        },
        "overall_priority": "high",
        "executive_summary": "Stabilize deployment and security controls first.",
        "timeline_summary": [],
        "plan_at_a_glance": [],
        "risk_heatmap": [],
        "days_1_30": [],
        "days_31_60": [],
        "days_61_90": [],
        "days_91_100": [],
        "success_metrics": [],
        "board_checkpoints": [],
        "dependencies": [],
        "limitations": [],
        "llm_api_key": "xai-secret",
    }

    markdown = _build_hundred_day_plan_markdown(plan)

    assert "- Plan Type: turnaround" in markdown
    assert "- Provider: Anthropic" in markdown
    assert "xai-secret" not in markdown


def test_download_key_changes_by_variant():
    payload = {
        "document_set_id": "set-123",
        "report_metadata": {
            "document_set_id": "set-123",
            "generated_at": "2026-06-10 14:32",
            "provider": "Mock",
            "model": "mock",
        },
    }

    assert _download_key(payload, "100_day_plan", "turnaround") != _download_key(
        payload,
        "100_day_plan",
        "growth_equity",
    )


def test_export_filename_helper_uses_report_metadata():
    payload = {"report_metadata": {"investigation": "FinTechCo Diligence"}}

    filename = _export_filename(payload, "board_summary")

    assert filename.startswith("FinTechCo_Diligence_board_summary_")
