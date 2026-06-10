import json
import os
import re
import sys
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import requests
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.advisor.text import normalize_text_field


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
DEFAULT_EVALUATION_PATH = Path(__file__).resolve().parents[1] / "docs" / "evaluation" / "default_questions.json"
SOURCE_TYPES = [
    "technology_assessment",
    "diligence_report",
    "sec_filing",
    "board_material",
]
CLASSIFICATIONS = ["confidential", "internal", "restricted", "public"]
EVALUATION_READY_STATUSES = {"chunked", "embedded", "indexed"}
SUMMARY_TYPES = [
    "technology_risk",
    "diligence_summary",
    "ai_readiness",
    "security_governance",
    "board_brief",
]
LLM_PROVIDER_OPTIONS = {
    "mock": "Mock",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "grok": "Grok / xAI",
}
DEFAULT_LLM_MODELS = {
    "mock": "mock",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-latest",
    "grok": "grok-4.3",
}
PROCESSING_STATUSES = {
    "uploaded": ("Uploaded", 15),
    "parsing": ("Parsing", 30),
    "parsed": ("Parsed", 45),
    "chunking": ("Chunking", 60),
    "chunked": ("Chunked", 75),
    "embedding": ("Embedding", 90),
    "embedded": ("Embedded", 100),
    "indexed": ("Embedded", 100),
    "failed": ("Failed", 100),
}
LOCAL_UI_STATE_KEYS = [
    "document_id",
    "summary_document_id",
    "active_document_id",
    "active_document_set_id",
    "active_document_set_name",
    "uploaded_documents",
    "selected_documents",
    "uploaded_filename",
    "document_status",
    "qa_response",
    "board_summary",
    "technology_report",
    "hundred_day_plan",
    "evaluation_response",
    "evaluation_questions_text",
    "evaluation_questions_initialized",
    "active_llm_provider",
    "active_llm_model",
    "active_llm_api_key",
    "openai_api_key",
    "anthropic_api_key",
    "xai_api_key",
    "processing_active",
    "processing_results",
]


def main() -> None:
    st.set_page_config(page_title="Executive AI Advisor", layout="wide")
    _initialize_state()
    _apply_styles()
    _render_llm_provider_sidebar()

    st.title("Executive AI Advisor")
    st.caption("Board-facing document intelligence demo")
    st.divider()

    _render_workspace_section()
    st.divider()
    _render_upload_section()
    st.divider()
    _render_processing_section()
    st.divider()

    left, right = st.columns([1, 1], gap="large")
    with left:
        _render_qa_section()
    with right:
        _render_board_summary_section()

    st.divider()
    _render_technology_report_section()
    st.divider()
    _render_hundred_day_plan_section()
    st.divider()
    _render_evaluation_section()
    st.divider()
    _render_evidence_section()
    st.divider()
    _render_export_section()


