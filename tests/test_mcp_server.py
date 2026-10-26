"""Tests for the MCP adapter. The server is exercised in-process through the official MCP client."""

import asyncio
from uuid import uuid4

import pytest
from mcp import Client

from app.diligence.service import DiligenceDocumentSetNotFoundError
from app.mcp_server import create_server
from app.mcp_server.__main__ import main
from app.mcp_server.audit import MemoryAuditSink
from app.retrieval.vector_search import SearchResult

EXPECTED_TOOLS = {
    "list_investigations",
    "search_evidence",
    "ask_advisor",
    "board_summary",
    "technology_risk_scorecard",
    "board_brief",
    "ai_governance_assessment",
    "ai_replicability_risk_assessment",
    "ai_knowledge_governance_assessment",
    "cra_readiness_assessment",
    "technology_due_diligence_report",
    "hundred_day_plan",
}


class FakeSession:
    closed = False

    def get(self, model, object_id):
        return None

    def close(self):
        self.closed = True


def make_result(content="The platform has a single engineer who owns all production deployments."):
    return SearchResult(
        document_id=uuid4(),
        document_title="Technology Assessment",
        chunk_id=uuid4(),
        chunk_index=0,
        content=content,
        page_start=3,
        page_end=4,
        similarity_score=0.87,
        source_type="technology_assessment",
        classification="confidential",
    )


def make_server(session_factory):
    # These tests cover tool behavior, not the audit table, so audit goes to memory.
    return create_server(session_factory, audit_sink=MemoryAuditSink())


def run_client(server, scenario):
    async def _run():
        async with Client(server) as client:
            return await scenario(client)

    return asyncio.run(_run())


def test_server_exposes_expected_tools_with_structured_output():
    tools = run_client(make_server(FakeSession), lambda c: c.list_tools()).tools

    assert {tool.name for tool in tools} == EXPECTED_TOOLS
    for tool in tools:
        assert tool.description
        assert tool.output_schema is not None
        assert tool.annotations.read_only_hint is True


def test_tools_never_accept_provider_api_keys():
    tools = run_client(make_server(FakeSession), lambda c: c.list_tools()).tools

    for tool in tools:
        assert "llm_api_key" not in tool.input_schema.get("properties", {})


def test_ask_advisor_reuses_service_and_returns_citations(monkeypatch):
    monkeypatch.setattr("app.advisor.service.search_similar_chunks", lambda **kwargs: [make_result()])
    session = FakeSession()

    result = run_client(
        make_server(lambda: session),
        lambda c: c.call_tool(
            "ask_advisor",
            {"question": "What key-person risk exists?", "llm_provider": "mock"},
        ),
    )

    assert result.is_error is False
    payload = result.structured_content
    assert payload["question"] == "What key-person risk exists?"
    assert payload["citations"][0]["document_title"] == "Technology Assessment"
    assert payload["confidence"] in {"high", "medium", "low"}
    assert session.closed is True


def test_search_evidence_returns_excerpts(monkeypatch):
    captured = {}

    def fake_search(**kwargs):
        captured.update(kwargs)
        return [make_result()]

    monkeypatch.setattr("app.retrieval.vector_search.search_similar_chunks", fake_search)
    document_set_id = uuid4()

    result = run_client(
        make_server(FakeSession),
        lambda c: c.call_tool(
            "search_evidence",
            {"query": "deployment ownership", "document_set_id": str(document_set_id), "top_k": 3},
        ),
    )

    assert result.is_error is False
    assert captured["document_set_id"] == document_set_id
    assert captured["top_k"] == 3
    hit = result.structured_content["results"][0]
    assert hit["page_start"] == 3
    assert "single engineer" in hit["content"]


def test_assessment_tool_maps_not_found_to_tool_error(monkeypatch):
    def missing(**kwargs):
        raise DiligenceDocumentSetNotFoundError("Document set not found.")

    monkeypatch.setattr("app.executive.service.generate_board_brief", missing)

    result = run_client(
        make_server(FakeSession),
        lambda c: c.call_tool("board_brief", {"document_set_id": str(uuid4())}),
    )

    assert result.is_error is True
    assert "Document set not found." in result.content[0].text


def test_invalid_arguments_are_rejected():
    result = run_client(
        make_server(FakeSession),
        lambda c: c.call_tool("hundred_day_plan", {"document_set_id": "not-a-uuid"}),
    )

    assert result.is_error is True


def test_resources_and_prompts_are_listed():
    async def scenario(client):
        resources = await client.list_resources()
        templates = await client.list_resource_templates()
        prompts = await client.list_prompts()
        prompt = await client.get_prompt("board_meeting_prep", {"document_set_id": "abc"})
        return resources, templates, prompts, prompt

    resources, templates, prompts, prompt = run_client(make_server(FakeSession), scenario)

    assert [str(r.uri) for r in resources.resources] == ["eaia://investigations"]
    assert [t.uri_template for t in templates.resource_templates] == ["eaia://investigations/{document_set_id}"]
    assert {p.name for p in prompts.prompts} == {"board_meeting_prep", "diligence_review"}
    assert "technology_risk_scorecard" in prompt.messages[0].content.text


def test_investigation_resource_reports_missing_set():
    from mcp.shared.exceptions import MCPError

    with pytest.raises(BaseException) as exc_info:
        run_client(
            make_server(FakeSession),
            lambda c: c.read_resource(f"eaia://investigations/{uuid4()}"),
        )

    error = exc_info.value
    while isinstance(error, BaseExceptionGroup):
        error = error.exceptions[0]
    assert isinstance(error, MCPError)
    assert "Investigation not found" in str(error)


def test_entry_point_selects_transport(monkeypatch):
    calls = []

    class StubServer:
        def run(self, transport, **kwargs):
            calls.append((transport, kwargs))

    created = []

    def fake_create_server(**kwargs):
        created.append(kwargs)
        return StubServer()

    monkeypatch.setattr("app.mcp_server.__main__.create_server", fake_create_server)

    main([])
    main(["--transport", "streamable-http", "--port", "9000"])

    assert calls == [("stdio", {}), ("streamable-http", {"host": "127.0.0.1", "port": 9000})]
    assert created[0]["transport"] == "stdio"
    assert created[1]["transport"] == "http"
    assert created[1]["token_verifier"] is None
