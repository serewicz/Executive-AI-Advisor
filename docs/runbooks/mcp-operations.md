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

Audit writes fail open: the tool result is returned and the record is logged at ERROR on `eaia.mcp.audit` with the message `Audit write failed`. Alert on that message. Every record is also logged at INFO on the same logger, so a log pipeline can rebuild missing rows.

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

## Model allowlist

```bash
cp config/models.example.yaml config/models.yaml
```

Edit `allowed_models` per provider and restart. The server refuses to start on an unknown provider, an empty list, or invalid YAML. A provider's configured default model (for example `OPENAI_CHAT_MODEL`) must be in its list, or calls that omit `llm_model` are denied.

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
