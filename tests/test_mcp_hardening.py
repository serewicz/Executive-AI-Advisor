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
from app.mcp_server.audit import (
    AuditHashKeyError,
    AuditRecord,
    FallbackAuditFile,
    MemoryAuditSink,
    hash_text,
    redact_arguments,
    resolve_hash_key,
)
from app.mcp_server.auth import (
    InsecureBindError,
    StaticTokenVerifier,
    TokenEntry,
    check_http_bind,
    hash_token,
    is_loopback_host,
    parse_token_entries,
)
from app.mcp_server.model_policy import ModelPolicy, ModelPolicyError, env_default_gaps, load_model_policy
from app.mcp_server.model_policy import main as model_policy_main
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
    monkeypatch.setattr(settings, "mcp_audit_hash_key", "k" * 32)

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
    assert policy.as_of == "2026-10-25"
    assert policy.is_allowed("local", "llama3.2:3b")
    assert not policy.is_allowed("openai", "gpt-6-astra")  # commented out on purpose


def test_model_entries_with_notes(tmp_path):
    path = tmp_path / "models.yaml"
    path.write_text(
        "as_of: '2026-10-25'\nproviders:\n  openai:\n    models:\n"
        "      - id: gpt-6-luna\n        notes: cheap\n      - id: gpt-6.1-sol\n"
    )
    policy = load_model_policy(settings, path)
    assert policy.is_allowed("openai", "gpt-6.1-sol")
    assert not policy.is_allowed("openai", "gpt-6-astra")


@pytest.mark.parametrize(
    "content",
    [
        "providers:\n  openai:\n    models: []\n",
        "providers:\n  openai:\n    models:\n      - id: x\n        price: 1\n",
        "providers:\n  local:\n    base_url: http://10.0.0.5:8000/v1\n    models:\n      - id: x\n",
    ],
)
def test_model_entries_reject_bad_input(tmp_path, content):
    path = tmp_path / "models.yaml"
    path.write_text(content)
    with pytest.raises(ModelPolicyError):
        load_model_policy(settings, path)


def test_local_provider_is_routed_and_allowlisted(monkeypatch):
    from app.advisor.providers.factory import get_llm_provider
    from app.advisor.providers.local_provider import LocalChatProvider

    get_llm_provider.cache_clear()
    provider = get_llm_provider("local")
    assert isinstance(provider, LocalChatProvider)
    client = provider._client(None)
    assert str(client.base_url).rstrip("/") == settings.local_llm_base_url.rstrip("/")
    get_llm_provider.cache_clear()


def test_policy_check_command(tmp_path, capsys):
    path = tmp_path / "models.yaml"
    path.write_text("providers:\n  openai:\n    models:\n      - id: some-other-model\n")
    assert model_policy_main([str(path)]) == 0
    out = capsys.readouterr().out
    assert "OK:" in out and "WARNING: openai: default model" in out
    path.write_text("providers:\n  acme:\n    models:\n      - id: x\n")
    assert model_policy_main([str(path)]) == 1
    assert model_policy_main([str(tmp_path / "missing.yaml")]) == 1


def test_env_default_gaps_empty_when_defaults_listed():
    assert env_default_gaps(load_model_policy(settings, ROOT / "missing.yaml"), settings) == []


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
        await client.get_prompt("board_meeting_prep", {"document_set_id": str(uuid4())})
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


class BrokenSink:
    def __init__(self) -> None:
        self.attempts = 0

    def write(self, record: AuditRecord) -> None:
        self.attempts += 1
        raise RuntimeError("database down at postgresql://eaia:hunter2@db.internal:5432/eaia")


def empty_sets(monkeypatch):
    monkeypatch.setattr(
        "app.services.document_sets.list_document_sets", lambda db: DocumentSetListResponse(document_sets=[])
    )


