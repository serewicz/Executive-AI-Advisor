"""Tests for ADR 0001: MCP authentication, model allowlist, error handling, rate limits, and audit."""

from __future__ import annotations

import ast
import asyncio
import json
import logging
import re
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from mcp import Client
from starlette.testclient import TestClient

from app.advisor.providers.base import LLMError
from app.core.config import settings
from app.mcp_server import create_server
from app.mcp_server.__main__ import main
from app.mcp_server.audit import AuditRecord, MemoryAuditSink, redact_arguments
from app.mcp_server.auth import (
    InsecureBindError,
    StaticTokenVerifier,
    TokenEntry,
    check_http_bind,
    hash_token,
    is_loopback_host,
    parse_token_entries,
)
from app.mcp_server.model_policy import ModelPolicy, ModelPolicyError, load_model_policy
from app.mcp_server.rate_limit import LimitPolicy, RateLimiter
from app.mcp_server.tokens import main as tokens_main
from app.retrieval.vector_search import SearchResult
from app.schemas.document_set import DocumentSetListResponse

ROOT = Path(__file__).resolve().parents[1]
UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


class FakeSession:
    closed = False

    def get(self, model, object_id):
        return None

    def close(self):
        self.closed = True


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def make_result():
    return SearchResult(
        document_id=uuid4(),
        document_title="Technology Assessment",
        chunk_id=uuid4(),
        chunk_index=0,
        content="The platform has a single engineer who owns all production deployments.",
        page_start=3,
        page_end=4,
        similarity_score=0.87,
        source_type="technology_assessment",
        classification="confidential",
    )


def build(**kwargs):
    sink = kwargs.pop("audit_sink", None) or MemoryAuditSink()
    server = create_server(FakeSession, audit_sink=sink, **kwargs)
    return server, sink


def run_client(server, scenario):
    async def _run():
        async with Client(server) as client:
            return await scenario(client)

    return asyncio.run(_run())


def call(server, tool, arguments):
    return run_client(server, lambda c: c.call_tool(tool, arguments))


# ------------------------------------------------------------------ authentication


@pytest.mark.parametrize(
    ("host", "has_tokens", "allow_insecure", "refused"),
    [
        ("127.0.0.1", False, False, False),
        ("::1", False, False, False),
        ("localhost", False, False, False),
        ("0.0.0.0", False, False, True),
        ("192.168.1.20", False, False, True),
        ("eaia.internal", False, False, True),
        ("0.0.0.0", True, False, False),
        ("0.0.0.0", False, True, False),
    ],
)
def test_http_bind_policy(host, has_tokens, allow_insecure, refused):
    if refused:
        with pytest.raises(InsecureBindError):
            check_http_bind(host, has_tokens=has_tokens, allow_insecure=allow_insecure)
    else:
        check_http_bind(host, has_tokens=has_tokens, allow_insecure=allow_insecure)


def test_insecure_override_logs_warning(caplog):
    with caplog.at_level(logging.WARNING):
        check_http_bind("0.0.0.0", has_tokens=False, allow_insecure=True)
    assert "MCP_ALLOW_INSECURE_BIND" in caplog.text


def test_loopback_detection():
    assert is_loopback_host("127.0.0.5")
    assert is_loopback_host("[::1]")
    assert not is_loopback_host("0.0.0.0")
    assert not is_loopback_host("10.0.0.1")


def test_entry_point_refuses_public_bind_without_tokens(monkeypatch, capsys):
    monkeypatch.setattr(settings, "mcp_auth_tokens", None)
    monkeypatch.setattr(settings, "mcp_allow_insecure_bind", False)
    monkeypatch.setattr(
        "app.mcp_server.__main__.create_server", lambda **kwargs: pytest.fail("server must not be created")
    )

    with pytest.raises(SystemExit) as exit_info:
        main(["--transport", "streamable-http", "--host", "0.0.0.0"])

    assert exit_info.value.code == 2
    assert "MCP_AUTH_TOKENS" in capsys.readouterr().err


