# MCP server operations

Runbook for operators of the Executive AI Advisor MCP server. Design and reasons: [ADR 0001](../adr/0001-mcp-hardening-and-audit-log.md).

## Settings

| Variable | Default | Purpose |
|---|---|---|
| `MCP_AUTH_TOKENS` | empty | Comma-separated `label:sha256hex` entries. Turns on bearer auth for HTTP. |
| `MCP_ALLOW_INSECURE_BIND` | `false` | Allows HTTP on a non-loopback address with no tokens. Lab use only. |
| `MCP_MODEL_POLICY_FILE` | `config/models.yaml` | Model allowlist. Missing file: allow only the models set in the environment. |
| `MCP_RATE_LIMIT_READ_PER_MINUTE` | `60` | Per client: read tools, resources, prompts. |
| `MCP_RATE_LIMIT_LLM_PER_MINUTE` | `10` | Per client: tools that call a model. |
| `MCP_RATE_LIMIT_LLM_PER_DAY` | `200` | Per client, rolling 24 hours. |
| `MCP_AUDIT_STORE_TEXT` | `false` | Store `query`, `question`, `meeting_focus` text in the audit log instead of a hash and length. |
| `MCP_AUDIT_ALLOW_UNAUDITED_OVERRIDE` | `true` | Allow `accept_unaudited=true` on tools when the audit table cannot be written. `false`: block with no override. |
| `MCP_AUDIT_FALLBACK_FILE` | `data/audit/mcp_audit_fallback.jsonl` | Append-only file for overrides and refusals during an audit outage. |

Restart the server after any change. Settings are read at startup.

## Start-up rules

| Transport | Host | Tokens | Result |
|---|---|---|---|
| stdio | n/a | n/a | Starts. Client is `stdio:<os user>`. |
| HTTP | loopback | none | Starts with a warning. Client is `http:unauthenticated-local`. |
| HTTP | loopback or other | set | Starts. Every request needs a valid bearer token. |
| HTTP | other | none | Exits with code 2. |
| HTTP | other | none, `MCP_ALLOW_INSECURE_BIND=true` | Starts with a warning on every start. |

## Issue a token

```bash
python -m app.mcp_server.tokens cursor-tim
# Token (give to the client, shown once): 3q2-...
# MCP_AUTH_TOKENS entry: cursor-tim:9f86d0...
```

1. Add the entry to `MCP_AUTH_TOKENS`. Separate entries with commas. Labels must be unique.
2. Restart the server.
3. Give the token to the client over a private channel. The server stores only the hash; a lost token cannot be recovered, only replaced.

Client configuration (Cursor):

```json
{
  "mcpServers": {
    "executive-ai-advisor": {
      "url": "https://eaia.example.org/mcp",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}
```

Use one label per person and client so the audit log and rate limits separate them.

## Revoke or rotate a token

1. Remove the entry from `MCP_AUTH_TOKENS`, or replace it with a new one for the same label.
2. Restart the server. Requests with the old token get HTTP 401.
3. Check the audit log for use of that label before revocation (query below).

## Read the audit log

Table `mcp_audit_events`. One row per tool call, resource read, or prompt, including errors, rate-limit rejections, and allowlist denials.

Outcomes: `ok`, `error`, `rate_limited`, `denied`.

Recent activity by client:

```sql
SELECT client_id, name, outcome, count(*)
FROM mcp_audit_events
WHERE occurred_at > now() - interval '1 day'
GROUP BY 1, 2, 3
ORDER BY 4 DESC;
```

Find the row for an error a user reported. The message ends with `Reference: <uuid>`:

```sql
SELECT * FROM mcp_audit_events WHERE correlation_id = '<uuid>';
```

The same ID is in the server log on logger `eaia.mcp` with the full trace.

Model use:

```sql
SELECT provider, model, client_id, count(*)
FROM mcp_audit_events
WHERE kind = 'tool' AND provider IS NOT NULL AND occurred_at > now() - interval '7 days'
GROUP BY 1, 2, 3;
```

Arguments hold a SHA-256 hash and length for free text. To check whether a known question was asked, hash it the same way:

```sql
SELECT occurred_at, client_id, name
FROM mcp_audit_events
WHERE arguments -> 'question' ->> 'sha256' = encode(sha256(convert_to('<exact question>', 'UTF8')), 'hex');
```

### Audit write failures

Audit writes fail closed. Design: ADR 0001 section 6.1.

What the user sees:

1. A tool call returns `The call was blocked because it could not be written to the audit log.`, the override instruction, and `Reference: <uuid>`. Resources and prompts return the block message with no override.
2. If the user still wants the answer, the client calls the same tool again with `accept_unaudited=true`.
3. The server tries the table again. If it works, the row is normal and `detail` is `accept_unaudited requested`.
4. If it fails again, the server writes an `unaudited_override` line to the fallback file and returns the answer. The text starts with `UNAUDITED:` and `_meta["eaia/audit"].audited` is `false`.
5. If the fallback file cannot be written either, the call is blocked with `the audit log and the fallback audit file are both unavailable`.

Alert on the ERROR message `Audit write failed` on logger `eaia.mcp.audit`. Every record is also logged at INFO on that logger.

Respond:

1. Find the database error class in the server log or in the `audit_db_error_class` field of the fallback file (for example `OperationalError`: connection; `InternalError` with "read-only transaction": a replica or read-only setting; `InsufficientPrivilege`: the role lost `INSERT`).
2. Fix the database. Confirm with one tool call that returns normally.
3. To stop all results until the database is fixed, set `MCP_AUDIT_ALLOW_UNAUDITED_OVERRIDE=false` and restart.

Reconcile the fallback file after an outage:

```bash
# What happened during the outage
jq -r '[.logged_at, .event, .client_id, .name, .outcome, .correlation_id] | @tsv' data/audit/mcp_audit_fallback.jsonl

# Overrides only
jq -c 'select(.event == "unaudited_override")' data/audit/mcp_audit_fallback.jsonl
```

Each line has the same redacted fields as a table row. `audit_refused` lines are calls that returned no data. `unaudited_override` lines are calls that returned data with no table row. Keep the file with your audit records; the application does not import it into the table, because a later insert would carry the wrong trust level for an append-only log. To start a new file, stop the server, move the file to archive storage, and restart. The server creates a new file with mode `0600`.

Keep the file on a disk the server user can write and other users cannot read. The directory `data/audit/` is in `.gitignore`.

## Least-privilege database role

Triggers block `UPDATE`, `DELETE`, and `TRUNCATE` for every role, but the table owner can disable them. To keep the MCP server's credentials from altering history, run the server as a role that does not own the table:

```sql
CREATE ROLE eaia_mcp LOGIN PASSWORD '<set-me>';
GRANT CONNECT ON DATABASE executive_ai_advisor TO eaia_mcp;
GRANT USAGE ON SCHEMA public TO eaia_mcp;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO eaia_mcp;
GRANT INSERT ON mcp_audit_events TO eaia_mcp;
```

Then set `DATABASE_URL` for the MCP process only to use `eaia_mcp`. Run migrations with the owner role. This was checked against Postgres 16: as `eaia_mcp`, `INSERT` works, `DELETE` is denied, and `ALTER TABLE ... DISABLE TRIGGER` fails with "must be owner".

## Retention

Run as the table owner. Choose the period your policy requires; 365 days is an example.

```sql
BEGIN;
ALTER TABLE mcp_audit_events DISABLE TRIGGER mcp_audit_events_no_update_delete;
DELETE FROM mcp_audit_events WHERE occurred_at < now() - interval '365 days';
ALTER TABLE mcp_audit_events ENABLE TRIGGER mcp_audit_events_no_update_delete;
COMMIT;
```

The `ALTER TABLE` takes a lock that blocks audit inserts until commit. Run it in a quiet period. Export rows to archive storage first if you need them later.

## TLS and reverse proxy

The server speaks plain HTTP. For anything beyond localhost, put a TLS proxy in front and keep bearer tokens on. Example with Caddy:

```
eaia.example.org {
    reverse_proxy 127.0.0.1:8765
}
```

Start the server on loopback and pass the public URL so the OAuth metadata is correct:

```bash
python -m app.mcp_server --transport streamable-http --host 127.0.0.1 --port 8765 \
  --public-url https://eaia.example.org
```

Do not rely on the proxy alone for authentication; keep `MCP_AUTH_TOKENS` set.

## Model list

```bash
cp config/models.example.yaml config/models.yaml
python -m app.mcp_server.model_policy config/models.yaml
```

The server refuses to start on an unknown provider, an empty list, an unknown key, or invalid YAML. A provider's default model (for example `OPENAI_CHAT_MODEL`) must be in its list, or calls that omit `llm_model` are denied; the check command warns about this. To add or retire models: [Updating the model list](updating-model-list.md).

## Rate-limit tuning

- Limits are per client label, in memory, and per process. They reset on restart.
- A rejected call returns `Rate limit exceeded. Retry after N seconds.` and is audited as `rate_limited`.
- To size limits, count recent use per client:

```sql
SELECT client_id, date_trunc('hour', occurred_at) AS hour, count(*)
FROM mcp_audit_events
WHERE provider IS NOT NULL AND occurred_at > now() - interval '7 days'
GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 20;
```

- Running more than one MCP instance multiplies the effective limit. Use one instance until a shared backend exists.