def fallback_lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_audit_failure_blocks_the_result(monkeypatch, tmp_path, caplog):
    empty_sets(monkeypatch)
    fallback = FallbackAuditFile(tmp_path / "fallback.jsonl")
    server, _ = build(audit_sink=BrokenSink(), fallback_audit=fallback)

    with caplog.at_level(logging.ERROR, logger="eaia.mcp.audit"):
        result = call(server, "list_investigations", {})

    text = result.content[0].text
    assert result.is_error is True
    assert "blocked because it could not be written to the audit log" in text
    assert "accept_unaudited=true" in text
    assert UUID_PATTERN.search(text)
    assert "hunter2" not in text and "database down" not in text
    assert "Audit write failed" in caplog.text
    lines = fallback_lines(fallback.path)
    assert [line["event"] for line in lines] == ["audit_refused"]
    assert lines[0]["correlation_id"] in text
    assert lines[0]["audit_db_error_class"] == "RuntimeError"


def test_override_returns_answer_marked_unaudited(monkeypatch, tmp_path):
    empty_sets(monkeypatch)
    sink = BrokenSink()
    fallback = FallbackAuditFile(tmp_path / "fallback.jsonl")
    server, _ = build(audit_sink=sink, fallback_audit=fallback)

    async def scenario(client):
        first = await client.call_tool("list_investigations", {})
        second = await client.call_tool("list_investigations", {"accept_unaudited": True})
        return first, second

    first, second = run_client(server, scenario)

    assert first.is_error is True
    assert second.is_error is False
    assert sink.attempts == 2  # the override call tried the audit table again
    assert second.content[0].text.startswith("UNAUDITED:")
    assert second.structured_content == {"document_sets": []}
    assert second.meta["eaia/audit"]["audited"] is False
    events = fallback_lines(fallback.path)
    assert [e["event"] for e in events] == ["audit_refused", "unaudited_override"]
    assert events[1]["correlation_id"] == second.meta["eaia/audit"]["reference"]
    assert "accept_unaudited" not in events[1]["arguments"]


def test_override_is_audited_normally_when_the_database_is_back(monkeypatch, tmp_path):
    empty_sets(monkeypatch)
    fallback = FallbackAuditFile(tmp_path / "fallback.jsonl")
    server, sink = build(fallback_audit=fallback)

    result = call(server, "list_investigations", {"accept_unaudited": True})

    assert result.is_error is False
    assert result.meta is None or "eaia/audit" not in result.meta
    assert sink.records[-1].outcome == "ok"
    assert sink.records[-1].detail == "accept_unaudited requested"
    assert fallback_lines(fallback.path) == []


def test_override_disabled_is_a_hard_failure(monkeypatch, tmp_path):
    empty_sets(monkeypatch)
    fallback = FallbackAuditFile(tmp_path / "fallback.jsonl")
    config = settings.model_copy(update={"mcp_audit_allow_unaudited_override": False})
    server, _ = build(audit_sink=BrokenSink(), fallback_audit=fallback, config=config)

    async def scenario(client):
        return (
            await client.call_tool("list_investigations", {}),
            await client.call_tool("list_investigations", {"accept_unaudited": True}),
        )

    first, second = run_client(server, scenario)

    assert first.is_error and second.is_error
    assert "Overrides are disabled" in first.content[0].text
    assert "accept_unaudited=true" not in first.content[0].text
    assert [e["event"] for e in fallback_lines(fallback.path)] == ["audit_refused", "audit_refused"]


def test_override_without_a_durable_fallback_is_refused(monkeypatch, tmp_path):
    empty_sets(monkeypatch)
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("")
    fallback = FallbackAuditFile(blocker / "fallback.jsonl")  # parent is a file, so append fails
    server, _ = build(audit_sink=BrokenSink(), fallback_audit=fallback)

    result = call(server, "list_investigations", {"accept_unaudited": True})

    assert result.is_error is True
    assert "fallback audit file are both unavailable" in result.content[0].text


def test_override_on_a_failing_call_returns_the_error_marked_unaudited(tmp_path):
    fallback = FallbackAuditFile(tmp_path / "fallback.jsonl")
    server, _ = build(audit_sink=BrokenSink(), fallback_audit=fallback)

    arguments = {"question": "Key risks?", "llm_provider": "openai", "llm_model": "nope", "accept_unaudited": True}
    result = call(server, "ask_advisor", arguments)

    assert result.is_error is True
    assert "Model not allowed" in result.content[0].text
    assert "UNAUDITED" in result.content[0].text
    assert fallback_lines(fallback.path)[0]["outcome"] == "denied"


