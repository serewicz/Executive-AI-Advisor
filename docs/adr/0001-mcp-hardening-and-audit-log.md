# ADR 0001: Harden the MCP server and add an audit log

Status: Accepted, pending review. Tracking issue: #23. Order: 1 of 3. ADR 0002 (#24) and ADR 0003 (#25) build on it.

Date: 2026-10-25

This record describes the design as built. Section "Changes from the draft" lists where the implementation differs from the version attached to #23.

## Problem and context

PR #18 added an MCP server (`app/mcp_server/`) with 12 tools. All 12 are read-only, and input validation is sound: IDs are UUIDs, `top_k` is bounded 1–50, and query length is capped. A review found five gaps that matter to enterprise and public-sector buyers, who expect read-only, auditable, least-privilege access:

1. **No authentication in HTTP mode.** `app/mcp_server/__main__.py` lines 15–27 offer `--transport streamable-http` with a configurable `--host`. The default bind is `127.0.0.1`, but `--host 0.0.0.0` exposes every tool, including the ones that call paid model APIs, to anyone on the network. There is no token check and no warning.
2. **Unrestricted model name.** `app/mcp_server/server.py` line 82 accepts any `llm_model` string up to 120 characters. A caller can select the most expensive model a configured key allows. This is a cost control gap, not only a security gap.
3. **Raw error passthrough.** `server.py` lines 92–93 add `ValueError` and `RuntimeError` to `_EXPECTED_ERRORS`, and line 138 returns `str(exc)` to the client. `LLMError` is a `RuntimeError` subclass (`app/advisor/providers/base.py` line 5), and providers embed the upstream exception text (for example `grok_provider.py` line 37). Database driver errors can include host names and connection details. These strings end up in model context and client logs.
4. **Coupling to private route helpers.** `server.py` line 34 imports `_document_set_detail` and `list_document_sets` from `app/api/routes/document_sets.py`. The MCP layer depends on a private function in the HTTP layer, so a route refactor can break MCP silently.
5. **No rate limit on paid tools.** Ten tools are annotated `READ_ONLY_LLM` (line 74) and each call can consume thousands of tokens (`llm_max_tokens` default 4000, `app/core/config.py`). Nothing limits calls per minute or per client.

There is also no record of who called which tool, when, with what arguments, or with what result. Without that, the system cannot answer the first question an auditor asks.

## Goals

- HTTP transport refuses to start on a non-loopback address without authentication configured.
- Model selection is limited to an allowlist from configuration.
- Clients receive stable, generic error messages. Detail goes to server logs with a correlation ID.
- MCP and REST call the same public service functions. No imports of underscored names across layers.
- Per-client rate limits on LLM-backed tools.
- An append-only audit record for every tool call and resource read.

## Non-goals

- OAuth 2.1 authorization server or SSO integration. Bearer tokens are enough for this phase. The design leaves room for the MCP authorization spec later.
- Multi-tenant row-level access control on investigations.
- Write tools. The server stays read-only.
- Cost accounting in dollars (ADR 0003).

## Design

### 1. Authentication for streamable-http

- New settings: `MCP_AUTH_TOKENS` (comma-separated `label:sha256hex` entries) and `MCP_ALLOW_INSECURE_BIND` (default false). `python -m app.mcp_server.tokens <label>` generates a token and prints the entry. Malformed or duplicate entries stop startup.
- Startup rule: if transport is HTTP and host is not loopback (`127.0.0.0/8`, `::1`, `localhost`) and no tokens are configured, exit with code 2 and a message naming `MCP_AUTH_TOKENS`. `MCP_ALLOW_INSECURE_BIND=true` overrides for lab use and logs a warning on every start. Loopback without tokens starts and logs a warning.
- Requests carry `Authorization: Bearer <token>`. Verification uses the MCP SDK's bearer middleware (`MCPServer(auth=..., token_verifier=...)`) with a static verifier (`app/mcp_server/auth.py`). The verifier hashes the token and compares each stored hash with `hmac.compare_digest`. Missing or wrong tokens get HTTP 401 before any tool code runs. The matched label becomes the `client_id` for rate limits and audit. The raw token is not kept on the request.
- Using the SDK middleware means the server already publishes OAuth protected-resource metadata. Moving to a real authorization server later replaces the verifier, not the transport code. `--public-url` sets the URL advertised in that metadata.
- stdio is unchanged. The OS process boundary is the trust boundary, and `client_id` is `stdio:<user>`.

Alternatives considered:
- *mTLS only*: strong, but heavy to operate for a single-team deployment. Can be layered in front with a reverse proxy; documented in the runbook.
- *Leave auth to a reverse proxy*: rejected as the only control because the default must be safe. A misconfigured proxy should not expose paid tools.
- *Full OAuth now*: rejected for scope. Revisit when a buyer needs SSO.

### 2. Model allowlist

