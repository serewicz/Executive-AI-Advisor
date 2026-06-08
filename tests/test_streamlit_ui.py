import streamlit as st

from ui.streamlit_app import (
    _build_qa_payload,
    _clear_local_ui_state,
    _evaluation_missing_requirements,
    _evaluation_questions_from_text,
    _evaluation_questions_to_text,
    _evaluation_ready_documents,
    _remove_document_from_local_state,
    _sync_active_document_set_state,
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