def test_resources_and_prompts_have_no_override(monkeypatch, tmp_path):
    empty_sets(monkeypatch)
    fallback = FallbackAuditFile(tmp_path / "fallback.jsonl")
    server, _ = build(audit_sink=BrokenSink(), fallback_audit=fallback)

    async def scenario(client):
        prompt_error = resource_error = None
        try:
            await client.get_prompt("board_meeting_prep", {"document_set_id": str(uuid4())})
        except BaseException as exc:  # noqa: BLE001
            prompt_error = str(exc)
        try:
            await client.read_resource("eaia://investigations")
        except BaseException as exc:  # noqa: BLE001
            resource_error = str(exc)
        return prompt_error, resource_error

    prompt_error, resource_error = run_client(server, scenario)

    assert prompt_error is not None  # the SDK reports prompt failures as a generic error
    assert "could not be written to the audit log" in resource_error
    assert "A resource cannot be overridden" in resource_error
    assert "accept_unaudited=true" not in resource_error
    assert [e["event"] for e in fallback_lines(fallback.path)] == ["audit_refused", "audit_refused"]


def _tool_names() -> list[str]:
    server, _ = build()
    return sorted(tool.name for tool in run_client(server, lambda c: c.list_tools()).tools)


ALL_TOOLS = _tool_names()


def test_tool_inventory_matches_the_docs():
    # README, ADR 0001, and the runbooks state this count. Update them together.
    assert len(ALL_TOOLS) == 12, ALL_TOOLS


def _minimal_arguments(schema: dict) -> dict:
    values = {"document_set_id": str(uuid4()), "query": "who deploys?", "question": "Key risks?"}
    return {name: values[name] for name in schema.get("required", [])}


@pytest.mark.parametrize("tool_name", ALL_TOOLS)
def test_override_reaches_the_guard_on_every_tool(tool_name, monkeypatch, tmp_path):
    """Each tool must pass accept_unaudited through to CallGuard (review finding on PR #26)."""
    empty_sets(monkeypatch)
    sink = BrokenSink()
    fallback = FallbackAuditFile(tmp_path / "fallback.jsonl")
    server, _ = build(audit_sink=sink, fallback_audit=fallback)
    tools = {t.name: t for t in run_client(server, lambda c: c.list_tools()).tools}
    schema = tools[tool_name].input_schema
    assert schema["properties"]["accept_unaudited"]["default"] is False
    arguments = _minimal_arguments(schema)

    async def scenario(client):
        return (
            await client.call_tool(tool_name, arguments),
            await client.call_tool(tool_name, {**arguments, "accept_unaudited": True}),
        )

    refused, overridden = run_client(server, scenario)

    assert "could not be written to the audit log" in refused.content[0].text
    # The override may succeed or carry the tool's own error, but it must not be refused again.
    assert "could not be written to the audit log" not in overridden.content[0].text
    assert "UNAUDITED" in overridden.content[0].text
    assert [e["event"] for e in fallback_lines(fallback.path)] == ["audit_refused", "unaudited_override"]
    assert sink.attempts == 2


def test_fallback_file_appends_and_never_truncates(tmp_path):
    fallback = FallbackAuditFile(tmp_path / "audit" / "fallback.jsonl")
    record = AuditRecord(correlation_id=uuid4(), client_id="c", transport="stdio", kind="tool", name="t")
    fallback.append("audit_refused", record, "OperationalError")
    fallback.append("unaudited_override", record, None)
    lines = fallback_lines(fallback.path)
    assert [line["event"] for line in lines] == ["audit_refused", "unaudited_override"]
    assert oct(fallback.path.stat().st_mode & 0o777) == "0o600"


@pytest.mark.parametrize("target", ["resource", "board_meeting_prep", "diligence_review"])
def test_malformed_investigation_id_is_a_validation_error_not_an_audit_outage(target, tmp_path, caplog):
    fallback = FallbackAuditFile(tmp_path / "fallback.jsonl")
    server, sink = build(fallback_audit=fallback)

    async def scenario(client):
        try:
            if target == "resource":
                await client.read_resource("eaia://investigations/not-a-uuid")
            else:
                await client.get_prompt(target, {"document_set_id": "not-a-uuid"})
        except BaseException as exc:  # noqa: BLE001
            return str(exc)
        return None

    with caplog.at_level(logging.ERROR, logger="eaia.mcp.audit"):
        error = run_client(server, scenario)

    assert error is not None
    if target == "resource":
        assert "Invalid investigation id." in error
    assert "audit log" not in error
    record = sink.records[-1]
    assert (record.outcome, record.error_class, record.document_set_id) == ("error", "InvalidInput", None)
    assert record.arguments["document_set_id"] == "not-a-uuid"
    assert "Audit write failed" not in caplog.text
    assert fallback_lines(fallback.path) == []