```yaml
# config/models.yaml (shared with ADR 0002)
providers:
  openai:   { allowed_models: [gpt-4o-mini] }
  anthropic: { allowed_models: [claude-3-5-sonnet-latest] }
  grok:     { allowed_models: [grok-4.3] }
  mock:     { allowed_models: [mock] }
```

Every LLM-backed tool resolves the provider (argument or `LLM_PROVIDER`) and the model (argument or the provider's configured default), then checks the pair against the allowlist before any retrieval or provider call. Unknown pair → `Model not allowed for this provider.`, audited as `denied`. The default model must also be listed, so a config change cannot route around the list.

- File location: `MCP_MODEL_POLICY_FILE`, default `config/models.yaml`. `config/models.example.yaml` is the template. The file is validated at startup (pydantic); unknown providers, empty lists, or bad YAML stop the server. Top-level keys other than `providers` are ignored so ADR 0002 can add routing to the same file.
- No file: the allowlist is `mock: [mock]` plus each provider's configured chat model from the environment. This keeps existing setups working and still blocks arbitrary model names.
- Scope: MCP only. The REST API and Streamlit UI still accept any model name. ADR 0002 moves the check into the shared service layer.

ADR 0002 turns this file into the routing policy; this ADR adds only the allowlist.

Alternative: remove `llm_model` from MCP entirely. Rejected because model choice per task is a real need (cheap model for search summaries, stronger model for diligence); the fix is governance, not removal.

### 3. Error handling

- `app/core/errors.py` defines `PublicError` and subclasses with a safe public message: `NotFound`, `InvalidInput`, `Denied`, `RateLimited`, `ProviderUnavailable`, `Internal`.
- `CallGuard` in `server.py` maps exceptions:
  - service `*NotFoundError` → `NotFound` with the service's message;
  - service `*ValidationError` → `InvalidInput` with the service's message;
  - `LLMError`, `EmbeddingError` → `The model provider request failed. Reference: <id>`;
  - anything else, including bare `ValueError` and `RuntimeError` → `Internal error. Reference: <id>`.
- The service messages passed through are string literals. A test parses `app/` and fails if any of those exceptions is raised with a non-literal message, so a future f-string cannot leak data through this path.
- For provider and internal errors the full trace is logged on logger `eaia.mcp` with the same correlation ID, and the audit row stores the exception class name.

Alternative: regex-scrub `str(exc)`. Rejected: deny-by-default is easier to reason about than trying to find every secret pattern.

### 4. Decouple from route helpers

`app/services/document_sets.py` holds `list_document_sets`, `get_document_set`, `document_set_detail`, `documents_for_set`, and `document_summary`. The REST routes and `server.py` both import from there. A test parses every module under `app/mcp_server` and fails on any import from `app.api`.

### 5. Rate limiting

- Token bucket per `client_id` per policy (`read`, `llm`), plus a rolling 24-hour count for the daily cap. Defaults: read tools, resources, and prompts 60/min; LLM tools 10/min and 200/day. Settings: `MCP_RATE_LIMIT_READ_PER_MINUTE`, `MCP_RATE_LIMIT_LLM_PER_MINUTE`, `MCP_RATE_LIMIT_LLM_PER_DAY`.
- In-process and thread-safe (`app/mcp_server/rate_limit.py`). The limiter takes an injected clock for tests. A shared backend (Postgres or Redis) can replace it behind the same `check(client_id, policy)` call.
- The limit is checked before the allowlist and before any provider call.
- Exceeded limit → `ToolError("Rate limit exceeded. Retry after N seconds.")`, audited.

Alternative: rely on provider-side rate limits. Rejected: those protect the vendor, not the budget.

### 6. Audit log

New table `mcp_audit_events` (Alembic migration after `20260608_0007`):

| column | type | notes |
|---|---|---|
| id | uuid pk | |
| occurred_at | timestamptz | server clock, UTC |
| correlation_id | uuid | also in logs and error messages |
| client_id | text | token label or `stdio:<user>` |
| transport | text | `stdio` / `http` |
| kind | text | `tool` / `resource` / `prompt` |
| name | text | tool or resource name |
| arguments | jsonb | redacted: `query`/`question` stored as SHA-256 plus length unless `MCP_AUDIT_STORE_TEXT=true` |
| document_set_id | uuid null | |
| outcome | text | `ok` / `error` / `rate_limited` / `denied` |
| error_class | text null | |
| duration_ms | int | |
| provider, model | text null | resolved provider and model for LLM tools |
| request_id | uuid null | reserved for the ADR 0003 ledger |
| detail | text null | reserved for operator notes; not written by the server |

Append-only: the migration adds triggers that reject `UPDATE`, `DELETE`, and `TRUNCATE` on the table for every role. Grants alone were not enough, because the app role runs migrations and owns the table, and an owner can grant itself anything. A table owner can still disable the triggers. For tamper resistance against the app credentials themselves, run the MCP server with a separate role that has `INSERT, SELECT` only; the runbook has the SQL. Retention runs as the owner and disables the trigger inside one transaction.

Writes: each record is written in its own session and transaction, so a failed tool call still produces a row. Writes fail open: if the insert fails, the tool result is returned and the record is logged as JSON at ERROR on logger `eaia.mcp.audit`. Every record is also logged at INFO on the same logger, which gives a second copy for log shipping.

Resources and prompts are audited with `kind` = `resource` or `prompt`. A read-only MCP resource `eaia://audit/recent` is not added; audit data is for operators, not for the model.

Alternative: structured log lines only. Rejected as the sole store: logs rotate and are hard to query for an auditor. Structured logs are still emitted in parallel.

## Threat model

| Threat | Control |
|---|---|
| Network attacker calls tools on exposed HTTP port | Startup refusal without tokens; bearer auth |
| Token theft | Tokens stored hashed; per-client labels; revocation by removing hash; audit shows use |
| Cost abuse (expensive model, call flooding) | Model allowlist; rate limits; ADR 0003 budgets |
| Information disclosure via errors | Generic messages, correlation IDs |
| Prompt injection in documents causing tool misuse | Tools are read-only; no write or network tools; audit trail for review |
| Sensitive text in audit log | Query/question hashed by default |
| Audit tampering | Append-only triggers; optional least-privilege role |
| Audit outage hides calls | Fail-open with ERROR log containing the full record |

## Acceptance criteria

1. `python -m app.mcp_server --transport streamable-http --host 0.0.0.0` exits non-zero with no tokens configured.
2. HTTP request without or with a wrong bearer token gets 401; correct token succeeds.
3. `ask_advisor` with `llm_model="not-allowed"` returns a `ToolError` and makes no provider call.
4. A provider exception containing `sk-...` or a DB URL never appears in the client response; response contains a correlation ID that matches a server log line.
5. No module under `app/mcp_server` imports from `app.api.routes` (enforced by test).
6. The 11th LLM-tool call within a minute from one client is rejected; read-only tools are unaffected.
7. Every tool call, including failures and rejections, writes one `mcp_audit_events` row; the app DB role cannot update or delete rows.
8. Existing 184 tests pass.

All eight are covered by tests in `tests/test_mcp_hardening.py` and `tests/test_mcp_audit_postgres.py`. The Postgres tests run when `EAIA_PG_INTEGRATION_URL` is set; CI does not set it yet (see Follow-ups).

## Test plan

- Unit: auth startup rule (table of host/token combinations), token compare, allowlist, error mapping, rate limiter with injected clock.
- Integration: the official MCP client in memory; HTTP through Starlette's `TestClient` against `streamable_http_app()` with bearer headers; audit rows and trigger behavior in Postgres.
- Negative: injected secrets and database URLs in exceptions; malformed token config; invalid policy files; burst calls.
- Migration: upgrade, downgrade, upgrade against Postgres 16 with pgvector (run by hand for this change; CI runs `alembic upgrade head`).

## Documentation deliverables

- `docs/adr/0001-mcp-hardening-and-audit-log.md` (this document).
- `docs/Security.md`: MCP section with threat model table and configuration.
- README MCP section: token setup for HTTP, allowlist.
- `docs/runbooks/mcp-operations.md`: issuing and revoking tokens, reading the audit log, rate-limit tuning, putting a TLS reverse proxy in front, retention job.

## Rollout and risks

- Ship behind defaults that are safe: stdio unaffected; HTTP on loopback unaffected; HTTP on other hosts requires tokens. CHANGELOG notes the breaking change for anyone binding 0.0.0.0.
- Risk: in-process rate limiter resets on restart and is per-instance. Acceptable for current single-instance use; documented.
- Risk: audit writes add latency. Write is a single insert in its own transaction; not yet measured under load.
- Risk: fail-open audit means a database outage leaves gaps in the table. The ERROR log line holds the full record, so gaps can be rebuilt from logs.

## Changes from the draft

| Draft | Built | Reason |
|---|---|---|
| Append-only through grants | Triggers, plus optional `INSERT, SELECT` role | The app role owns the table, so grants do not bind it |
| Audit failure behavior unstated | Fail open, ERROR log with the full record | An audit outage should not take down read-only tools; the log keeps the record |
| Allowlist for the server | Allowlist for MCP only | Keeps this change inside the MCP layer; ADR 0002 moves it to the service layer |
| `provider`/`model` filled by ADR 0002 | Filled now for LLM tools | The allowlist already resolves both |
| Custom auth middleware implied | MCP SDK bearer middleware with a static verifier | Less code, standard 401 behavior, path to OAuth |

## Follow-ups

- Run `tests/test_mcp_audit_postgres.py` in CI: set `EAIA_PG_INTEGRATION_URL` and move `alembic upgrade head` before `pytest` in `ci-validate.yml`. Not done here because the change touches `.github/workflows`.
- Shared rate-limit backend before running more than one MCP instance.
- Apply the model allowlist to REST and Streamlit (ADR 0002).

## Dependencies

None. ADR 0002 uses the `config/models.yaml` file and the `provider`/`model` audit columns. ADR 0003 links ledger rows to `request_id`.
