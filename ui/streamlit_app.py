import json
import os
from pathlib import Path
from typing import Any

import requests
import streamlit as st


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
    "evaluation_response",
    "evaluation_questions_text",
    "evaluation_questions_initialized",
]


def main() -> None:
    st.set_page_config(page_title="Executive AI Advisor", layout="wide")
    _initialize_state()
    _apply_styles()

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
        "evaluation_response": None,
        "evaluation_questions_text": "",
        "evaluation_questions_initialized": False,
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
    if document_set_id:
        if st.button("Process All", use_container_width=True):
            detail = _load_active_document_set_detail()
            if not detail:
                return
            _sync_active_document_set_state(detail)
            if not st.session_state.uploaded_documents:
                st.warning("No backend documents are currently attached to this investigation.")
                return
            response = _post_json(f"/document-sets/{document_set_id}/process", {})
            if response:
                documents = response.get("documents", [])
                st.success(f"Processed {len(documents)} document(s) in active investigation.")
                for document in documents:
                    st.write(f"- {document.get('filename')}: **{document.get('status')}**")
                refreshed = _load_active_document_set_detail()
                if refreshed:
                    _sync_active_document_set_state(refreshed)
                st.rerun()
        st.caption("Runs parse, chunk, and embed for documents in the active investigation that need processing.")
        return

    document_id = _active_document_id()
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Parse document", disabled=not document_id, use_container_width=True):
            _run_processing_step("parse")
    with col2:
        if st.button("Chunk document", disabled=not document_id, use_container_width=True):
            _run_processing_step("chunk")
    with col3:
        if st.button("Embed document", disabled=not document_id, use_container_width=True):
            _run_processing_step("embed")

    if not document_id:
        st.info("Upload a PDF before running the processing pipeline.")
    elif st.session_state.document_status:
        st.write(f"Current status: **{st.session_state.document_status}**")


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
        with st.spinner("Generating board memo"):
            response = _post_json("/advisor/board-summary", payload)
        if response:
            if response.get("document_id"):
                st.session_state.document_id = response["document_id"]
            st.session_state.board_summary = response

    if st.session_state.board_summary:
        _render_board_memo(st.session_state.board_summary)


def _render_board_memo(response: dict[str, Any]) -> None:
    memo = response.get("memo", {})
    title = _format_summary_type(response.get("summary_type", "board_brief"))
    st.subheader(title)
    _render_confidence(response.get("confidence", "low"))

    st.markdown("#### Executive Summary")
    st.markdown(memo.get("executive_summary", "No executive summary returned."))

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
                },
            )
        if response:
            st.session_state.technology_report = response

    report = st.session_state.technology_report
    if report:
        _render_technology_report(report)


def _render_technology_report(report: dict[str, Any]) -> None:
    st.subheader("Technology Due Diligence Report")
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
    st.markdown(report.get("executive_summary", "No executive summary returned."))

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
        file_name="Technology Due Diligence Report.md",
        mime="text/markdown",
        key=f"download_report_inline_{report.get('report_type', 'technology_due_diligence')}_{report.get('document_set_id', 'unknown')}",
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
            st.session_state.evaluation_response = response

    response = st.session_state.evaluation_response
    if not response:
        return

    st.metric("Average Score", f"{response.get('average_score', 0):.2f}")
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
        file_name="Evaluation Report.md",
        mime="text/markdown",
        key=f"download_evaluation_report_markdown_{response.get('evaluation_run_id', 'latest')}",
        use_container_width=True,
    )


def _render_evidence_section() -> None:
    st.header("Citations / Evidence")
    board_summary = st.session_state.board_summary
    technology_report = st.session_state.technology_report
    qa_response = st.session_state.qa_response
    evaluation_response = st.session_state.evaluation_response

    if not board_summary and not technology_report and not qa_response and not evaluation_response:
        st.info("Run Executive Q&A, generate a report, generate a board summary, or run evaluation to view citations.")
        return

    if board_summary:
        _render_citations(board_summary.get("citations", []), title="Board Summary Evidence")
    if technology_report:
        _render_citations(technology_report.get("citations", []), title="Technology Diligence Evidence")
    if qa_response:
        _render_citations(qa_response.get("citations", []), title="Q&A Evidence")
    if evaluation_response:
        for result in evaluation_response.get("results", []):
            _render_citations(result.get("citations", []), title=f"Evaluation Evidence: {result.get('question', '')}")


def _render_export_section() -> None:
    st.header("Export Markdown")
    board_summary = st.session_state.board_summary
    technology_report = st.session_state.technology_report

    if not board_summary and not technology_report:
        st.info("Generate a board summary or technology due diligence report before exporting.")
        return

    if board_summary:
        markdown = _build_markdown_memo(board_summary)
        st.download_button(
            label="Download Board Memo.md",
            data=markdown,
            file_name="Board Memo.md",
            mime="text/markdown",
            key=f"download_board_summary_markdown_{board_summary.get('summary_type', 'board')}_{board_summary.get('document_set_id') or board_summary.get('document_id') or 'latest'}",
            use_container_width=True,
        )
        with st.expander("Board memo Markdown preview"):
            st.code(markdown, language="markdown")

    if technology_report:
        report_markdown = _build_technology_report_markdown(technology_report)
        st.download_button(
            label="Download Technology Due Diligence Report.md",
            data=report_markdown,
            file_name="Technology Due Diligence Report.md",
            mime="text/markdown",
            key=f"download_technology_diligence_markdown_{technology_report.get('report_type', 'technology_due_diligence')}_{technology_report.get('document_set_id', 'unknown')}",
            use_container_width=True,
        )
        with st.expander("Technology diligence Markdown preview"):
            st.code(report_markdown, language="markdown")


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


def _run_processing_step(step: str) -> None:
    document_id = _active_document_id()
    if not document_id:
        st.warning("Upload or enter a document ID first.")
        return

    labels = {"parse": "Parsing", "chunk": "Chunking", "embed": "Embedding"}
    with st.spinner(labels[step]):
        response = _post_json(f"/documents/{document_id}/{step}", {})

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
    st.session_state.evaluation_response = None


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
    st.session_state.evaluation_response = None


def _clear_local_ui_state() -> None:
    for key in LOCAL_UI_STATE_KEYS:
        if key in {"uploaded_documents", "selected_documents"}:
            st.session_state[key] = []
        elif key in {"qa_response", "board_summary", "technology_report", "evaluation_response"}:
            st.session_state[key] = None
        elif key == "evaluation_questions_initialized":
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
    st.session_state.evaluation_response = None


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


def _build_markdown_memo(response: dict[str, Any]) -> str:
    memo = response.get("memo", {})
    lines = [
        f"# {_format_summary_type(response.get('summary_type', 'board_brief'))}",
        "",
        f"Document ID: `{response.get('document_id', '')}`",
        f"Investigation ID: `{response.get('document_set_id', '')}`",
        f"Scope: `{response.get('scope', 'document')}`",
        f"Confidence: **{str(response.get('confidence', 'low')).title()}**",
        "",
        "## Executive Summary",
        memo.get("executive_summary", ""),
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
        f"Investigation ID: `{report.get('document_set_id', '')}`",
        f"Report Type: `{report.get('report_type', 'technology_due_diligence')}`",
        "",
        "## Executive Summary",
        report.get("executive_summary", ""),
        "",
        "## Overall Risk Rating",
        f"Risk Rating: **{str(report.get('overall_risk_rating', 'unknown')).title()}**",
        f"Confidence: **{str(report.get('confidence', 'low')).title()}**",
        "",
    ]
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