# ------------------------------------------------------------------ free-text hashing

KEY = "k" * 32


def test_free_text_is_hmac_not_plain_sha256():
    import hashlib

    redacted = redact_arguments({"question": "Is the Acme deal at risk?"}, store_text=False, hash_key=KEY.encode())
    digest = redacted["question"]["hmac_sha256"]
    assert "sha256" not in redacted["question"]
    assert digest != hashlib.sha256(b"Is the Acme deal at risk?").hexdigest()
    assert digest == hash_text("Is the Acme deal at risk?", KEY.encode())
    other = redact_arguments({"question": "Is the Acme deal at risk?"}, store_text=False, hash_key=b"x" * 32)
    assert other["question"]["hmac_sha256"] != digest


def test_hash_key_rules(caplog):
    assert resolve_hash_key(KEY, required=True) == KEY.encode()
    with pytest.raises(AuditHashKeyError, match="at least 32"):
        resolve_hash_key("short", required=False)
    with pytest.raises(AuditHashKeyError, match="required"):
        resolve_hash_key(None, required=True)
    with caplog.at_level(logging.WARNING):
        first = resolve_hash_key(None, required=False)
    assert len(first) == 32 and first != resolve_hash_key(None, required=False)
    assert "MCP_AUDIT_HASH_KEY is not set" in caplog.text
    with pytest.raises(AuditHashKeyError):
        redact_arguments({"question": "q"}, store_text=False, hash_key=None)


def test_server_uses_the_configured_hash_key(monkeypatch):
    monkeypatch.setattr("app.retrieval.vector_search.search_similar_chunks", lambda **kwargs: [make_result()])
    config = settings.model_copy(update={"mcp_audit_hash_key": KEY})
    server, sink = build(config=config)

    call(server, "search_evidence", {"query": "who deploys?"})

    assert sink.records[-1].arguments["query"]["hmac_sha256"] == hash_text("who deploys?", KEY.encode())


def test_public_http_bind_requires_hash_key(monkeypatch, capsys):
    monkeypatch.setattr(settings, "mcp_auth_tokens", "cursor:" + "a" * 64)
    monkeypatch.setattr(settings, "mcp_audit_hash_key", None)
    monkeypatch.setattr(
        "app.mcp_server.__main__.create_server", lambda **kwargs: pytest.fail("server must not be created")
    )

    with pytest.raises(SystemExit) as exit_info:
        main(["--transport", "streamable-http", "--host", "0.0.0.0"])

    assert exit_info.value.code == 2
    assert "MCP_AUDIT_HASH_KEY is required" in capsys.readouterr().err


def test_loopback_http_without_hash_key_starts(monkeypatch):
    monkeypatch.setattr(settings, "mcp_auth_tokens", None)
    monkeypatch.setattr(settings, "mcp_audit_hash_key", None)
    created = {}

    class Stub:
        def run(self, *args, **kwargs):
            created["ran"] = True

    monkeypatch.setattr("app.mcp_server.__main__.create_server", lambda **kwargs: created.update(kwargs) or Stub())

    main(["--transport", "streamable-http", "--host", "127.0.0.1"])

    assert created["ran"] and len(created["audit_hash_key"]) == 32


# ------------------------------------------------------------------ audit circuit breaker


class FlakySink(MemoryAuditSink):
    """Fails while ``down`` is true."""

    def __init__(self) -> None:
        super().__init__()
        self.down = True
        self.attempts = 0

    def write(self, record: AuditRecord) -> None:
        self.attempts += 1
        if self.down:
            raise RuntimeError("database down")
        super().write(record)