def _initialize_state() -> None:
    defaults = {
        "document_id": "",
        "summary_document_id": "",
        "active_document_id": "",
        "uploaded_filename": "",
        "document_status": "",
        "active_document_set_id": "",
        "active_document_set_name": "",
        "uploaded_documents": [],
        "selected_documents": [],
        "qa_response": None,
        "board_summary": None,
        "technology_report": None,
        "hundred_day_plan": None,
        "evaluation_response": None,
        "evaluation_questions_text": "",
        "evaluation_questions_initialized": False,
        "active_llm_provider": "mock",
        "active_llm_model": DEFAULT_LLM_MODELS["mock"],
        "active_llm_api_key": "",
        "openai_api_key": "",
        "anthropic_api_key": "",
        "xai_api_key": "",
        "processing_active": False,
        "processing_results": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _apply_styles() -> None:
    st.markdown(
        """
        <style>
        .confidence {
            display: inline-block;
            padding: 0.25rem 0.6rem;
            border-radius: 0.35rem;
            font-size: 0.82rem;
            font-weight: 650;
            border: 1px solid rgba(49, 51, 63, 0.2);
        }
        .confidence-high { background: #e8f5ee; color: #145a32; }
        .confidence-medium { background: #fff6df; color: #7a4b00; }
        .confidence-low { background: #fbeaea; color: #8a1f1f; }
        .section-note { color: #5f6368; font-size: 0.92rem; }
        .workspace-active { font-size: 1.05rem; font-weight: 650; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_llm_provider_sidebar() -> None:
    with st.sidebar:
        st.header("LLM Provider")
        st.caption(
            "Choose the answer-generation provider used for reports. Provider and model are recorded in report "
            "metadata for governance; API keys are never displayed or exported."
        )
        provider_keys = list(LLM_PROVIDER_OPTIONS.keys())
        current_provider = st.session_state.active_llm_provider
        selected_provider = st.selectbox(
            "Provider",
            provider_keys,
            index=provider_keys.index(current_provider) if current_provider in provider_keys else 0,
            format_func=lambda value: LLM_PROVIDER_OPTIONS[value],
            key="llm_provider_select",
        )
        if selected_provider != st.session_state.active_llm_provider:
            st.session_state.active_llm_provider = selected_provider
            st.session_state.active_llm_model = DEFAULT_LLM_MODELS[selected_provider]
            st.session_state.active_llm_api_key = _session_key_for_provider(selected_provider)

        model = st.text_input(
            "Model",
            value=st.session_state.active_llm_model or DEFAULT_LLM_MODELS[selected_provider],
            key=f"llm_model_input_{selected_provider}",
        )
        st.session_state.active_llm_model = model.strip() or DEFAULT_LLM_MODELS[selected_provider]

        with st.expander("Why use your own provider key?", expanded=False):
            st.markdown(
                "\n".join(
                    [
                        "- **Security:** keys stay in the local Streamlit session and are not saved by the app.",
                        "- **Cost tracking:** your provider account shows usage and spend directly.",
                        "- **Provider control:** compare Mock, OpenAI, Anthropic, and Grok outputs without code changes.",
                        "- **Governance:** generated reports show provider and model metadata, never API keys.",
                    ]
                )
            )
        st.warning("Do not commit provider API keys to Git or paste them into exported report text.")
        entered_key = st.text_input("API key", type="password", key=f"llm_api_key_input_{selected_provider}")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Use session key", use_container_width=True):
                if selected_provider == "mock":
                    st.info("Mock provider does not require an API key.")
                elif entered_key:
                    _store_session_key(selected_provider, entered_key)
                    st.success("API key loaded for this Streamlit session.")
                else:
                    st.warning("Enter an API key before loading it into the session.")
        with col2:
            if st.button("Clear API Keys", use_container_width=True):
                _clear_session_api_keys()
                st.success("Session API keys cleared.")

        if selected_provider == "mock":
            st.caption("Provider: Mock, no key required")
        elif _session_key_for_provider(selected_provider):
            st.caption(f"Provider: {LLM_PROVIDER_OPTIONS[selected_provider]}, key loaded in session")
        else:
            st.caption(f"Provider: {LLM_PROVIDER_OPTIONS[selected_provider]}, using environment key if configured")


def _store_session_key(provider: str, api_key: str) -> None:
    key = api_key.strip()
    if provider == "openai":
        st.session_state.openai_api_key = key
    elif provider == "anthropic":
        st.session_state.anthropic_api_key = key
    elif provider == "grok":
        st.session_state.xai_api_key = key
    st.session_state.active_llm_api_key = key


def _session_key_for_provider(provider: str) -> str:
    if provider == "openai":
        return st.session_state.get("openai_api_key", "")
    if provider == "anthropic":
        return st.session_state.get("anthropic_api_key", "")
    if provider == "grok":
        return st.session_state.get("xai_api_key", "")
    return ""


def _clear_session_api_keys() -> None:
    for key in ["openai_api_key", "anthropic_api_key", "xai_api_key", "active_llm_api_key"]:
        st.session_state[key] = ""


def _generation_provider_payload() -> dict[str, Any]:
    provider = st.session_state.get("active_llm_provider", "mock")
    payload: dict[str, Any] = {
        "llm_provider": provider,
        "llm_model": st.session_state.get("active_llm_model") or DEFAULT_LLM_MODELS.get(provider),
    }
    api_key = _session_key_for_provider(provider)
    if provider != "mock" and api_key:
        payload["llm_api_key"] = api_key
    return payload


def _render_workspace_section() -> None:
    st.header("Investigation Workspace")
    st.markdown(
        '<div class="section-note">Use one workspace per company or deal so prior investigations stay out of scope.</div>',
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        with st.form("create_workspace_form", clear_on_submit=True):
            name = st.text_input("New investigation name", placeholder="SampleCo Diligence")
            description = st.text_area(
                "Description",
                placeholder="Synthetic B2B SaaS diligence package",
                height=80,
            )
            submitted = st.form_submit_button("Create new investigation", use_container_width=True)
        if submitted:
            if not name.strip():
                st.warning("Name the investigation before creating it.")
            else:
                response = _post_json(
                    "/document-sets",
                    {"name": name.strip(), "description": description.strip() or None},
                    expected_status={201},
                )
                if response:
                    _set_active_document_set(response["document_set_id"], response["name"])
                    st.rerun()

    document_sets = _get_json("/document-sets") or {"document_sets": []}
    options = document_sets.get("document_sets", [])
    labels = ["No active investigation"] + [
        f"{item['name']} ({item.get('document_count', 0)} docs)" for item in options
    ]
    active_id = st.session_state.active_document_set_id
    selected_index = 0
    for index, item in enumerate(options, start=1):
        if item["document_set_id"] == active_id:
            selected_index = index
            break

    with col2:
        selected = st.selectbox("Select existing investigation", labels, index=selected_index)
        if selected != labels[selected_index]:
            if selected == labels[0]:
                _clear_active_document_set()
            else:
                selected_item = options[labels.index(selected) - 1]
                _set_active_document_set(selected_item["document_set_id"], selected_item["name"])
            st.rerun()

        if st.button("Clear active investigation selection", use_container_width=True):
            _clear_active_document_set()
            st.rerun()
        if st.button("Clear Local UI State", use_container_width=True):
            _clear_local_ui_state()
            st.success("Local UI state cleared. Backend data was not deleted.")
            st.rerun()

    if not st.session_state.active_document_set_id:
        st.info("Create or select an investigation before uploading diligence PDFs.")
        return

    refresh_col, _spacer = st.columns([1, 2])
    if refresh_col.button("Refresh Investigation", use_container_width=True):
        detail = _load_active_document_set_detail()
        if detail:
            _sync_active_document_set_state(detail)
            st.success("Investigation refreshed from backend.")
        st.rerun()

    detail = _load_active_document_set_detail()
    if not detail:
        return
    _sync_active_document_set_state(detail)

    st.markdown(f"<div class='workspace-active'>Active investigation: {detail['name']}</div>", unsafe_allow_html=True)
    if detail.get("description"):
        st.caption(detail["description"])

    documents = st.session_state.uploaded_documents
    st.markdown("#### Documents in scope")
    if not documents:
        st.info("No documents have been added to this investigation yet.")
        return

    for document in documents:
        cols = st.columns([3, 1, 1, 1])
        cols[0].markdown(f"**{document['filename']}**")
        cols[0].caption(f"Document ID: {document['document_id']}")
        cols[1].metric("Status", document["status"])
        cols[2].caption(f"{document['source_type']} / {document['classification']}")
        if cols[3].button("Remove", key=f"remove_{document['document_id']}"):
            _request(
                "DELETE",
                f"/document-sets/{st.session_state.active_document_set_id}/documents/{document['document_id']}",
            )
            _remove_document_from_local_state(document["document_id"])
            st.rerun()


def _render_upload_section() -> None:
    st.header("Document Upload")
    st.markdown(
        '<div class="section-note">Upload one or more PDFs into the active investigation workspace.</div>',
        unsafe_allow_html=True,
    )

    with st.form("upload_form", clear_on_submit=False):
        uploaded_files = st.file_uploader(
            "Upload diligence PDFs",
            type=["pdf"],
            accept_multiple_files=True,
        )
        col1, col2 = st.columns(2)
        with col1:
            source_type = st.selectbox("Source type", SOURCE_TYPES)
        with col2:
            classification = st.selectbox("Classification", CLASSIFICATIONS)

        submitted = st.form_submit_button(
            "Upload PDFs",
            disabled=not st.session_state.active_document_set_id,
            use_container_width=True,
        )

    if submitted:
        if not st.session_state.active_document_set_id:
            st.warning("Create or select an investigation before uploading.")
            return
        if not uploaded_files:
            st.warning("Select at least one PDF before uploading.")
            return

        uploaded_count = 0
        with st.spinner("Uploading documents"):
            for uploaded_file in uploaded_files:
                response = _upload_document(
                    uploaded_file,
                    source_type,
                    classification,
                    document_set_id=st.session_state.active_document_set_id,
                )
                if response is None:
                    continue
                document_id = response.get("document_id")
                if not document_id:
                    st.error(f"Upload for {uploaded_file.name} did not return a document_id. Skipping it.")
                    continue
                uploaded_count += 1
                st.session_state.document_id = document_id
                st.session_state.active_document_id = document_id
                st.session_state.summary_document_id = document_id
                st.session_state.uploaded_filename = response.get("filename", uploaded_file.name)
                st.session_state.document_status = response.get("status", "uploaded")
        st.session_state.qa_response = None
        st.session_state.board_summary = None
        st.session_state.technology_report = None
        st.session_state.hundred_day_plan = None
        st.session_state.evaluation_response = None
        if uploaded_count:
            detail = _load_active_document_set_detail()
            if detail:
                _sync_active_document_set_state(detail)
            st.success(f"Uploaded {uploaded_count} document(s) to active investigation.")
            st.rerun()

    if st.session_state.document_id:
        st.success("Document uploaded")
        col1, col2, col3 = st.columns([2, 1, 1])
        col1.text_input("Document ID", value=st.session_state.document_id, key="document_id_display")
        col2.metric("Status", st.session_state.document_status or "uploaded")
        col3.metric("Filename", st.session_state.uploaded_filename or "PDF")


def _render_processing_section() -> None:
    st.header("Processing Pipeline")
    st.markdown(
        '<div class="section-note">Run the document through parsing, chunking, and embedding.</div>',
        unsafe_allow_html=True,
    )

    document_set_id = st.session_state.active_document_set_id
    processing_active = bool(st.session_state.get("processing_active"))
    if document_set_id:
        _render_processing_status_table(st.session_state.uploaded_documents)
        col1, col2 = st.columns([1, 1])
        with col1:
            refresh_clicked = st.button("Refresh Status", use_container_width=True, disabled=processing_active)
        with col2:
            process_clicked = st.button("Process All", use_container_width=True, disabled=processing_active)

        if refresh_clicked:
            detail = _load_active_document_set_detail()
            if detail:
                _sync_active_document_set_state(detail)
                st.success("Investigation status refreshed.")

        if process_clicked:
            detail = _load_active_document_set_detail()
            if not detail:
                return
            _sync_active_document_set_state(detail)
            if not st.session_state.uploaded_documents:
                st.warning("No backend documents are currently attached to this investigation.")
                return
            st.session_state.processing_active = True
            with st.spinner("Processing investigation documents"):
                response = _post_json(f"/document-sets/{document_set_id}/process", {})
            st.session_state.processing_active = False
            if response:
                documents = response.get("documents", [])
                st.session_state.processing_results = documents
                refreshed = _load_active_document_set_detail()
                if refreshed:
                    _sync_active_document_set_state(refreshed)
                _render_processing_completion(documents)

        if st.session_state.get("processing_results") and not process_clicked:
            _render_processing_completion(st.session_state.processing_results)
        st.caption("Runs parse, chunk, and embed for documents in the active investigation that need processing.")
        return

    document_id = _active_document_id()
    if st.session_state.document_status:
        _render_single_document_status(st.session_state.uploaded_filename or document_id, st.session_state.document_status)
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Parse document", disabled=not document_id or processing_active, use_container_width=True):
            _run_processing_step("parse")
    with col2:
        if st.button("Chunk document", disabled=not document_id or processing_active, use_container_width=True):
            _run_processing_step("chunk")
    with col3:
        if st.button("Embed document", disabled=not document_id or processing_active, use_container_width=True):
            _run_processing_step("embed")

    if not document_id:
        st.info("Upload a PDF before running the processing pipeline.")


def _render_qa_section() -> None:
    st.header("Executive Q&A")
    document_id = _active_document_id()
    document_set_id = st.session_state.active_document_set_id
    question = st.text_area(
        "Question",
        value="What are the main technology risks?",
        height=110,
    )
    top_k = st.slider("Sources to retrieve", min_value=1, max_value=20, value=5, key="qa_top_k")
    search_globally = st.checkbox(
        "Industry Benchmark / Cross-Investigation Analysis",
        value=False,
        help=(
            "Includes documents from other investigations and companies. "
            "Use for benchmarking and trend analysis, not company-specific diligence."
        ),
    )
    if search_globally:
        st.warning(
            "Includes documents from other investigations and companies. "
            "Use for benchmarking and trend analysis, not company-specific diligence."
        )
    elif document_set_id:
        st.caption(f"Scoped to active investigation: {st.session_state.active_document_set_name}")
    elif document_id:
        st.caption(f"Scoped to document: {document_id}")

    if st.button("Ask Advisor", disabled=not question.strip(), use_container_width=True):
        with st.spinner("Retrieving evidence and drafting answer"):
            response = _post_json(
                "/advisor/ask",
                _build_qa_payload(
                    question=question.strip(),
                    top_k=top_k,
                    document_id=document_id,
                    document_set_id=document_set_id,
                    search_globally=search_globally,
                ),
            )
        if response:
            st.session_state.qa_response = response

    response = st.session_state.qa_response
    if response:
        st.subheader("Answer")
        st.markdown(response.get("answer", ""))
        _render_confidence(response.get("confidence", "low"))
        scope = response.get("scope", "global")
        if scope == "document":
            st.caption(f"Search scope: document {response.get('document_id', '')}")
        elif scope == "document_set":
            st.caption(f"Search scope: investigation {response.get('document_set_id', '')}")
        else:
            st.caption("Search scope: all documents")
        _render_limitations(response.get("limitations", []))
        _render_citations(response.get("citations", []), title="Q&A Citations")


def _build_qa_payload(
    question: str,
    top_k: int,
    document_id: str,
    document_set_id: str = "",
    search_globally: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "question": question,
        "top_k": top_k,
        "source_type": None,
        "classification": None,
    }
    if document_set_id and not search_globally:
        payload["document_set_id"] = document_set_id
    elif document_id and not search_globally:
        payload["document_id"] = document_id
    payload.update(_generation_provider_payload())
    return payload


def _render_board_summary_section() -> None:
    st.header("Board Summary Generator")
    document_id = st.text_input(
        "Document ID",
        value=st.session_state.document_id,
        placeholder="Paste or upload a document ID",
        key="summary_document_id",
    )
    col1, col2 = st.columns([2, 1])
    with col1:
        summary_type = st.selectbox("Summary type", SUMMARY_TYPES)
    with col2:
        top_k = st.slider("Sources", min_value=3, max_value=25, value=12, key="summary_top_k")

    document_set_id = st.session_state.active_document_set_id
    if document_set_id:
        st.caption(f"Defaults to active investigation: {st.session_state.active_document_set_name}")

    disabled = not document_set_id and not document_id.strip()
    if st.button("Generate Board Summary", disabled=disabled, use_container_width=True):
        payload = {"summary_type": summary_type, "top_k": top_k}
        if document_set_id:
            payload["document_set_id"] = document_set_id
        else:
            payload["document_id"] = document_id.strip()
        payload.update(_generation_provider_payload())
        with st.spinner("Generating board memo"):
            response = _post_json("/advisor/board-summary", payload)
        if response:
            if response.get("document_id"):
                st.session_state.document_id = response["document_id"]
            st.session_state.board_summary = _with_report_metadata(response, "board_summary")

    if st.session_state.board_summary:
        _render_board_memo(st.session_state.board_summary)


def _render_board_memo(response: dict[str, Any]) -> None:
    memo = response.get("memo", {})
    title = _format_summary_type(response.get("summary_type", "board_brief"))
    st.subheader(title)
    _render_report_metadata(response)
    _render_confidence(response.get("confidence", "low"))

    st.markdown("#### Executive Summary")
    st.markdown(normalize_text_field(memo.get("executive_summary", "No executive summary returned.")))

    _render_list("Key Risks", memo.get("key_risks", []))
    _render_list("Evidence", memo.get("evidence", []))
    _render_list("Board Questions", memo.get("board_questions", []))
    _render_list("Recommended Actions", memo.get("recommended_actions", []))
    _render_limitations(memo.get("limitations", []))
    _render_citations(response.get("citations", []), title="Board Summary Citations")


def _render_technology_report_section() -> None:
    st.header("Technology Due Diligence Report")
    st.markdown(
        '<div class="section-note">Generate a structured board-quality report for the active investigation workspace.</div>',
        unsafe_allow_html=True,
    )

    document_set_id = st.session_state.active_document_set_id
    if document_set_id:
        st.caption(f"Scoped to active investigation: {st.session_state.active_document_set_name}")
    else:
        st.info("Select or create an investigation before generating a technology due diligence report.")

    col1, col2 = st.columns([1, 1])
    with col1:
        top_k = st.slider("Evidence budget", min_value=5, max_value=40, value=20, key="technology_report_top_k")
    with col2:
        include_plan = st.checkbox("Include 30/60/90-day plan", value=True, key="technology_report_plan")

    if st.button(
        "Generate Technology Due Diligence Report",
        disabled=not document_set_id,
        use_container_width=True,
    ):
        with st.spinner("Retrieving evidence and generating technology diligence report"):
            response = _post_json(
                "/diligence/technology-report",
                {
                    "document_set_id": document_set_id,
                    "top_k": top_k,
                    "include_100_day_plan": include_plan,
                    **_generation_provider_payload(),
                },
            )
        if response:
            st.session_state.technology_report = _with_report_metadata(response, "technology_due_diligence")

    report = st.session_state.technology_report
    if report:
        _render_technology_report(report)


def _render_technology_report(report: dict[str, Any]) -> None:
    st.subheader("Technology Due Diligence Report")
    _render_report_metadata(report)
    findings = report.get("findings", [])
    risk_counts = _risk_counts(findings)

    metric_cols = st.columns(6)
    metric_cols[0].metric("Overall Risk", str(report.get("overall_risk_rating", "unknown")).title())
    metric_cols[1].metric("Confidence", f"{str(report.get('confidence', 'low')).title()}")
    metric_cols[2].metric("Total Findings", len(findings))
    metric_cols[3].metric("Red Findings", risk_counts["red"])
    metric_cols[4].metric("Yellow Findings", risk_counts["yellow"])
    metric_cols[5].metric("Green Findings", risk_counts["green"])

    st.markdown(
        " ".join(
            [
                render_risk_badge(str(report.get("overall_risk_rating", "green"))),
                render_confidence_badge(str(report.get("confidence", "low"))),
            ]
        ),
        unsafe_allow_html=True,
    )

    st.markdown("#### Executive Summary")
    st.markdown(normalize_text_field(report.get("executive_summary", "No executive summary returned.")))

    _render_risk_heatmap(report.get("risk_heatmap", []))
    _render_list("Top 5 Risks", report.get("top_5_risks", []))
    _render_technology_findings(findings)
    _render_list("Management Questions", report.get("management_questions", []))
    _render_list("Board Discussion Points", report.get("board_discussion_points", []))
    _render_list("Recommended Actions", report.get("recommended_actions", []))
    _render_technology_plan(report.get("thirty_sixty_ninety_day_plan", {}))
    _render_limitations(report.get("limitations", []))
    _render_citations(report.get("citations", []), title="Report Citations")

    markdown = _build_technology_report_markdown(report)
    st.download_button(
        label="Download Technology Due Diligence Report.md",
        data=markdown,
        file_name=_export_filename(report, "technology_due_diligence"),
        mime="text/markdown",
        key=f"{_download_key(report, 'technology_due_diligence')}_inline",
        use_container_width=True,
    )


def _render_technology_findings(findings: list[dict[str, Any]]) -> None:
    st.markdown("#### Findings")
    if not findings:
        st.markdown("No findings returned.")
        return

    for finding in findings:
        st.markdown(f"##### {_format_summary_type(finding.get('category', 'finding'))}")
        st.markdown(
            " ".join(
                [
                    render_risk_badge(str(finding.get("risk_rating", "green"))),
                    render_confidence_badge(str(finding.get("confidence", "low"))),
                ]
            ),
            unsafe_allow_html=True,
        )
        st.caption(f"Recommended owner: {finding.get('recommended_owner', 'Unassigned')}")
        st.markdown(f"**{finding.get('title', '')}**")
        st.markdown(f"**Risk rationale:** {finding.get('risk_rationale', 'No risk rationale returned.')}")
        st.markdown(
            f"**Confidence rationale:** {finding.get('confidence_rationale', 'No confidence rationale returned.')}"
        )
        st.markdown(f"**Business impact:** {finding.get('business_impact', '')}")
        st.markdown(f"**Evidence:** {finding.get('evidence_summary', '')}")
        st.markdown(f"**Recommended action:** {finding.get('recommended_action', '')}")
        _render_citations(
            finding.get("citations", []),
            title=f"{_format_summary_type(finding.get('category', 'finding'))} Evidence",
            use_expanders=False,
        )
        st.divider()


def _render_technology_plan(plan: dict[str, list[str]]) -> None:
    st.markdown("#### 30/60/90-Day Plan")
    col1, col2, col3 = st.columns(3)
    with col1:
        _render_list("Days 1-30", plan.get("days_1_30", []))
    with col2:
        _render_list("Days 31-60", plan.get("days_31_60", []))
    with col3:
        _render_list("Days 61-90", plan.get("days_61_90", []))


def _render_hundred_day_plan_section() -> None:
    st.header("100-Day Technology Plan")
    st.markdown(
        '<div class="section-note">Convert diligence findings into an operating plan for a CTO, operating partner, or portfolio company.</div>',
        unsafe_allow_html=True,
    )

    document_set_id = st.session_state.active_document_set_id
    if document_set_id:
        st.caption(f"Scoped to active investigation: {st.session_state.active_document_set_name}")
    else:
        st.info("Select or create an investigation before generating a 100-day plan.")

    plan_type = st.selectbox(
        "Plan type",
        ["growth_equity", "acquisition_integration", "turnaround"],
        format_func=_format_summary_type,
        key="hundred_day_plan_type",
    )

    if st.button("Generate 100-Day Plan", disabled=not document_set_id, use_container_width=True):
        with st.spinner("Generating 100-day technology plan"):
            response = _post_json(
                "/diligence/100-day-plan",
                {
                    "document_set_id": document_set_id,
                    "plan_type": plan_type,
                    **_generation_provider_payload(),
                },
            )
        if response:
            st.session_state.hundred_day_plan = _with_report_metadata(
                response,
                "100_day_plan",
                variant=plan_type,
            )

    plan = st.session_state.hundred_day_plan
    if plan:
        _render_hundred_day_plan(plan)


def _render_hundred_day_plan(plan: dict[str, Any]) -> None:
    st.subheader("100-Day Technology Plan")
    _render_report_metadata(plan)
    col1, col2 = st.columns(2)
    col1.metric("Plan Type", _format_summary_type(plan.get("plan_type", "")))
    col2.metric("Overall Priority", str(plan.get("overall_priority", "unknown")).title())

    one_pager_tab, full_plan_tab = st.tabs(["Executive One-Pager", "Full 100-Day Plan"])
    with one_pager_tab:
        _render_hundred_day_one_pager(plan)
    with full_plan_tab:
        _render_full_hundred_day_plan(plan)


def _render_full_hundred_day_plan(plan: dict[str, Any]) -> None:
    st.markdown("#### Executive Summary")
    st.markdown(normalize_text_field(plan.get("executive_summary", "No executive summary returned.")))

    _render_timeline_summary(plan.get("timeline_summary", []))
    _render_plan_at_a_glance(plan.get("plan_at_a_glance", []))
    _render_risk_heatmap(plan.get("risk_heatmap", []))
    if plan.get("quick_wins"):
        _render_list("Quick Wins", plan.get("quick_wins", []))
    _render_plan_actions("Days 1-30", plan.get("days_1_30", []))
    _render_plan_actions("Days 31-60", plan.get("days_31_60", []))
    _render_plan_actions("Days 61-90", plan.get("days_61_90", []))
    _render_plan_actions("Days 91-100 / Board Readout", plan.get("days_91_100", []))
    _render_list("Success Metrics", plan.get("success_metrics", []))
    _render_board_checkpoints(plan.get("board_checkpoints", []))
    _render_list("Dependencies", plan.get("dependencies", []))
    _render_limitations(plan.get("limitations", []))

    markdown = _build_hundred_day_plan_markdown(plan)
    st.download_button(
        label="Download 100-Day Technology Plan.md",
        data=markdown,
        file_name=_export_filename(plan, "100_day_plan", str(plan.get("plan_type", "plan"))),
        mime="text/markdown",
        key=f"{_download_key(plan, '100_day_plan', str(plan.get('plan_type', 'plan')))}_inline",
        use_container_width=True,
    )


def _render_hundred_day_one_pager(plan: dict[str, Any]) -> None:
    one_pager = plan.get("executive_one_pager") or {}
    if not one_pager:
        st.info("No executive one-pager returned.")
        return

    st.markdown("#### Executive Summary")
    st.markdown(normalize_text_field(one_pager.get("executive_summary", "No executive summary returned.")))

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Current State")
        st.markdown(one_pager.get("current_state", "Not provided."))
    with col2:
        st.markdown("#### Target State")
        st.markdown(one_pager.get("target_state", "Not provided."))

    st.markdown("#### Overall Risk")
    st.markdown(one_pager.get("overall_risk", "Not provided."))

    _render_risk_heatmap(plan.get("risk_heatmap", []))
    _render_list("Top 5 Priorities", one_pager.get("top_5_priorities", []))
    _render_list("First 30 Days", one_pager.get("first_30_days", []))
    _render_list("Days 31-60", one_pager.get("days_31_60", []))
    _render_list("Days 61-90", one_pager.get("days_61_90", []))
    _render_list("Board Decisions Required", one_pager.get("board_decisions_required", []))
    _render_list("Success Metrics", one_pager.get("success_metrics", []))
    _render_list("Key Dependencies", one_pager.get("key_dependencies", []))

    markdown = _build_hundred_day_one_pager_markdown(plan)
    st.download_button(
        label="Download Executive One-Pager.md",
        data=markdown,
        file_name=_export_filename(plan, "100_day_plan_one_pager", str(plan.get("plan_type", "plan"))),
        mime="text/markdown",
        key=f"{_download_key(plan, '100_day_plan_one_pager', str(plan.get('plan_type', 'plan')))}_inline",
        use_container_width=True,
    )


def _render_plan_actions(title: str, actions: list[dict[str, Any]]) -> None:
    st.markdown(f"#### {title}")
    if not actions:
        st.markdown("No actions assigned.")
        return

    for index, action in enumerate(actions, start=1):
        st.markdown(f"##### {index}. {action.get('action', '')}")
        st.caption(f"Priority: {str(action.get('priority', '')).title()} | Owner: {action.get('owner', '')}")
        st.markdown(f"**Business rationale:** {action.get('business_rationale', '')}")
        _render_list("Deliverables", action.get("deliverables", []))
        st.markdown(f"**Success metric:** {action.get('success_metric', '')}")
        st.markdown(f"**Risk reduction:** {action.get('risk_reduction', '')}")
        _render_citations(
            action.get("citations", []),
            title=f"{title} Action {index} Evidence",
            use_expanders=False,
        )


def _render_plan_at_a_glance(rows: list[dict[str, Any]]) -> None:
    st.markdown("#### 100-Day Plan at a Glance")
    if not rows:
        st.markdown("No plan summary returned.")
        return
    st.table(
        [
            {
                "Timeframe": row.get("timeframe", ""),
                "Primary Objective": row.get("primary_objective", ""),
                "Key Actions": row.get("key_actions", ""),
                "Success Measures": row.get("success_measures", ""),
                "Risk Reduced": row.get("risk_reduced", ""),
            }
            for row in rows
        ]
    )


def _render_timeline_summary(rows: list[dict[str, Any]]) -> None:
    st.markdown("#### Timeline Summary")
    if not rows:
        st.markdown("No timeline summary returned.")
        return
    st.table(
        [
            {
                "Phase": row.get("phase", ""),
                "Primary Objective": row.get("primary_objective", ""),
                "Key Actions": row.get("key_actions", ""),
                "Expected Outcomes": row.get("expected_outcomes", ""),
                "Risk Reduced": row.get("risk_reduced", ""),
                "Board Checkpoint": row.get("board_checkpoint", ""),
            }
            for row in rows
        ]
    )


def _render_board_checkpoints(checkpoints: list[dict[str, Any]]) -> None:
    st.markdown("#### Board Checkpoints")
    if not checkpoints:
        st.markdown("None provided.")
        return
    for checkpoint in checkpoints:
        st.markdown(f"##### {checkpoint.get('timeframe', '')}")
        st.markdown(f"**Question for management:** {checkpoint.get('question', '')}")
        st.markdown(f"**Evidence requested:** {checkpoint.get('evidence_requested', '')}")
        decision = checkpoint.get("decision_needed")
        if decision:
            st.markdown(f"**Decision needed:** {decision}")


def _render_evaluation_section() -> None:
    st.header("Evaluation")
    st.markdown(
        '<div class="section-note">Run deterministic checks for citation quality, groundedness, relevance, and executive usefulness.</div>',
        unsafe_allow_html=True,
    )
    default_questions = _load_default_evaluation_questions()
    default_question_text = _evaluation_questions_to_text(default_questions)
    if not st.session_state.evaluation_questions_initialized:
        st.session_state.evaluation_questions_text = default_question_text
        st.session_state.evaluation_questions_initialized = True

    active_document_set_id = st.session_state.active_document_set_id
    active_document_id = _active_document_id()
    scope_options = ["Single Document"]
    default_scope_index = 0
    if active_document_set_id:
        scope_options.insert(0, "Active Investigation / Document Set")
        default_scope_index = 0

    scope = st.radio(
        "Evaluation Scope",
        scope_options,
        index=default_scope_index,
        horizontal=True,
        key="evaluation_scope",
    )

    document_id = ""
    if scope == "Active Investigation / Document Set":
        st.info(
            "Single-document evaluation only. Select one processed document from the active investigation."
        )
        document_id = _render_evaluation_document_selector(st.session_state.uploaded_documents)
    else:
        document_id = st.text_input(
            "Evaluation document ID",
            value=active_document_id,
            placeholder="Paste or upload a document ID",
            key="evaluation_document_id",
        ).strip()

    question_mode = st.radio(
        "Question Mode",
        ["Default question set", "Custom questions"],
        horizontal=True,
        key="evaluation_question_mode",
    )

    question_col1, question_col2 = st.columns(2)
    with question_col1:
        if st.button("Reset to default questions", use_container_width=True):
            st.session_state.evaluation_questions_text = default_question_text
            st.rerun()
    with question_col2:
        if st.button("Clear evaluation questions", use_container_width=True):
            st.session_state.evaluation_questions_text = ""
            st.session_state.evaluation_questions_initialized = True
            st.rerun()

    if question_mode == "Default question set":
        st.caption("The default set is editable before running evaluation.")
    else:
        st.caption("Enter one custom evaluation question per line.")

    questions_text = st.text_area(
        "Evaluation questions",
        key="evaluation_questions_text",
        height=180,
        placeholder="Enter one evaluation question per line.",
    )
    questions = _evaluation_questions_from_text(questions_text, default_questions)

    missing_requirements = _evaluation_missing_requirements(
        scope=scope,
        document_id=document_id,
        questions=questions,
        active_document_set_id=active_document_set_id,
        available_documents=st.session_state.uploaded_documents,
    )
    if missing_requirements:
        for requirement in missing_requirements:
            st.info(requirement)

    if st.button("Run Evaluation", disabled=bool(missing_requirements), use_container_width=True):
        with st.spinner("Running deterministic evaluation"):
            response = _post_json(
                "/evaluation/run",
                {
                    "document_id": document_id,
                    "evaluation_type": "advisor_qa",
                    "questions": questions,
                },
            )
        if response:
            st.session_state.evaluation_response = _with_report_metadata(response, "evaluation_report")

    response = st.session_state.evaluation_response
    if not response:
        return

    st.metric("Average Score", f"{response.get('average_score', 0):.2f}")
    _render_report_metadata(response)
    for result in response.get("results", []):
        with st.expander(f"{result.get('overall_score', 0):.2f} - {result.get('question', '')}"):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Citations", f"{result.get('citation_score', 0):.2f}")
            col2.metric("Groundedness", f"{result.get('groundedness_score', 0):.2f}")
            col3.metric("Relevance", f"{result.get('relevance_score', 0):.2f}")
            col4.metric("Executive Usefulness", f"{result.get('executive_usefulness_score', 0):.2f}")
            st.markdown("#### Answer")
            st.markdown(result.get("answer", ""))
            _render_list("Notes", result.get("notes", []))
            _render_citations(
                result.get("citations", []),
                title="Evaluation Citations",
                use_expanders=False,
            )

    report = _build_evaluation_markdown(response)
    st.download_button(
        label="Download Evaluation Report.md",
        data=report,
        file_name=_export_filename(response, "evaluation_report"),
        mime="text/markdown",
        key=_download_key(response, "evaluation_report", response.get("evaluation_run_id", "latest")),
        use_container_width=True,
    )


def _render_evidence_section() -> None:
    st.header("Citations / Evidence")
    board_summary = st.session_state.board_summary
    technology_report = st.session_state.technology_report
    hundred_day_plan = st.session_state.hundred_day_plan
    qa_response = st.session_state.qa_response
    evaluation_response = st.session_state.evaluation_response

    if not board_summary and not technology_report and not hundred_day_plan and not qa_response and not evaluation_response:
        st.info("Run Executive Q&A, generate a report, generate a board summary, or run evaluation to view citations.")
        return

    if board_summary:
        _render_citations(board_summary.get("citations", []), title="Board Summary Evidence")
    if technology_report:
        _render_citations(technology_report.get("citations", []), title="Technology Diligence Evidence")
    if hundred_day_plan:
        for phase in ("days_1_30", "days_31_60", "days_61_90"):
            for index, action in enumerate(hundred_day_plan.get(phase, []), start=1):
                _render_citations(action.get("citations", []), title=f"100-Day Plan {phase} Action {index} Evidence")
    if qa_response:
        _render_citations(qa_response.get("citations", []), title="Q&A Evidence")
    if evaluation_response:
        for result in evaluation_response.get("results", []):
            _render_citations(result.get("citations", []), title=f"Evaluation Evidence: {result.get('question', '')}")


def _render_export_section() -> None:
    st.header("Export Markdown")
    board_summary = st.session_state.board_summary
    technology_report = st.session_state.technology_report
    hundred_day_plan = st.session_state.hundred_day_plan

    if not board_summary and not technology_report and not hundred_day_plan:
        st.info("Generate a board summary, technology due diligence report, or 100-day plan before exporting.")
        return

    if board_summary:
        markdown = _build_markdown_memo(board_summary)
        st.download_button(
            label="Download Board Memo.md",
            data=markdown,
            file_name=_export_filename(board_summary, "board_summary", board_summary.get("summary_type", "board")),
            mime="text/markdown",
            key=_download_key(board_summary, "board_summary", board_summary.get("summary_type", "board")),
            use_container_width=True,
        )
        with st.expander("Board memo Markdown preview"):
            st.code(markdown, language="markdown")

    if technology_report:
        report_markdown = _build_technology_report_markdown(technology_report)
        st.download_button(
            label="Download Technology Due Diligence Report.md",
            data=report_markdown,
            file_name=_export_filename(technology_report, "technology_due_diligence"),
            mime="text/markdown",
            key=_download_key(technology_report, "technology_due_diligence"),
            use_container_width=True,
        )
        with st.expander("Technology diligence Markdown preview"):
            st.code(report_markdown, language="markdown")

    if hundred_day_plan:
        plan_markdown = _build_hundred_day_plan_markdown(hundred_day_plan)
        st.download_button(
            label="Download 100-Day Technology Plan.md",
            data=plan_markdown,
            file_name=_export_filename(
                hundred_day_plan,
                "100_day_plan",
                str(hundred_day_plan.get("plan_type", "plan")),
            ),
            mime="text/markdown",
            key=_download_key(hundred_day_plan, "100_day_plan", str(hundred_day_plan.get("plan_type", "plan"))),
            use_container_width=True,
        )
        with st.expander("100-day plan Markdown preview"):
            st.code(plan_markdown, language="markdown")


def _upload_document(
    uploaded_file,
    source_type: str,
    classification: str,
    document_set_id: str = "",
) -> dict[str, Any] | None:
    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            "application/pdf",
        )
    }
    data = {"source_type": source_type, "classification": classification}
    if document_set_id:
        data["document_set_id"] = document_set_id
    return _request("POST", "/documents/upload", files=files, data=data, expected_status={201})


def _get_json(path: str) -> dict[str, Any] | None:
    return _request("GET", path)


def _load_default_evaluation_questions() -> list[dict[str, Any]]:
    try:
        with DEFAULT_EVALUATION_PATH.open() as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return [
            {
                "question": "What cybersecurity risks are disclosed?",
                "expected_themes": ["security", "risk", "controls"],
            },
            {
                "question": "What should the board monitor?",
                "expected_themes": ["board", "monitor", "risk"],
            },
        ]


def _evaluation_questions_to_text(questions: list[dict[str, Any]]) -> str:
    return "\n".join(question["question"] for question in questions if question.get("question"))


def _evaluation_questions_from_text(
    questions_text: str,
    default_questions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    expected_themes_by_question = {
        question["question"]: question.get("expected_themes")
        for question in default_questions
        if question.get("question")
    }
    questions = []
    for line in questions_text.splitlines():
        question = line.strip()
        if not question:
            continue
        questions.append(
            {
                "question": question,
                "expected_themes": expected_themes_by_question.get(question),
            }
        )
    return questions


def _evaluation_ready_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        document
        for document in documents
        if str(document.get("status", "")).lower() in EVALUATION_READY_STATUSES
    ]


def _render_evaluation_document_selector(documents: list[dict[str, Any]]) -> str:
    if not documents:
        st.warning("Upload and process at least one document.")
        return ""

    ready_documents = _evaluation_ready_documents(documents)
    if not ready_documents:
        st.warning("Upload and process at least one document.")
        st.caption("Evaluation-ready statuses: chunked, embedded, indexed.")
        for document in documents:
            st.caption(f"{document.get('filename', 'Untitled document')} - {document.get('status', 'unknown')}")
        return ""

    labels = [
        f"{document.get('filename', 'Untitled document')} ({document.get('status', 'unknown')})"
        for document in ready_documents
    ]
    active_document_id = _active_document_id()
    selected_index = 0
    for index, document in enumerate(ready_documents):
        if document.get("document_id") == active_document_id:
            selected_index = index
            break

    selected_label = st.selectbox(
        "Select document to evaluate",
        labels,
        index=selected_index,
        key="evaluation_selected_document_label",
    )
    selected_document = ready_documents[labels.index(selected_label)]
    st.caption(f"Document ID: {selected_document.get('document_id', '')}")
    return selected_document.get("document_id", "")


def _evaluation_missing_requirements(
    scope: str,
    document_id: str,
    questions: list[dict[str, Any]],
    active_document_set_id: str,
    available_documents: list[dict[str, Any]],
) -> list[str]:
    missing = []
    if scope == "Active Investigation / Document Set" and not active_document_set_id:
        missing.append("Select or create an investigation.")
    if scope == "Active Investigation / Document Set" and active_document_set_id:
        if not _evaluation_ready_documents(available_documents):
            missing.append("Upload and process at least one document.")
    if not document_id:
        if scope == "Single Document":
            missing.append("Upload and process at least one document.")
        elif "Upload and process at least one document." not in missing:
            missing.append("Upload and process at least one document.")
    if not questions:
        missing.append("Enter at least one evaluation question.")
    return missing


def _render_processing_status_table(documents: list[dict[str, Any]]) -> None:
    if not documents:
        st.info("Upload PDFs into the active investigation before processing.")
        return

    st.markdown("#### Document Status")
    for document in documents:
        _render_single_document_status(
            str(document.get("filename", "Untitled document")),
            str(document.get("status", "uploaded")),
            str(document.get("error", "") or document.get("error_message", "")),
        )


def _render_single_document_status(filename: str, status: str, error_message: str = "") -> None:
    label, progress_value = _processing_status(status)
    st.caption(f"{filename}: {label}")
    st.progress(progress_value, text=label)
    if status.lower() == "failed":
        st.error(error_message or "Processing failed for this document. Review backend logs for details.")


def _render_processing_completion(documents: list[dict[str, Any]]) -> None:
    if not documents:
        return
    failed = [document for document in documents if str(document.get("status", "")).lower() == "failed"]
    if failed:
        st.error("Processing finished with errors. Failed documents are shown in the status list.")
        for document in failed:
            st.write(f"- {document.get('filename', 'Untitled document')}: failed")
        return
    if all(str(document.get("status", "")).lower() in {"embedded", "indexed"} for document in documents):
        st.success("Processing complete. You can now run Q&A, Board Summary, Diligence Report, or 100-Day Plan.")
    else:
        st.info("Processing updated. Refresh status if any documents are still moving through the pipeline.")


def _processing_status(status: str) -> tuple[str, int]:
    normalized = status.strip().lower()
    return PROCESSING_STATUSES.get(normalized, (status.title() if status else "Uploaded", 10))


def _run_processing_step(step: str) -> None:
    document_id = _active_document_id()
    if not document_id:
        st.warning("Upload or enter a document ID first.")
        return

    labels = {"parse": "Parsing", "chunk": "Chunking", "embed": "Embedding"}
    interim_status = {"parse": "parsing", "chunk": "chunking", "embed": "embedding"}
    st.session_state.processing_active = True
    st.session_state.document_status = interim_status[step]
    with st.spinner(labels[step]):
        response = _post_json(f"/documents/{document_id}/{step}", {})
    st.session_state.processing_active = False

    if not response:
        return

    st.session_state.document_status = response.get("status", st.session_state.document_status)
    st.success(f"{labels[step]} complete")
    if "pages_parsed" in response:
        st.write(f"Pages parsed: **{response['pages_parsed']}**")
    if "chunks_created" in response:
        st.write(f"Chunks created: **{response['chunks_created']}**")
    if "chunks_embedded" in response:
        st.write(f"Chunks embedded: **{response['chunks_embedded']}**")
    if st.session_state.document_status in {"embedded", "indexed"}:
        st.success("Processing complete. You can now run Q&A, Board Summary, Diligence Report, or 100-Day Plan.")


def _post_json(
    path: str,
    payload: dict[str, Any],
    expected_status: set[int] | None = None,
) -> dict[str, Any] | None:
    return _request("POST", path, json=payload, expected_status=expected_status)


def _request(
    method: str,
    path: str,
    expected_status: set[int] | None = None,
    **kwargs,
) -> dict[str, Any] | None:
    expected_status = expected_status or {200}
    url = f"{API_BASE_URL}{path}"

    try:
        response = requests.request(method, url, timeout=120, **kwargs)
    except requests.RequestException as exc:
        st.error(f"Backend request failed: {exc}")
        return None

    if response.status_code not in expected_status:
        st.error(_format_error(response))
        return None

    try:
        return response.json()
    except ValueError:
        st.error("Backend returned a non-JSON response.")
        return None


def _format_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"Backend returned {response.status_code}: {response.text}"

    detail = payload.get("detail", payload)
    if response.status_code == 404 and isinstance(detail, str) and "Document not found" in detail:
        _remove_document_from_local_state(_extract_uuid_from_text(detail))
        return (
            "This document no longer exists in the backend. "
            "Refresh the investigation or clear local UI state."
        )
    if response.status_code == 404 and isinstance(detail, str) and "Document set not found" in detail:
        _clear_active_document_set()
        return (
            "This investigation no longer exists in the backend. "
            "Refresh the investigation list or clear local UI state."
        )
    return f"Backend returned {response.status_code}: {detail}"


def _active_document_id() -> str:
    return (
        st.session_state.get("summary_document_id")
        or st.session_state.get("active_document_id")
        or st.session_state.document_id
        or ""
    ).strip()


def _set_active_document_set(document_set_id: str, name: str) -> None:
    st.session_state.active_document_set_id = document_set_id
    st.session_state.active_document_set_name = name
    st.session_state.document_id = ""
    st.session_state.active_document_id = ""
    st.session_state.summary_document_id = ""
    st.session_state.uploaded_documents = []
    st.session_state.selected_documents = []
    st.session_state.qa_response = None
    st.session_state.board_summary = None
    st.session_state.technology_report = None
    st.session_state.hundred_day_plan = None
    st.session_state.evaluation_response = None
    st.session_state.processing_results = []


def _clear_active_document_set() -> None:
    st.session_state.active_document_set_id = ""
    st.session_state.active_document_set_name = ""
    st.session_state.document_id = ""
    st.session_state.active_document_id = ""
    st.session_state.summary_document_id = ""
    st.session_state.uploaded_documents = []
    st.session_state.selected_documents = []
    st.session_state.qa_response = None
    st.session_state.board_summary = None
    st.session_state.technology_report = None
    st.session_state.hundred_day_plan = None
    st.session_state.evaluation_response = None
    st.session_state.processing_results = []


def _clear_local_ui_state() -> None:
    for key in LOCAL_UI_STATE_KEYS:
        if key in {"uploaded_documents", "selected_documents", "processing_results"}:
            st.session_state[key] = []
        elif key in {"qa_response", "board_summary", "technology_report", "hundred_day_plan", "evaluation_response"}:
            st.session_state[key] = None
        elif key == "evaluation_questions_initialized":
            st.session_state[key] = False
        elif key == "processing_active":
            st.session_state[key] = False
        else:
            st.session_state[key] = ""


def _load_active_document_set_detail() -> dict[str, Any] | None:
    document_set_id = st.session_state.active_document_set_id
    if not document_set_id:
        return None
    detail = _get_json(f"/document-sets/{document_set_id}")
    if detail is None:
        return None
    return detail


def _sync_active_document_set_state(detail: dict[str, Any]) -> None:
    documents = detail.get("documents", [])
    backend_document_ids = {document["document_id"] for document in documents}

    st.session_state.active_document_set_id = detail.get(
        "document_set_id",
        st.session_state.get("active_document_set_id", ""),
    )
    st.session_state.active_document_set_name = detail.get(
        "name",
        st.session_state.get("active_document_set_name", ""),
    )
    st.session_state.uploaded_documents = documents
    st.session_state.selected_documents = [
        document_id
        for document_id in st.session_state.get("selected_documents", [])
        if document_id in backend_document_ids
    ]

    for key in ("document_id", "active_document_id", "summary_document_id"):
        if st.session_state.get(key) and st.session_state[key] not in backend_document_ids:
            st.session_state[key] = ""

    if documents and not _active_document_id():
        latest = documents[0]
        st.session_state.document_id = latest["document_id"]
        st.session_state.active_document_id = latest["document_id"]
        st.session_state.summary_document_id = latest["document_id"]
        st.session_state.uploaded_filename = latest.get("filename", "")
        st.session_state.document_status = latest.get("status", "")


def _remove_document_from_local_state(document_id: str | None) -> None:
    if not document_id:
        return
    st.session_state.uploaded_documents = [
        document for document in st.session_state.get("uploaded_documents", [])
        if document.get("document_id") != document_id
    ]
    st.session_state.selected_documents = [
        selected for selected in st.session_state.get("selected_documents", [])
        if selected != document_id
    ]
    for key in ("document_id", "active_document_id", "summary_document_id"):
        if st.session_state.get(key) == document_id:
            st.session_state[key] = ""
    st.session_state.qa_response = None
    st.session_state.board_summary = None
    st.session_state.technology_report = None
    st.session_state.hundred_day_plan = None
    st.session_state.evaluation_response = None
    st.session_state.processing_results = []


def _extract_uuid_from_text(text: str) -> str | None:
    import re

    match = re.search(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        text,
    )
    return match.group(0) if match else None


def _render_confidence(confidence: str) -> None:
    normalized = confidence if confidence in {"high", "medium", "low"} else "low"
    st.markdown(
        f'<span class="confidence confidence-{normalized}">Confidence: {normalized.title()}</span>',
        unsafe_allow_html=True,
    )


def render_risk_badge(risk_rating: str) -> str:
    normalized = risk_rating.strip().lower()
    styles = {
        "red": ("Red", "#fdecec", "#b42318", "#f5a6a0"),
        "yellow": ("Yellow", "#fff7e6", "#8a4b00", "#f2c36b"),
        "green": ("Green", "#eaf7ef", "#17663a", "#8ccfa5"),
    }
    label, background, color, border = styles.get(normalized, styles["green"])
    return (
        f'<span style="display:inline-block;padding:0.25rem 0.6rem;border-radius:0.35rem;'
        f'font-size:0.82rem;font-weight:650;background:{background};color:{color};'
        f'border:1px solid {border};">Risk: {label}</span>'
    )


def render_confidence_badge(confidence: str) -> str:
    normalized = confidence.strip().lower()
    styles = {
        "high": ("High Confidence", "#e8f5ee", "#145a32", "#8ccfa5"),
        "medium": ("Medium Confidence", "#fff6df", "#7a4b00", "#f2c36b"),
        "low": ("Low Confidence", "#fbeaea", "#8a1f1f", "#f5a6a0"),
    }
    label, background, color, border = styles.get(normalized, styles["low"])
    return (
        f'<span style="display:inline-block;padding:0.25rem 0.6rem;border-radius:0.35rem;'
        f'font-size:0.82rem;font-weight:650;background:{background};color:{color};'
        f'border:1px solid {border};">{label}</span>'
    )


def _risk_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"red": 0, "yellow": 0, "green": 0}
    for finding in findings:
        risk_rating = str(finding.get("risk_rating", "")).lower()
        if risk_rating in counts:
            counts[risk_rating] += 1
    return counts


def _render_risk_heatmap(rows: list[dict[str, Any]]) -> None:
    st.markdown("#### Executive Risk Heatmap")
    if not rows:
        st.markdown("No risk heatmap returned.")
        return

    table_rows = []
    for row in rows:
        table_rows.append(
            "<tr>"
            f"<td>{escape(_format_summary_type(str(row.get('category', ''))))}</td>"
            f"<td>{render_risk_badge(str(row.get('risk_rating', 'green')))}</td>"
            f"<td>{render_confidence_badge(str(row.get('confidence', 'low')))}</td>"
            f"<td style=\"text-align:right;\">{int(row.get('evidence_count') or 0)}</td>"
            f"<td>{escape(str(row.get('primary_recommended_action', '')))}</td>"
            "</tr>"
        )

    st.markdown(
        "<table style=\"width:100%;border-collapse:collapse;\">"
        "<thead><tr>"
        "<th style=\"text-align:left;border-bottom:1px solid #ddd;padding:0.4rem;\">Category</th>"
        "<th style=\"text-align:left;border-bottom:1px solid #ddd;padding:0.4rem;\">Risk Rating</th>"
        "<th style=\"text-align:left;border-bottom:1px solid #ddd;padding:0.4rem;\">Confidence</th>"
        "<th style=\"text-align:right;border-bottom:1px solid #ddd;padding:0.4rem;\">Evidence Count</th>"
        "<th style=\"text-align:left;border-bottom:1px solid #ddd;padding:0.4rem;\">Primary Recommended Action</th>"
        "</tr></thead>"
        "<tbody>"
        + "".join(table_rows)
        + "</tbody></table>",
        unsafe_allow_html=True,
    )


def _render_limitations(limitations: list[str]) -> None:
    if limitations:
        _render_list("Limitations", limitations)


def _render_list(title: str, values: list[str]) -> None:
    st.markdown(f"#### {title}")
    if not values:
        st.markdown("None provided.")
        return
    for value in values:
        st.markdown(f"- {value}")


def _render_citations(citations: list[dict[str, Any]], title: str, use_expanders: bool = True) -> None:
    st.markdown(f"#### {title}")
    if not citations:
        st.markdown("No citations returned.")
        return

    for index, citation in enumerate(citations, start=1):
        label = citation.get("source_label") or f"S{index}"
        document_title = citation.get("document_title", "Untitled document")
        page_start = citation.get("page_start", "?")
        page_end = citation.get("page_end", "?")
        heading = f"{label} - {document_title} - pages {page_start}-{page_end}"

        if use_expanders:
            with st.expander(heading):
                _render_citation_body(citation)
                st.caption(f"Document ID: {citation.get('document_id')}")
                st.caption(f"Chunk ID: {citation.get('chunk_id')}")
                if citation.get("full_source_text") and st.toggle(
                    f"Full source text {label}",
                    value=False,
                    key=f"full_source_{citation.get('chunk_id', index)}_{title}",
                ):
                    st.code(citation.get("full_source_text", ""), language="text")
        else:
            with st.container():
                st.markdown(f"**{heading}**")
                _render_citation_body(citation)
                st.caption(f"Document ID: {citation.get('document_id')}")
                st.caption(f"Chunk ID: {citation.get('chunk_id')}")
                if index < len(citations):
                    st.divider()


def _render_citation_body(citation: dict[str, Any]) -> None:
    if citation.get("relevance_reason"):
        st.caption(citation.get("relevance_reason"))
    st.markdown("**Relevant excerpt**")
    st.markdown(citation.get("excerpt", ""))


def build_export_filename(
    investigation_name: str,
    report_type: str,
    variant: str | None = None,
    extension: str = "md",
) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    parts = [
        _sanitize_filename_part(investigation_name or "Investigation"),
        _sanitize_filename_part(report_type),
    ]
    if variant:
        parts.append(_sanitize_filename_part(variant))
    parts.append(timestamp)
    suffix = extension.lstrip(".") or "md"
    return "_".join(part for part in parts if part) + f".{suffix}"


def _sanitize_filename_part(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    return sanitized or "report"


def _with_report_metadata(
    payload: dict[str, Any],
    report_type: str,
    variant: str | None = None,
) -> dict[str, Any]:
    enriched = dict(payload)
    enriched["report_metadata"] = {
        "investigation": st.session_state.get("active_document_set_name") or "Single Document",
        "report_type": report_type,
        "plan_type": variant,
        "provider": LLM_PROVIDER_OPTIONS.get(st.session_state.get("active_llm_provider", "mock"), "Mock"),
        "model": st.session_state.get("active_llm_model") or DEFAULT_LLM_MODELS["mock"],
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "document_set_id": st.session_state.get("active_document_set_id") or payload.get("document_set_id", ""),
        "included_documents": _included_document_names(),
    }
    return enriched


def _included_document_names() -> list[str]:
    names = [
        str(document.get("filename", "")).strip()
        for document in st.session_state.get("uploaded_documents", [])
        if str(document.get("filename", "")).strip()
    ]
    if names:
        return names
    uploaded_filename = str(st.session_state.get("uploaded_filename", "")).strip()
    return [uploaded_filename] if uploaded_filename else []


def _render_report_metadata(payload: dict[str, Any]) -> None:
    metadata = _report_metadata(payload)
    st.caption(
        f"Provider: {metadata['provider']} | Model: {metadata['model']} | Generated: {metadata['generated_at']}"
    )


def _report_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(payload.get("report_metadata") or {})
    metadata.setdefault("investigation", st.session_state.get("active_document_set_name") or "Investigation")
    metadata.setdefault("report_type", payload.get("report_type") or payload.get("summary_type") or "report")
    metadata.setdefault("plan_type", payload.get("plan_type"))
    metadata.setdefault("provider", LLM_PROVIDER_OPTIONS.get(st.session_state.get("active_llm_provider", "mock"), "Mock"))
    metadata.setdefault("model", st.session_state.get("active_llm_model") or DEFAULT_LLM_MODELS["mock"])
    metadata.setdefault("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
    metadata.setdefault(
        "document_set_id",
        payload.get("document_set_id") or st.session_state.get("active_document_set_id", ""),
    )
    metadata.setdefault("included_documents", _included_document_names())
    return metadata


def _metadata_lines(payload: dict[str, Any], default_report_type: str) -> list[str]:
    metadata = _report_metadata(payload)
    report_type = metadata.get("report_type") or default_report_type
    plan_type = metadata.get("plan_type")
    included_documents = metadata.get("included_documents") or []
    lines = [
        f"- Investigation: {metadata.get('investigation', 'Investigation')}",
        f"- Report Type: {report_type}",
    ]
    if plan_type:
        lines.append(f"- Plan Type: {plan_type}")
    lines.extend(
        [
            f"- Provider: {metadata.get('provider', 'Mock')}",
            f"- Model: {metadata.get('model', 'mock')}",
            f"- Generated At: {metadata.get('generated_at', '')}",
            f"- Document Set ID: `{metadata.get('document_set_id', '')}`",
            f"- Included Documents: {', '.join(included_documents) if included_documents else 'Not specified'}",
            "",
        ]
    )
    return lines


def _export_filename(payload: dict[str, Any], report_type: str, variant: str | None = None) -> str:
    metadata = _report_metadata(payload)
    return build_export_filename(str(metadata.get("investigation", "Investigation")), report_type, variant)


def _download_key(payload: dict[str, Any], report_type: str, variant: str | None = None) -> str:
    metadata = _report_metadata(payload)
    raw = "_".join(
        [
            "download",
            report_type,
            str(metadata.get("document_set_id") or payload.get("document_id") or "single"),
            variant or str(metadata.get("plan_type") or ""),
            str(metadata.get("generated_at") or ""),
        ]
    )
    return _sanitize_filename_part(raw).lower()


def _build_markdown_memo(response: dict[str, Any]) -> str:
    memo = response.get("memo", {})
    lines = [
        f"# {_format_summary_type(response.get('summary_type', 'board_brief'))}",
        "",
        *_metadata_lines(response, "board_summary"),
        f"Document ID: `{response.get('document_id', '')}`",
        f"Investigation ID: `{response.get('document_set_id', '')}`",
        f"Scope: `{response.get('scope', 'document')}`",
        f"Confidence: **{str(response.get('confidence', 'low')).title()}**",
        "",
        "## Executive Summary",
        normalize_text_field(memo.get("executive_summary", "")),
        "",
    ]

    lines.extend(_markdown_list("Key Risks", memo.get("key_risks", [])))
    lines.extend(_markdown_list("Evidence", memo.get("evidence", [])))
    lines.extend(_markdown_list("Board Questions", memo.get("board_questions", [])))
    lines.extend(_markdown_list("Recommended Actions", memo.get("recommended_actions", [])))
    lines.extend(_markdown_list("Limitations", memo.get("limitations", [])))
    lines.extend(["## Citations", ""])

    for index, citation in enumerate(response.get("citations", []), start=1):
        label = citation.get("source_label") or f"S{index}"
        lines.extend(
            [
                f"### {label}",
                f"- Document: {citation.get('document_title', 'Untitled document')}",
                f"- Pages: {citation.get('page_start', '?')}-{citation.get('page_end', '?')}",
                f"- Document ID: `{citation.get('document_id', '')}`",
                f"- Chunk ID: `{citation.get('chunk_id', '')}`",
                f"- Relevance: {citation.get('relevance_reason') or 'Not specified.'}",
                "",
                "**Relevant excerpt**",
                "",
                citation.get("excerpt", ""),
                "",
            ]
        )
        if citation.get("full_source_text"):
            lines.extend(
                [
                    "<details>",
                    "<summary>Full source text</summary>",
                    "",
                    "```text",
                    citation.get("full_source_text", ""),
                    "```",
                    "",
                    "</details>",
                    "",
                ]
            )

    return "\n".join(lines).strip() + "\n"


def _build_evaluation_markdown(response: dict[str, Any]) -> str:
    lines = [
        "# Evaluation Report",
        "",
        *_metadata_lines(response, "evaluation_report"),
        f"Evaluation Run ID: `{response.get('evaluation_run_id', '')}`",
        f"Document ID: `{response.get('document_id', '')}`",
        f"Evaluation Type: `{response.get('evaluation_type', '')}`",
        f"Average Score: **{response.get('average_score', 0):.2f}**",
        "",
    ]

    for result in response.get("results", []):
        lines.extend(
            [
                f"## {result.get('question', '')}",
                "",
                f"- Citation Score: {result.get('citation_score', 0):.2f}",
                f"- Groundedness Score: {result.get('groundedness_score', 0):.2f}",
                f"- Relevance Score: {result.get('relevance_score', 0):.2f}",
                f"- Executive Usefulness Score: {result.get('executive_usefulness_score', 0):.2f}",
                f"- Overall Score: {result.get('overall_score', 0):.2f}",
                "",
                "### Answer",
                result.get("answer", ""),
                "",
            ]
        )
        lines.extend(_markdown_list("Notes", result.get("notes", [])))
        lines.extend(["### Citations", ""])
        for index, citation in enumerate(result.get("citations", []), start=1):
            label = citation.get("source_label") or f"S{index}"
            lines.extend(
                [
                    f"#### {label}",
                    f"- Document: {citation.get('document_title', 'Untitled document')}",
                    f"- Pages: {citation.get('page_start', '?')}-{citation.get('page_end', '?')}",
                    f"- Document ID: `{citation.get('document_id', '')}`",
                    f"- Chunk ID: `{citation.get('chunk_id', '')}`",
                    f"- Relevance: {citation.get('relevance_reason') or 'Not specified.'}",
                    "",
                    "**Relevant excerpt**",
                    "",
                    citation.get("excerpt", ""),
                    "",
                ]
            )
            if citation.get("full_source_text"):
                lines.extend(
                    [
                        "<details>",
                        "<summary>Full source text</summary>",
                        "",
                        "```text",
                        citation.get("full_source_text", ""),
                        "```",
                        "",
                        "</details>",
                        "",
                    ]
                )

    return "\n".join(lines).strip() + "\n"


def _build_technology_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Technology Due Diligence Report",
        "",
        *_metadata_lines(report, "technology_due_diligence"),
        f"Investigation ID: `{report.get('document_set_id', '')}`",
        f"Report Type: `{report.get('report_type', 'technology_due_diligence')}`",
        "",
        "## Executive Summary",
        normalize_text_field(report.get("executive_summary", "")),
        "",
        "## Overall Risk Rating",
        f"Risk Rating: **{str(report.get('overall_risk_rating', 'unknown')).title()}**",
        f"Confidence: **{str(report.get('confidence', 'low')).title()}**",
        "",
    ]
    lines.extend(_markdown_risk_heatmap(report.get("risk_heatmap", [])))
    lines.extend(_markdown_list("Top 5 Risks", report.get("top_5_risks", [])))
    lines.extend(["## Findings", ""])
    for finding in report.get("findings", []):
        lines.extend(
            [
                f"### {_format_summary_type(finding.get('category', 'finding'))}",
                f"- Title: {finding.get('title', '')}",
                f"- Risk Rating: {str(finding.get('risk_rating', '')).title()}",
                f"- Confidence: {str(finding.get('confidence', '')).title()}",
                f"- Recommended Owner: {finding.get('recommended_owner', '')}",
                f"- Risk Rationale: {finding.get('risk_rationale', '')}",
                f"- Confidence Rationale: {finding.get('confidence_rationale', '')}",
                "",
                f"**Business Impact:** {finding.get('business_impact', '')}",
                "",
                f"**Evidence Summary:** {finding.get('evidence_summary', '')}",
                "",
                f"**Recommended Action:** {finding.get('recommended_action', '')}",
                "",
                "#### Citations",
                "",
            ]
        )
        lines.extend(_markdown_citations(finding.get("citations", []), heading_level="#####"))

    lines.extend(_markdown_list("Management Questions", report.get("management_questions", [])))
    lines.extend(_markdown_list("Board Discussion Points", report.get("board_discussion_points", [])))
    lines.extend(_markdown_list("Recommended Actions", report.get("recommended_actions", [])))
    lines.extend(["## 30/60/90-Day Plan", ""])
    plan = report.get("thirty_sixty_ninety_day_plan", {})
    lines.extend(_markdown_list("Days 1-30", plan.get("days_1_30", [])))
    lines.extend(_markdown_list("Days 31-60", plan.get("days_31_60", [])))
    lines.extend(_markdown_list("Days 61-90", plan.get("days_61_90", [])))
    lines.extend(_markdown_list("Limitations", report.get("limitations", [])))
    lines.extend(["## Citations", ""])
    lines.extend(_markdown_citations(report.get("citations", []), heading_level="###"))
    return "\n".join(lines).strip() + "\n"


def _build_hundred_day_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# 100-Day Technology Plan",
        "",
        *_metadata_lines(plan, "100_day_plan"),
        f"Investigation ID: `{plan.get('document_set_id', '')}`",
        f"Plan Type: `{plan.get('plan_type', '')}`",
        f"Overall Priority: **{str(plan.get('overall_priority', '')).title()}**",
        "",
        "## Executive Summary",
        normalize_text_field(plan.get("executive_summary", "")),
        "",
    ]
    lines.extend(_markdown_timeline_summary(plan.get("timeline_summary", [])))
    lines.extend(_markdown_plan_at_a_glance(plan.get("plan_at_a_glance", [])))
    lines.extend(_markdown_risk_heatmap(plan.get("risk_heatmap", [])))
    if plan.get("quick_wins"):
        lines.extend(_markdown_list("Quick Wins", plan.get("quick_wins", [])))
    lines.extend(_markdown_plan_actions("Days 1-30", plan.get("days_1_30", [])))
    lines.extend(_markdown_plan_actions("Days 31-60", plan.get("days_31_60", [])))
    lines.extend(_markdown_plan_actions("Days 61-90", plan.get("days_61_90", [])))
    lines.extend(_markdown_plan_actions("Days 91-100 / Board Readout", plan.get("days_91_100", [])))
    lines.extend(_markdown_list("Success Metrics", plan.get("success_metrics", [])))
    lines.extend(_markdown_board_checkpoints(plan.get("board_checkpoints", [])))
    lines.extend(_markdown_list("Dependencies", plan.get("dependencies", [])))
    lines.extend(_markdown_list("Limitations", plan.get("limitations", [])))
    return "\n".join(lines).strip() + "\n"


def _build_hundred_day_one_pager_markdown(plan: dict[str, Any]) -> str:
    one_pager = plan.get("executive_one_pager") or {}
    lines = [
        "# Executive One-Pager: 100-Day Technology Plan",
        "",
        *_metadata_lines(plan, "100_day_plan_one_pager"),
        f"Investigation ID: `{plan.get('document_set_id', '')}`",
        f"Plan Type: `{plan.get('plan_type', '')}`",
        "",
        "## Executive Summary",
        normalize_text_field(one_pager.get("executive_summary", "")),
        "",
        "## Current State",
        one_pager.get("current_state", ""),
        "",
        "## Target State",
        one_pager.get("target_state", ""),
        "",
        "## Overall Risk",
        one_pager.get("overall_risk", ""),
        "",
    ]
    lines.extend(_markdown_list("Top 5 Priorities", one_pager.get("top_5_priorities", [])))
    lines.extend(_markdown_timeline_summary(plan.get("timeline_summary", [])))
    lines.extend(_markdown_risk_heatmap(plan.get("risk_heatmap", [])))
    lines.extend(_markdown_list("First 30 Days", one_pager.get("first_30_days", [])))
    lines.extend(_markdown_list("Days 31-60", one_pager.get("days_31_60", [])))
    lines.extend(_markdown_list("Days 61-90", one_pager.get("days_61_90", [])))
    lines.extend(_markdown_list("Board Decisions Required", one_pager.get("board_decisions_required", [])))
    lines.extend(_markdown_list("Success Metrics", one_pager.get("success_metrics", [])))
    lines.extend(_markdown_list("Key Dependencies", one_pager.get("key_dependencies", [])))
    return "\n".join(lines).strip() + "\n"


def _markdown_plan_at_a_glance(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "## 100-Day Plan at a Glance",
        "",
        "| Timeframe | Primary Objective | Key Actions | Success Measures | Risk Reduced |",
        "| --- | --- | --- | --- | --- |",
    ]
    if not rows:
        lines.extend(["| None provided. |  |  |  |  |", ""])
        return lines
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.get("timeframe", ""),
                    row.get("primary_objective", ""),
                    row.get("key_actions", ""),
                    row.get("success_measures", ""),
                    row.get("risk_reduced", ""),
                ]
            )
            + " |"
        )
    lines.append("")
    return lines


def _markdown_timeline_summary(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "## Timeline Summary",
        "",
        "| Phase | Primary Objective | Key Actions | Expected Outcomes | Risk Reduced | Board Checkpoint |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if not rows:
        lines.extend(["| None provided. |  |  |  |  |  |", ""])
        return lines
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("phase", "")),
                    str(row.get("primary_objective", "")),
                    str(row.get("key_actions", "")),
                    str(row.get("expected_outcomes", "")),
                    str(row.get("risk_reduced", "")),
                    str(row.get("board_checkpoint", "")),
                ]
            )
            + " |"
        )
    lines.append("")
    return lines


def _markdown_risk_heatmap(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "## Executive Risk Heatmap",
        "",
        "| Category | Risk Rating | Confidence | Evidence Count | Primary Recommended Action |",
        "| --- | --- | --- | ---: | --- |",
    ]
    if not rows:
        lines.extend(["| None provided. |  |  | 0 |  |", ""])
        return lines
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _format_summary_type(str(row.get("category", ""))),
                    str(row.get("risk_rating", "")).title(),
                    str(row.get("confidence", "")).title(),
                    str(row.get("evidence_count", 0)),
                    str(row.get("primary_recommended_action", "")).replace("|", "\\|"),
                ]
            )
            + " |"
        )
    lines.append("")
    return lines


def _markdown_plan_actions(title: str, actions: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    if not actions:
        lines.extend(["No actions assigned.", ""])
        return lines

    for index, action in enumerate(actions, start=1):
        lines.extend(
            [
                f"### {index}. {action.get('action', '')}",
                f"- Priority: {str(action.get('priority', '')).title()}",
                f"- Owner: {action.get('owner', '')}",
                f"- Business Rationale: {action.get('business_rationale', '')}",
                f"- Success Metric: {action.get('success_metric', '')}",
                f"- Risk Reduction: {action.get('risk_reduction', '')}",
                "",
                "#### Deliverables",
                "",
            ]
        )
        lines.extend([f"- {deliverable}" for deliverable in action.get("deliverables", [])])
        lines.extend(
            [
                "",
                "#### Citations",
                "",
            ]
        )
        lines.extend(_markdown_citations(action.get("citations", []), heading_level="#####"))
    return lines


def _markdown_board_checkpoints(checkpoints: list[dict[str, Any]]) -> list[str]:
    lines = ["## Board Checkpoints", ""]
    if not checkpoints:
        lines.extend(["None provided.", ""])
        return lines
    for checkpoint in checkpoints:
        lines.extend(
            [
                f"### {checkpoint.get('timeframe', '')}",
                f"- Question for management: {checkpoint.get('question', '')}",
                f"- Evidence requested: {checkpoint.get('evidence_requested', '')}",
                f"- Decision needed: {checkpoint.get('decision_needed') or 'None specified.'}",
                "",
            ]
        )
    return lines


def _markdown_citations(citations: list[dict[str, Any]], heading_level: str) -> list[str]:
    if not citations:
        return ["No citations returned.", ""]

    lines = []
    for index, citation in enumerate(citations, start=1):
        label = citation.get("source_label") or f"S{index}"
        lines.extend(
            [
                f"{heading_level} {label}",
                f"- Document: {citation.get('document_title', 'Untitled document')}",
                f"- Pages: {citation.get('page_start', '?')}-{citation.get('page_end', '?')}",
                f"- Document ID: `{citation.get('document_id', '')}`",
                f"- Chunk ID: `{citation.get('chunk_id', '')}`",
                f"- Relevance: {citation.get('relevance_reason') or 'Not specified.'}",
                "",
                "**Relevant excerpt**",
                "",
                citation.get("excerpt", ""),
                "",
            ]
        )
    return lines


def _markdown_list(title: str, values: list[str]) -> list[str]:
    lines = [f"## {title}", ""]
    if not values:
        lines.extend(["None provided.", ""])
        return lines
    lines.extend([f"- {value}" for value in values])
    lines.append("")
    return lines


def _format_summary_type(summary_type: str) -> str:
    return summary_type.replace("_", " ").title()


if __name__ == "__main__":
    main()