def test_entry_point_enables_bearer_auth_when_tokens_configured(monkeypatch):
    created = {}

    class StubServer:
        def run(self, transport, **kwargs):
            created["run"] = (transport, kwargs)

    def fake_create_server(**kwargs):
        created.update(kwargs)
        return StubServer()

    monkeypatch.setattr(settings, "mcp_auth_tokens", f"cursor-tim:{hash_token('secret-token')}")
    monkeypatch.setattr("app.mcp_server.__main__.create_server", fake_create_server)

    main(["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "9100"])

    assert isinstance(created["token_verifier"], StaticTokenVerifier)
    assert created["public_url"] == "http://0.0.0.0:9100"
    assert created["run"] == ("streamable-http", {"host": "0.0.0.0", "port": 9100})


def test_entry_point_rejects_malformed_token_config(monkeypatch):
    monkeypatch.setattr(settings, "mcp_auth_tokens", "cursor-tim:not-a-hash")
    with pytest.raises(SystemExit):
        main(["--transport", "streamable-http"])


@pytest.mark.parametrize("raw", ["nolabel", ":" + "a" * 64, "x:" + "z" * 64, "x:abc", f"a:{'a' * 64},a:{'b' * 64}"])
def test_token_config_rejects_bad_entries(raw):
    with pytest.raises(ValueError):
        parse_token_entries(raw)


def test_token_config_parses_entries():
    digest = hash_token("t")
    assert parse_token_entries(f" a:{digest} , b:{digest.upper()} ") == [
        TokenEntry("a", digest),
        TokenEntry("b", digest),
    ]
    assert parse_token_entries("") == []


def test_static_token_verifier():
    verifier = StaticTokenVerifier([TokenEntry("cursor-tim", hash_token("right"))])

    good = asyncio.run(verifier.verify_token("right"))
    bad = asyncio.run(verifier.verify_token("wrong"))

    assert good is not None and good.client_id == "cursor-tim"
    assert good.token == "redacted"
    assert bad is None


def test_token_generator_prints_matching_hash(capsys):
    tokens_main(["cursor-tim"])
    out = capsys.readouterr().out
    token = re.search(r"shown once\): (\S+)", out).group(1)
    assert f"cursor-tim:{hash_token(token)}" in out


def _http_app(sink):
    server = create_server(
        FakeSession,
        transport="http",
        audit_sink=sink,
        token_verifier=StaticTokenVerifier([TokenEntry("cursor-tim", hash_token("right"))]),
        public_url="http://testserver",
    )
    return server.streamable_http_app(json_response=True, host="0.0.0.0")


INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}},
}
HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


@pytest.mark.parametrize("auth", [None, "Bearer wrong", "Basic right"])
def test_http_rejects_missing_or_wrong_token(auth):
    headers = dict(HEADERS)
    if auth:
        headers["Authorization"] = auth
    with TestClient(_http_app(MemoryAuditSink())) as client:
        response = client.post("/mcp", json=INIT, headers=headers)
    assert response.status_code == 401


def test_http_accepts_valid_token_and_audits_client_label(monkeypatch):
    monkeypatch.setattr(
        "app.services.document_sets.list_document_sets", lambda db: DocumentSetListResponse(document_sets=[])
    )
    sink = MemoryAuditSink()
    headers = {**HEADERS, "Authorization": "Bearer right"}
    with TestClient(_http_app(sink)) as client:
        init = client.post("/mcp", json=INIT, headers=headers)
        assert init.status_code == 200
        session_headers = {**headers}
        if "mcp-session-id" in init.headers:
            session_headers["mcp-session-id"] = init.headers["mcp-session-id"]
        protocol = init.json()["result"]["protocolVersion"]
        session_headers["mcp-protocol-version"] = protocol
        client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=session_headers)
        result = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "list_investigations", "arguments": {}}},
            headers=session_headers,
        )

    assert result.status_code == 200
    assert result.json()["result"]["isError"] is False
    assert [(r.name, r.client_id, r.transport) for r in sink.records] == [("list_investigations", "cursor-tim", "http")]


# ----------------------------------------------------------------- model allowlist


def test_disallowed_model_is_rejected_before_any_provider_call(monkeypatch):
    def must_not_run(*args, **kwargs):
        pytest.fail("provider or retrieval must not be called")

    monkeypatch.setattr("app.advisor.service.search_similar_chunks", must_not_run)
    monkeypatch.setattr("app.advisor.service.get_llm_provider", must_not_run)
    server, sink = build()

    result = call(server, "ask_advisor", {"question": "Key risks?", "llm_provider": "openai", "llm_model": "not-allowed"})

    assert result.is_error is True
    assert "Model not allowed for this provider." in result.content[0].text
    assert sink.records[-1].outcome == "denied"
    assert (sink.records[-1].provider, sink.records[-1].model) == ("openai", "not-allowed")


def test_disallowed_provider_is_rejected():
    server, _ = build(model_policy=ModelPolicy(allowed={"mock": frozenset({"mock"})}))
    result = call(server, "board_brief", {"document_set_id": str(uuid4()), "llm_provider": "openai"})
    assert result.is_error is True
    assert "Model not allowed" in result.content[0].text


