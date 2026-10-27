# ADR 0001: Harden the MCP server and add an audit log

Status: Accepted, pending review. Tracking issue: #23. Order: 1 of 3. ADR 0002 (#24) and ADR 0003 (#25) build on it.

Date: 2026-10-25. Revised 2026-10-25: audit failure changed from fail open to fail closed with an explicit override (section 6.1); the model allowlist became a dated model list (section 2). Revised again after code review: free text is hashed with a keyed HMAC (section 6.2), malformed investigation IDs are validation errors (section 6.3), a circuit breaker stops model calls during an audit outage (section 6.4), and the mock provider runs only in mock mode (section 2).

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
# config/models.yaml (shared with ADR 0002). Abbreviated; see config/models.example.yaml.
as_of: "2026-10-25"
providers:
  openai:
    models:
      - id: gpt-6-luna
        notes: Lowest-cost current model.
```

Every LLM-backed tool resolves the provider (argument or `LLM_PROVIDER`) and the model (argument or the provider's configured default), then checks the pair against the allowlist before any retrieval or provider call. Unknown pair → `Model not allowed for this provider.`, audited as `denied`. The default model must also be listed, so a config change cannot route around the list.

- File location: `MCP_MODEL_POLICY_FILE`, default `config/models.yaml`. `config/models.example.yaml` is the template. The file is validated at startup (pydantic); unknown providers, empty lists, or bad YAML stop the server. Top-level keys other than `providers` are ignored so ADR 0002 can add routing to the same file.
- No file: the allowlist is `mock: [mock]` plus each provider's configured chat model from the environment. This keeps existing setups working and still blocks arbitrary model names.
- Scope: MCP only. The REST API and Streamlit UI still accept any model name. ADR 0002 moves the check into the shared service layer.

ADR 0002 turns this file into the routing policy; this ADR adds only the allowlist.

The file is a list of current models, not only a list of names:

- Each entry has an `id` and optional `notes` (cost tier, intended use). Unknown keys are rejected, so a typo such as `modle:` fails at startup instead of being ignored.
- `as_of` records the date someone last checked the IDs against the providers' model pages. Providers retire models on their own schedules (the previous default `claude-3-5-sonnet-latest` was retired by its provider before this revision). The date tells the next reader how stale the list may be.
- The older `allowed_models: [...]` form still loads, so existing files keep working.
- `python -m app.mcp_server.model_policy [path]` validates a file without starting the server and warns when a provider's environment default is missing from its list.
- The procedure for changing the list is in `docs/runbooks/updating-model-list.md`.

Local models and new default models were split out of this ADR's PR into a separate draft PR, so this change covers only hardening and the list format.

Mock provider. The mock provider returns canned text. It is allowed only when the server runs with `LLM_PROVIDER=mock`; otherwise a call naming `mock` is denied before retrieval, whatever the model list says. Without this, a deployment with no `models.yaml` let any caller get a canned board brief that looks real. Mock results start with a `MOCK OUTPUT:` text block and carry `_meta["eaia/mock"] = true`.

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
| arguments | jsonb | redacted: `query`/`question`/`meeting_focus` stored as HMAC-SHA256 plus length unless `MCP_AUDIT_STORE_TEXT=true` (section 6.2) |
| document_set_id | uuid null | |
| outcome | text | `ok` / `error` / `rate_limited` / `denied` |
| error_class | text null | |
| duration_ms | int | |
| provider, model | text null | resolved provider and model for LLM tools |
| request_id | uuid null | reserved for the ADR 0003 ledger |
| detail | text null | set when the caller passed `accept_unaudited` (section 6.1) |

Append-only: the migration adds triggers that reject `UPDATE`, `DELETE`, and `TRUNCATE` on the table for every role. Grants alone were not enough, because the app role runs migrations and owns the table, and an owner can grant itself anything. A table owner can still disable the triggers. For tamper resistance against the app credentials themselves, run the MCP server with a separate role that has `INSERT, SELECT` only; the runbook has the SQL. Retention runs as the owner and disables the trigger inside one transaction.

Writes: each record is written in its own session and transaction, so a failed tool call still produces a row. The write happens after the operation, so the row holds the outcome and duration. Every record is also logged at INFO on logger `eaia.mcp.audit`, which gives a second copy for log shipping. Section 6.1 covers what happens when the write fails.

#### 6.1 Audit write failure: fail closed, with an explicit override

The first version failed open: if the insert failed, the result went back to the client and the gap was noted in the log. It was changed after review. The owner's position is that a call the system cannot account for should not return data by default, and that the person asking should decide whether an unaudited answer is acceptable.

Behavior:

1. The operation runs, then the audit row is written.
2. If the write succeeds, the result (or error) is returned as before.
3. If the write fails, the result is withheld. The client gets `The call was blocked because it could not be written to the audit log.` plus a reference ID and, for tools, the instruction to call again with `accept_unaudited=true` if the answer is still wanted. The database error text is never sent. A line with event `audit_refused` is appended to the fallback file (below).
4. A call with `accept_unaudited=true` is a new call. It runs the operation and tries the audit table again. If the table write succeeds, the row is normal and `detail` records that the override was requested. Nothing else changes.
5. If the table write fails again, the server appends an `unaudited_override` line to the fallback file. Only after that line is written (with `fsync`) does the result go back. The result's first text block starts with `UNAUDITED:` and the reference ID, and `_meta["eaia/audit"]` is `{"audited": false, "reference": "<id>"}` so clients can detect it without parsing text. Structured content is unchanged.
6. If the fallback file also cannot be written, the override is refused. There is then no durable record of the override, so the answer is not returned.
7. If the operation itself failed (for example, the model was denied), the override returns that error with the `UNAUDITED` notice. No data leaves, so there is nothing to withhold.

Scope: the override exists on all 12 tools (`test_override_reaches_the_guard_on_every_tool` checks each one). Resources and prompts fail closed with no override. MCP resources and prompts do not take extra arguments in a way clients present to users, and neither carries a cost that a retry would repeat.

Settings:
- `MCP_AUDIT_ALLOW_UNAUDITED_OVERRIDE` (default `true`). `false` makes every audit failure a hard failure. Use `false` where policy says no record, no answer.
- `MCP_AUDIT_FALLBACK_FILE` (default `data/audit/mcp_audit_fallback.jsonl`). JSON Lines, opened with `O_APPEND`, mode `0600`, `fsync` on every line. The application never truncates it. Each line holds the same redacted fields as the table plus `event`, `logged_at`, and the class name of the database error. Operators reconcile it after an outage (runbook).

Why the override is an argument and not a server prompt: MCP has an elicitation feature that lets a server ask the user a question mid-call. Client support is uneven, and a call that waits on a person holds a model response open. An argument is visible in the client's tool-call display, works with every client, and lands in the audit record. The tool description tells the calling model to leave it false unless the user asked.

Alternatives considered:

| Option | Why not chosen |
|---|---|
| Fail open (first version) | Returns data the system cannot account for. Owner rejected it. |
| Fail closed, no override | Simple and strict. Available with `MCP_AUDIT_ALLOW_UNAUDITED_OVERRIDE=false`. Not the default because a database outage would stop all work, including a user who accepts the gap. |
| Write the audit row before the operation | Catches a down database before a paid model call. Needs a second row or an update to record the outcome, and the table is append-only. Kept as a follow-up if cost waste on refused calls shows up in practice. |
| Cache the refused result and return it on override | Avoids a second model call. Holds sensitive output in memory keyed by an ID that becomes a bearer credential for that result. Rejected. |
| Fallback to log lines only | Logs rotate and are not guaranteed durable at the moment of return. The fallback file is synced before the answer goes out. |

Risks:
- A refused LLM call has already spent tokens, and the override spends them again. The rate limiter counts both calls. Expect this cost only during a database outage.
- The fallback file is on local disk. It is not tamper-evident; a user with shell access to the host can edit it. It is evidence of overrides, not proof. Ship it to log storage if that matters.
- A caller model could set `accept_unaudited=true` on its own. The field description says not to, the value appears in the client's tool-call view, and every use is recorded. If that is not enough, set the override off.
- The fallback file grows during an outage and is never rotated by the application. The runbook covers rotation.

#### 6.2 Hashing free text

Free text (`query`, `question`, `meeting_focus`) is stored as `{"hmac_sha256": ..., "length": ...}`, keyed by `MCP_AUDIT_HASH_KEY`. A plain SHA-256 of a short question can be reversed by hashing guesses; a keyed hash cannot be checked without the key.

- The key is required for HTTP on a non-loopback host. The server exits with code 2 without it, or if it is shorter than 32 characters.
- On stdio and loopback HTTP with no key, the server uses a random key for the life of the process and logs a warning. Hashes from that process cannot be matched later.
- Generate a key: `python -c "import secrets; print(secrets.token_hex(32))"`. Store it with the other secrets. Rotating it makes older hashes unmatchable with the new key; keep the old key if you need to check old rows.
- This is a change: rows written before it have a `sha256` field; rows after it have `hmac_sha256`. Queries that compared `sha256` must change (runbook).

#### 6.3 Malformed investigation IDs

Resources and prompts take an investigation ID as a string. A value that is not a UUID used to reach the `uuid` column in the audit insert, fail there, and look like an audit outage. The guard now parses the ID first: a malformed value is an `InvalidInput` error, audited with `outcome = error`, `document_set_id` null, and the raw value in `arguments`.

#### 6.4 Circuit breaker

When an audit write fails, a model call has already spent tokens before the refusal. To limit that, for `MCP_AUDIT_BREAKER_SECONDS` (default 30, `0` turns it off) after a failed write, tools that call a model are refused before retrieval or the provider runs. The message says the model was not called.

- The refusal is itself audited. If that write succeeds, the breaker closes and the caller is told to call again.
- `accept_unaudited=true` skips the breaker: the call runs and the audit table is retried before the fallback file, as in 6.1. A user who asked for the answer gets it.
- Read tools, resources, and prompts are not affected; they cost nothing to retry.

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
| Sensitive text in audit log | Free text stored as keyed HMAC by default; key required off loopback |
| Repeated paid calls during an audit outage | Circuit breaker refuses model calls before the provider for 30 s after a failure |
| Canned output mistaken for advice | Mock allowed only with `LLM_PROVIDER=mock`; output labeled |
| Audit tampering | Append-only triggers; optional least-privilege role |
| Audit outage hides calls | Fail closed. Results are withheld unless the caller overrides; each override is written to a synced fallback file first |
| Caller model overrides audit without the user asking | Override visible in the tool call; recorded in table or fallback file; can be turned off |

## Acceptance criteria

1. `python -m app.mcp_server --transport streamable-http --host 0.0.0.0` exits non-zero with no tokens configured.
2. HTTP request without or with a wrong bearer token gets 401; correct token succeeds.
3. `ask_advisor` with `llm_model="not-allowed"` returns a `ToolError` and makes no provider call.
4. A provider exception containing `sk-...` or a DB URL never appears in the client response; response contains a correlation ID that matches a server log line.
5. No module under `app/mcp_server` imports from `app.api.routes` (enforced by test).
6. The 11th LLM-tool call within a minute from one client is rejected; read-only tools are unaffected.
7. Every tool call, including failures and rejections, writes one `mcp_audit_events` row; the app DB role cannot update or delete rows.
8. Existing 184 tests pass.
9. When the audit write fails, a tool call returns no data, and the message names `accept_unaudited=true` and a reference ID.
10. A call with `accept_unaudited=true` retries the table; on a second failure it writes an `unaudited_override` line to the fallback file before returning a result marked `UNAUDITED` in text and `_meta`.
11. With `MCP_AUDIT_ALLOW_UNAUDITED_OVERRIDE=false`, or when the fallback file cannot be written, the override is refused.
12. Resources and prompts have no override.
13. `accept_unaudited` works on all 12 tools.
14. A malformed investigation ID is audited as a validation error, not an audit failure.
15. Free text is stored as HMAC-SHA256; HTTP off loopback without `MCP_AUDIT_HASH_KEY` exits 2.
16. After an audit failure, model tools are refused before the provider until the breaker closes; the override still runs.
17. `mock` is denied unless `LLM_PROVIDER=mock`; mock output is labeled.

All seventeen are covered by tests in `tests/test_mcp_hardening.py` and `tests/test_mcp_audit_postgres.py`. The Postgres tests run when `EAIA_PG_INTEGRATION_URL` is set; CI does not set it yet; the CI change is on local branch `ci-postgres-tests` (see Follow-ups).

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
- Risk: fail-closed audit means a database outage blocks results until the caller overrides or the database returns. This is the intended trade (section 6.1).

## Changes from the draft

| Draft | Built | Reason |
|---|---|---|
| Append-only through grants | Triggers, plus optional `INSERT, SELECT` role | The app role owns the table, so grants do not bind it |
| Audit failure behavior unstated | Fail closed, with an explicit `accept_unaudited` override recorded in a fallback file | First built as fail open; changed after owner review (section 6.1) |
| Allowlist of model names | Dated model list with notes and a validation command | Makes the list easy to keep current |
| SHA-256 of free text | HMAC-SHA256 with `MCP_AUDIT_HASH_KEY` | Plain hashes of short text can be guessed |
| Local provider and new default models in this PR | Split to a separate draft PR | Review: keep this PR to hardening |
| Allowlist for the server | Allowlist for MCP only | Keeps this change inside the MCP layer; ADR 0002 moves it to the service layer |
| `provider`/`model` filled by ADR 0002 | Filled now for LLM tools | The allowlist already resolves both |
| Custom auth middleware implied | MCP SDK bearer middleware with a static verifier | Less code, standard 401 behavior, path to OAuth |

## Follow-ups

- Run `tests/test_mcp_audit_postgres.py` in CI: set `EAIA_PG_INTEGRATION_URL` and move `alembic upgrade head` before `pytest` in `ci-validate.yml`. The commit is on local branch `ci-postgres-tests` and is not pushed: pushing workflow files needs a token with `workflow` scope.
- Shared rate-limit backend before running more than one MCP instance.
- Apply the model allowlist to REST and Streamlit (ADR 0002).
- REST API authentication and the Dockerfile bind: issue #27.

## Dependencies

None. ADR 0002 uses the `config/models.yaml` file and the `provider`/`model` audit columns. ADR 0003 links ledger rows to `request_id`.