def breaker_server(monkeypatch, tmp_path, **config_updates):
    empty_sets(monkeypatch)
    provider_calls = []

    def spy(**kwargs):
        provider_calls.append(kwargs)
        return [make_result()]

    monkeypatch.setattr("app.advisor.service.search_similar_chunks", spy)
    monkeypatch.setattr("app.retrieval.vector_search.search_similar_chunks", spy)
    sink = FlakySink()
    fallback = FallbackAuditFile(tmp_path / "fallback.jsonl")
    config = settings.model_copy(update=config_updates) if config_updates else None
    server, _ = build(audit_sink=sink, fallback_audit=fallback, **({"config": config} if config else {}))
    clock = FakeClock()
    server.call_guard._clock = clock
    return server, sink, fallback, clock, provider_calls


ASK = {"question": "Key risks?", "llm_provider": "mock"}


def test_breaker_refuses_model_tools_before_the_provider(monkeypatch, tmp_path):
    server, sink, fallback, clock, provider_calls = breaker_server(monkeypatch, tmp_path)

    async def scenario(client):
        await client.call_tool("list_investigations", {})  # audit fails, breaker opens
        clock.now = 10
        return await client.call_tool("ask_advisor", ASK)

    result = run_client(server, scenario)

    assert provider_calls == []
    text = result.content[0].text
    assert result.is_error and "The model was not called." in text and "accept_unaudited=true" in text
    assert [e["event"] for e in fallback_lines(fallback.path)] == ["audit_refused", "audit_refused"]
    assert fallback_lines(fallback.path)[1]["outcome"] == "denied"


def test_breaker_refusal_closes_the_breaker_when_the_audit_log_is_back(monkeypatch, tmp_path):
    server, sink, fallback, clock, provider_calls = breaker_server(monkeypatch, tmp_path)

    async def scenario(client):
        await client.call_tool("list_investigations", {})
        sink.down = False
        clock.now = 5
        first = await client.call_tool("ask_advisor", ASK)
        second = await client.call_tool("ask_advisor", ASK)
        return first, second

    first, second = run_client(server, scenario)

    assert first.is_error and "audit log is working again" in first.content[0].text
    assert sink.records[0].outcome == "denied"
    assert sink.records[0].detail.startswith("audit circuit breaker open")
    assert second.is_error is False
    assert len(provider_calls) == 1


def test_override_passes_the_breaker_and_still_retries_the_audit(monkeypatch, tmp_path):
    server, sink, fallback, clock, provider_calls = breaker_server(monkeypatch, tmp_path)

    async def scenario(client):
        await client.call_tool("list_investigations", {})
        clock.now = 5
        return await client.call_tool("ask_advisor", {**ASK, "accept_unaudited": True})

    result = run_client(server, scenario)

    assert len(provider_calls) == 1
    assert sink.attempts == 2  # the override tried the audit table before using the fallback file
    assert result.content[0].text.startswith("UNAUDITED:")
    assert [e["event"] for e in fallback_lines(fallback.path)] == ["audit_refused", "unaudited_override"]


def test_breaker_expires_and_does_not_affect_read_tools(monkeypatch, tmp_path):
    server, sink, fallback, clock, provider_calls = breaker_server(monkeypatch, tmp_path)

    async def scenario(client):
        await client.call_tool("list_investigations", {})
        clock.now = 1
        await client.call_tool("search_evidence", {"query": "risk"})  # read tool: runs, audit attempted
        sink.down = False
        clock.now = 31  # 30 seconds after the last failure at t=1
        return await client.call_tool("ask_advisor", ASK)

    result = run_client(server, scenario)

    assert sink.attempts == 3
    assert len(provider_calls) == 2  # search_evidence and ask_advisor both ran
    assert result.is_error is False


def test_breaker_can_be_turned_off(monkeypatch, tmp_path):
    server, sink, fallback, clock, provider_calls = breaker_server(
        monkeypatch, tmp_path, mcp_audit_breaker_seconds=0
    )

    async def scenario(client):
        await client.call_tool("list_investigations", {})
        sink.down = False
        return await client.call_tool("ask_advisor", ASK)

    result = run_client(server, scenario)

    assert result.is_error is False
    assert len(provider_calls) == 1


# ------------------------------------------------------------------ mock provider


