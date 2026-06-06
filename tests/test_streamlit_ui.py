from ui.streamlit_app import _build_qa_payload


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