def test_allowed_default_model_runs(monkeypatch):
    monkeypatch.setattr("app.advisor.service.search_similar_chunks", lambda **kwargs: [make_result()])
    server, sink = build()

    result = call(server, "ask_advisor", {"question": "What key-person risk exists?", "llm_provider": "mock"})

    assert result.is_error is False
    assert (sink.records[-1].provider, sink.records[-1].model, sink.records[-1].outcome) == ("mock", "mock", "ok")


def test_model_policy_file(tmp_path):
    path = tmp_path / "models.yaml"
    path.write_text("providers:\n  openai:\n    allowed_models: [gpt-4o-mini, gpt-4o]\nroutes: {}\n")

    policy = load_model_policy(settings, path)

    assert policy.is_allowed("openai", "gpt-4o")
    assert not policy.is_allowed("openai", "o1")
    assert not policy.is_allowed("anthropic", None)


def test_model_policy_defaults_to_environment_models(tmp_path):
    policy = load_model_policy(settings, tmp_path / "missing.yaml")
    assert policy.source == "environment"
    assert policy.is_allowed("openai", settings.openai_chat_model)
    assert not policy.is_allowed("openai", "gpt-4o-unlisted")


@pytest.mark.parametrize(
    "content",
    ["providers: [", "providers:\n  openai:\n    allowed_models: []\n", "providers:\n  acme:\n    allowed_models: [x]\n"],
)
def test_model_policy_rejects_invalid_files(tmp_path, content):
    path = tmp_path / "models.yaml"
    path.write_text(content)
    with pytest.raises(ModelPolicyError):
        load_model_policy(settings, path)


def test_example_policy_file_is_valid():
    policy = load_model_policy(settings, ROOT / "config" / "models.example.yaml")
    assert policy.is_allowed("mock", "mock")


# -------------------------------------------------------------------- error handling

# Built at runtime so the repository secret scan does not flag the fixture.
FAKE_KEY = "sk-" + "proj-" + "A" * 24
LEAKY = f"upstream said: invalid key {FAKE_KEY} at postgresql://eaia:hunter2@db.internal:5432/eaia"


@pytest.mark.parametrize("exc", [LLMError(LEAKY), RuntimeError(LEAKY), ValueError(LEAKY), KeyError(LEAKY)])
def test_internal_errors_do_not_reach_client(monkeypatch, caplog, exc):
    def boom(**kwargs):
        raise exc

    monkeypatch.setattr("app.executive.service.generate_board_brief", boom)
    server, sink = build()

    with caplog.at_level(logging.ERROR, logger="eaia.mcp"):
        result = call(server, "board_brief", {"document_set_id": str(uuid4()), "llm_provider": "mock"})

    text = result.content[0].text
    assert result.is_error is True
    assert "sk-proj" not in text and "hunter2" not in text and "db.internal" not in text
    reference = UUID_PATTERN.search(text).group(0)
    assert reference == str(sink.records[-1].correlation_id)
    assert reference in caplog.text
    assert sink.records[-1].error_class == type(exc).__name__


def test_domain_not_found_message_is_kept(monkeypatch):
    from app.diligence.service import DiligenceDocumentSetNotFoundError

    def missing(**kwargs):
        raise DiligenceDocumentSetNotFoundError("Document set not found.")

    monkeypatch.setattr("app.executive.service.generate_board_brief", missing)
    server, sink = build()

    result = call(server, "board_brief", {"document_set_id": str(uuid4())})

    assert result.content[0].text.endswith("Document set not found.")
    assert "Reference" not in result.content[0].text
    assert sink.records[-1].outcome == "error"


SAFE_MESSAGE_CLASSES = {
    "AdvisorDocumentNotFoundError",
    "AdvisorValidationError",
    "DiligenceDocumentNotFoundError",
    "DiligenceDocumentSetNotFoundError",
    "DiligenceValidationError",
    "CRADocumentSetNotFoundError",
    "CRAValidationError",
    "AIKnowledgeGovernanceDocumentSetNotFoundError",
    "AIKnowledgeGovernanceValidationError",
}