def test_mock_output_is_labeled(monkeypatch):
    monkeypatch.setattr("app.advisor.service.search_similar_chunks", lambda **kwargs: [make_result()])
    monkeypatch.setattr("app.retrieval.vector_search.search_similar_chunks", lambda **kwargs: [make_result()])
    server, sink = build(config=settings.model_copy(update={"llm_provider": "mock"}))

    result = call(server, "ask_advisor", {"question": "Key risks?"})

    assert result.is_error is False
    assert result.content[0].text.startswith("MOCK OUTPUT:")
    assert result.meta["eaia/mock"] is True
    assert result.structured_content["answer"]
    assert sink.records[-1].provider == "mock"


@pytest.mark.parametrize("arguments", [{"question": "Key risks?", "llm_provider": "mock"}, {"question": "Key risks?"}])
def test_mock_is_denied_unless_the_server_runs_in_mock_mode(arguments, monkeypatch):
    calls = []
    monkeypatch.setattr("app.advisor.service.search_similar_chunks", lambda **kwargs: calls.append(1) or [])
    config = settings.model_copy(update={"llm_provider": "openai"})
    policy = ModelPolicy({"mock": frozenset({"mock"}), "openai": frozenset({"gpt-x"})})
    server, sink = build(config=config, model_policy=policy)

    result = call(server, "ask_advisor", {**arguments, "llm_provider": "mock"})

    assert result.is_error is True
    assert "LLM_PROVIDER=mock" in result.content[0].text
    assert sink.records[-1].outcome == "denied"
    assert calls == []


def test_unaudited_mock_output_carries_both_labels(monkeypatch, tmp_path):
    monkeypatch.setattr("app.advisor.service.search_similar_chunks", lambda **kwargs: [make_result()])
    server, _ = build(audit_sink=BrokenSink(), fallback_audit=FallbackAuditFile(tmp_path / "f.jsonl"))

    result = call(server, "ask_advisor", {"question": "Key risks?", "llm_provider": "mock", "accept_unaudited": True})

    texts = [block.text for block in result.content]
    assert texts[0].startswith("UNAUDITED:") and texts[1].startswith("MOCK OUTPUT:")
    assert result.meta["eaia/audit"]["audited"] is False and result.meta["eaia/mock"] is True


# ------------------------------------------------------------------ local provider pin and defaults


def _settings_with_local_url(url: str):
    from app.core.config import Settings

    return Settings(_env_file=None, LOCAL_LLM_BASE_URL=url)


def test_local_base_url_without_a_policy_file_refuses_to_start(tmp_path):
    with pytest.raises(ModelPolicyError, match="LOCAL_LLM_BASE_URL is set"):
        load_model_policy(_settings_with_local_url("http://10.0.0.5:8000/v1"), tmp_path / "missing.yaml")


def test_local_base_url_without_a_pin_refuses_to_start(tmp_path):
    path = tmp_path / "models.yaml"
    path.write_text("providers:\n  local:\n    models:\n      - id: x\n")
    with pytest.raises(ModelPolicyError, match="no providers.local.base_url"):
        load_model_policy(_settings_with_local_url("http://10.0.0.5:8000/v1"), path)


def test_local_base_url_with_a_matching_pin_starts(tmp_path):
    path = tmp_path / "models.yaml"
    path.write_text("providers:\n  local:\n    base_url: http://10.0.0.5:8000/v1/\n    models:\n      - id: x\n")
    policy = load_model_policy(_settings_with_local_url("http://10.0.0.5:8000/v1"), path)
    assert policy.is_allowed("local", "x")


def test_unset_local_base_url_needs_no_pin(tmp_path):
    from app.core.config import Settings

    config = Settings(_env_file=None)
    assert "local_llm_base_url" not in config.model_fields_set
    assert load_model_policy(config, tmp_path / "missing.yaml").source == "environment"


def test_default_models_are_in_the_example_list():
    from app.core.config import Settings
    from app.mcp_server.model_policy import env_default_gaps

    config = Settings(_env_file=None)
    assert config.openai_chat_model == "gpt-6.1-sol"
    assert config.anthropic_chat_model == "claude-sonnet-5-5"
    policy = load_model_policy(config, ROOT / "config" / "models.example.yaml")
    gaps = [gap for gap in env_default_gaps(policy, config) if not gap.startswith("grok")]
    assert gaps == []
