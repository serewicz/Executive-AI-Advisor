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
SUMMARY_TYPES = [
    "technology_risk",
    "diligence_summary",
    "ai_readiness",
    "security_governance",
    "board_brief",
]


def main() -> None:
    st.set_page_config(page_title="Executive AI Advisor", layout="wide")
    _initialize_state()
    _apply_styles()

    st.title("Executive AI Advisor")
    st.caption("Board-facing document intelligence demo")
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
    _render_evaluation_section()
    st.divider()
    _render_evidence_section()
    st.divider()
    _render_export_section()


def _initialize_state() -> None:
    defaults = {
        "document_id": "",
        "summary_document_id": "",
        "uploaded_filename": "",
        "document_status": "",
        "qa_response": None,
        "board_summary": None,
        "evaluation_response": None,
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
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_upload_section() -> None:
    st.header("Document Upload")
    st.markdown(
        '<div class="section-note">Upload a PDF and capture the governance metadata used downstream.</div>',
        unsafe_allow_html=True,
    )

    with st.form("upload_form", clear_on_submit=False):
        uploaded_file = st.file_uploader("PDF file", type=["pdf"])
        col1, col2 = st.columns(2)
        with col1:
            source_type = st.selectbox("Source type", SOURCE_TYPES)
        with col2:
            classification = st.selectbox("Classification", CLASSIFICATIONS)

        submitted = st.form_submit_button("Upload PDF", use_container_width=True)

    if submitted:
        if uploaded_file is None:
            st.warning("Select a PDF before uploading.")
            return

        with st.spinner("Uploading document"):
            response = _upload_document(uploaded_file, source_type, classification)

        if response is None:
            return

        st.session_state.document_id = response["document_id"]
        st.session_state.summary_document_id = response["document_id"]
        st.session_state.uploaded_filename = response.get("filename", uploaded_file.name)
        st.session_state.document_status = response.get("status", "uploaded")
        st.session_state.qa_response = None
        st.session_state.board_summary = None
        st.session_state.evaluation_response = None

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
    question = st.text_area(
        "Question",
        value="What are the main technology risks?",
        height=110,
    )
    top_k = st.slider("Sources to retrieve", min_value=1, max_value=20, value=5, key="qa_top_k")
    search_globally = st.checkbox("Search across all documents", value=False)
    if document_id and not search_globally:
        st.caption(f"Scoped to document: {document_id}")

    if st.button("Ask Advisor", disabled=not question.strip(), use_container_width=True):
        with st.spinner("Retrieving evidence and drafting answer"):
            response = _post_json(
                "/advisor/ask",
                _build_qa_payload(
                    question=question.strip(),
                    top_k=top_k,
                    document_id=document_id,
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
        else:
            st.caption("Search scope: all documents")
        _render_limitations(response.get("limitations", []))
        _render_citations(response.get("citations", []), title="Q&A Citations")


def _build_qa_payload(
    question: str,
    top_k: int,
    document_id: str,
    search_globally: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "question": question,
        "top_k": top_k,
        "source_type": None,
        "classification": None,
    }
    if document_id and not search_globally:
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

    if st.button("Generate Board Summary", disabled=not document_id.strip(), use_container_width=True):
        with st.spinner("Generating board memo"):
            response = _post_json(
                "/advisor/board-summary",
                {
                    "document_id": document_id.strip(),
                    "summary_type": summary_type,
                    "top_k": top_k,
                },
            )
        if response:
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


def _render_evaluation_section() -> None:
    st.header("Evaluation")
    st.markdown(
        '<div class="section-note">Run deterministic checks for citation quality, groundedness, relevance, and executive usefulness.</div>',
        unsafe_allow_html=True,
    )

    document_id = st.text_input(
        "Evaluation document ID",
        value=_active_document_id(),
        placeholder="Paste or upload a document ID",
        key="evaluation_document_id",
    )
    questions = _load_default_evaluation_questions()

    with st.expander("Default evaluation questions", expanded=False):
        for question in questions:
            st.markdown(f"- {question['question']}")

    if st.button("Run Evaluation", disabled=not document_id.strip(), use_container_width=True):
        with st.spinner("Running deterministic evaluation"):
            response = _post_json(
                "/evaluation/run",
                {
                    "document_id": document_id.strip(),
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
        use_container_width=True,
    )


def _render_evidence_section() -> None:
    st.header("Citations / Evidence")
    board_summary = st.session_state.board_summary
    qa_response = st.session_state.qa_response
    evaluation_response = st.session_state.evaluation_response

    if not board_summary and not qa_response and not evaluation_response:
        st.info("Run Executive Q&A, generate a board summary, or run evaluation to view citations.")
        return

    if board_summary:
        _render_citations(board_summary.get("citations", []), title="Board Summary Evidence")
    if qa_response:
        _render_citations(qa_response.get("citations", []), title="Q&A Evidence")
    if evaluation_response:
        for result in evaluation_response.get("results", []):
            _render_citations(result.get("citations", []), title=f"Evaluation Evidence: {result.get('question', '')}")


def _render_export_section() -> None:
    st.header("Export Markdown")
    board_summary = st.session_state.board_summary

    if not board_summary:
        st.info("Generate a board summary before exporting a memo.")
        return

    markdown = _build_markdown_memo(board_summary)
    st.download_button(
        label="Download Board Memo.md",
        data=markdown,
        file_name="Board Memo.md",
        mime="text/markdown",
        use_container_width=True,
    )
    with st.expander("Markdown preview"):
        st.code(markdown, language="markdown")


def _upload_document(uploaded_file, source_type: str, classification: str) -> dict[str, Any] | None:
    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            "application/pdf",
        )
    }
    data = {"source_type": source_type, "classification": classification}
    return _request("POST", "/documents/upload", files=files, data=data, expected_status={201})


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


def _post_json(path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    return _request("POST", path, json=payload)


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
    return f"Backend returned {response.status_code}: {detail}"


def _active_document_id() -> str:
    return (st.session_state.get("summary_document_id") or st.session_state.document_id or "").strip()


def _render_confidence(confidence: str) -> None:
    normalized = confidence if confidence in {"high", "medium", "low"} else "low"
    st.markdown(
        f'<span class="confidence confidence-{normalized}">Confidence: {normalized.title()}</span>',
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
                st.write(citation.get("excerpt", ""))
                st.caption(f"Document ID: {citation.get('document_id')}")
                st.caption(f"Chunk ID: {citation.get('chunk_id')}")
        else:
            with st.container():
                st.markdown(f"**{heading}**")
                st.markdown(citation.get("excerpt", ""))
                st.caption(f"Document ID: {citation.get('document_id')}")
                st.caption(f"Chunk ID: {citation.get('chunk_id')}")
                if index < len(citations):
                    st.divider()


def _build_markdown_memo(response: dict[str, Any]) -> str:
    memo = response.get("memo", {})
    lines = [
        f"# {_format_summary_type(response.get('summary_type', 'board_brief'))}",
        "",
        f"Document ID: `{response.get('document_id', '')}`",
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
                "",
                citation.get("excerpt", ""),
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
                    "",
                    citation.get("excerpt", ""),
                    "",
                ]
            )

    return "\n".join(lines).strip() + "\n"


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