def test_pass_through_errors_are_raised_with_string_literals_only():
    """The MCP server returns these messages verbatim, so they must never be built from runtime data."""
    offenders = []
    for path in (ROOT / "app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                func = node.exc.func
                name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
                if name in SAFE_MESSAGE_CLASSES:
                    args = node.exc.args
                    if len(args) != 1 or not isinstance(args[0], ast.Constant) or not isinstance(args[0].value, str):
                        offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert offenders == []


# ------------------------------------------------------------------------ coupling


def test_mcp_server_does_not_import_api_routes():
    offenders = []
    for path in (ROOT / "app" / "mcp_server").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules = []
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            elif isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            offenders.extend(f"{path.name}: {m}" for m in modules if m.startswith("app.api"))
    assert offenders == []


# ---------------------------------------------------------------------- rate limits


def test_rate_limiter_bucket_refills():
    clock = FakeClock()
    limiter = RateLimiter({"llm": LimitPolicy(per_minute=10)}, clock=clock)

    assert all(limiter.check("a", "llm").allowed for _ in range(10))
    denied = limiter.check("a", "llm")
    assert not denied.allowed and denied.retry_after_seconds == 6
    assert limiter.check("b", "llm").allowed  # other clients are independent

    clock.now = 6.0
    assert limiter.check("a", "llm").allowed
    assert not limiter.check("a", "llm").allowed


def test_rate_limiter_daily_cap():
    clock = FakeClock()
    limiter = RateLimiter({"llm": LimitPolicy(per_minute=100, per_day=3)}, clock=clock)

    for _ in range(3):
        assert limiter.check("a", "llm").allowed
        clock.now += 60
    denied = limiter.check("a", "llm")
    assert not denied.allowed and denied.retry_after_seconds == 86_400 - 180

    clock.now = 86_400
    assert limiter.check("a", "llm").allowed


def test_server_rate_limits_paid_tools_only(monkeypatch):
    monkeypatch.setattr("app.advisor.service.search_similar_chunks", lambda **kwargs: [make_result()])
    monkeypatch.setattr("app.retrieval.vector_search.search_similar_chunks", lambda **kwargs: [make_result()])
    clock = FakeClock()
    limiter = RateLimiter({"read": LimitPolicy(per_minute=60), "llm": LimitPolicy(per_minute=10, per_day=200)}, clock=clock)
    server, sink = build(rate_limiter=limiter)

    async def scenario(client):
        llm = [await client.call_tool("ask_advisor", {"question": "Key risks?", "llm_provider": "mock"}) for _ in range(11)]
        read = [await client.call_tool("search_evidence", {"query": "risk"}) for _ in range(5)]
        return llm, read

    llm, read = run_client(server, scenario)

    assert [r.is_error for r in llm] == [False] * 10 + [True]
    assert "Rate limit exceeded. Retry after 6 seconds." in llm[-1].content[0].text
    assert not any(r.is_error for r in read)
    assert [r.outcome for r in sink.records].count("rate_limited") == 1


# ---------------------------------------------------------------------------- audit


def test_every_call_is_audited_once(monkeypatch):
    monkeypatch.setattr("app.retrieval.vector_search.search_similar_chunks", lambda **kwargs: [make_result()])
    server, sink = build()
    set_id = uuid4()

    async def scenario(client):
        await client.call_tool("search_evidence", {"query": "who deploys?", "document_set_id": str(set_id)})
        await client.call_tool("ask_advisor", {"question": "x" * 10, "llm_provider": "openai", "llm_model": "nope"})
        await client.get_prompt("board_meeting_prep", {"document_set_id": "abc"})
        try:
            await client.read_resource(f"eaia://investigations/{uuid4()}")
        except BaseException:  # noqa: BLE001 - the error path is what is being audited
            pass

    run_client(server, scenario)

    assert [(r.kind, r.name, r.outcome) for r in sink.records] == [
        ("tool", "search_evidence", "ok"),
        ("tool", "ask_advisor", "denied"),
        ("prompt", "board_meeting_prep", "ok"),
        ("resource", "eaia://investigations/{document_set_id}", "error"),
    ]
    first = sink.records[0]
    assert first.document_set_id == set_id
    assert first.client_id.startswith("stdio:")
    assert first.arguments["query"]["length"] == len("who deploys?")
    assert "who deploys?" not in json.dumps(first.arguments, default=str)
    assert all(r.duration_ms >= 0 for r in sink.records)


def test_audit_can_store_text_when_configured():
    redacted = redact_arguments({"question": "secret plan", "top_k": 5, "llm_model": None}, store_text=True)
    assert redacted == {"question": "secret plan", "top_k": 5}


def test_audit_failure_does_not_change_tool_result(monkeypatch, caplog):
    class BrokenSink:
        def write(self, record: AuditRecord) -> None:
            raise RuntimeError("database down")

    monkeypatch.setattr(
        "app.services.document_sets.list_document_sets", lambda db: DocumentSetListResponse(document_sets=[])
    )
    server, _ = build(audit_sink=BrokenSink())

    with caplog.at_level(logging.ERROR, logger="eaia.mcp.audit"):
        result = call(server, "list_investigations", {})

    assert result.is_error is False
    assert "Audit write failed" in caplog.text
