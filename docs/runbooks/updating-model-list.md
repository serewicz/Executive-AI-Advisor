# Updating the model list

The MCP server calls only the models listed in `config/models.yaml`. This runbook covers adding a model, retiring one, adding a local model, checking the file, testing, and rolling back. Design: [ADR 0001](../adr/0001-mcp-hardening-and-audit-log.md), section 2.

Do this when a provider releases or retires a model, when you change a default model in the environment, or at least once a quarter. The `as_of` date at the top of the file tells you when the list was last checked.

## File format

```yaml
as_of: "2026-10-25"          # date you last checked the IDs against provider pages

providers:
  openai:
    notes: Optional note for the provider.
    models:
      - id: gpt-6-luna       # exact model ID the provider's API accepts
        notes: Lowest-cost current model. Default for routine summaries.
      - id: gpt-6.1-sol
  local:
    base_url: http://127.0.0.1:11434/v1   # must equal LOCAL_LLM_BASE_URL
    models:
      - id: llama3.2:3b
```

Rules:

- Providers: `mock`, `openai`, `anthropic`, `grok`, `local`. Any other name stops the server.
- Each provider needs at least one model. To turn a provider off, delete its block.
- Unknown keys stop the server. This catches typos.
- `id` must match the provider's API ID exactly. A display name such as "GPT-6 Luna" will not work.
- The older form `allowed_models: [a, b]` still loads. New edits should use `models`.

## Add or retire a hosted model

1. Copy the file you run, so you can roll back:

   ```bash
   cp config/models.yaml config/models.yaml.bak
   ```

2. Look up the current IDs on the provider's model page:
   - OpenAI: https://platform.openai.com/docs/models
   - Anthropic: https://docs.anthropic.com/en/docs/about-claude/models
   - xAI (Grok): https://docs.x.ai/docs/models
3. Edit `config/models.yaml`:
   - To add: add an `- id:` line under the provider, with a short `notes` line (cost tier, intended use).
   - To retire: delete the line. Calls that name that model are then denied before the provider is contacted.
   - Set `as_of` to today's date.
4. If you retire a provider's default model, change the default in `.env` too:

   | Provider | Default variable |
   |---|---|
   | openai | `OPENAI_CHAT_MODEL` |
   | anthropic | `ANTHROPIC_CHAT_MODEL` |
   | grok | `XAI_CHAT_MODEL` |
   | local | `LOCAL_LLM_MODEL` |

   The default must be in the list, or calls that omit `llm_model` are denied.
5. Validate (next section), then restart the MCP server. The file is read at startup only.

## Add a local LLM or SLM

Provider `local` sends chat requests to any server that speaks the OpenAI chat-completions API. No vendor key is needed and documents stay on your network. Example with Ollama:

1. Install and start the model server, and pull a model:

   ```bash
   ollama pull llama3.2:3b
   ollama serve            # listens on 127.0.0.1:11434
   ```

   llama.cpp server (`llama-server`) and vLLM work the same way. Use the URL that ends in `/v1`.
2. Check that the server answers:

   ```bash
   curl -s http://127.0.0.1:11434/v1/models
   ```

   Use the model ID exactly as it appears in that output.
3. Set the environment in `.env`:

   ```bash
   LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
   LOCAL_LLM_MODEL=llama3.2:3b
   LOCAL_LLM_API_KEY=            # only if your server requires one
   ```

4. Add or edit the `local` block in `config/models.yaml`. `base_url` must equal `LOCAL_LLM_BASE_URL` (a trailing `/` is ignored), or the server does not start. If `LOCAL_LLM_BASE_URL` is set and the block has no `base_url`, the server does not start either. Always set both. This stops a changed environment variable from sending evidence to a host nobody reviewed.

   ```yaml
   local:
     base_url: http://127.0.0.1:11434/v1
     models:
       - id: llama3.2:3b
         notes: Small model on the advisor host. Drafts only.
       - id: qwen3:14b
         notes: Larger local model for board summaries.
   ```

5. Validate and restart.

Choosing a local model:

- The advisor asks for JSON output. Some OpenAI-compatible servers ignore `response_format`, and small models (1-3B parameters) often return malformed JSON on long prompts. The tool then returns an error with a reference ID, after the tokens are spent. Run one real `board_brief` call against each model before you list it.
- Context length must fit the retrieved evidence plus the prompt. 8k tokens is a working minimum.
- The advisor sends retrieved document excerpts to `LOCAL_LLM_BASE_URL`. "Local" is the API style, not a guarantee of location. If the server is on another host, use TLS or a private network, and treat the host as holding your documents.

## Validate

```bash
python -m app.mcp_server.model_policy config/models.yaml
```

Output on success:

```
OK: config/models.yaml (as_of 2026-10-25)
  openai: gpt-6-luna, gpt-6.1-sol
  ...
```

It exits 1 with the reason on an invalid or missing file. It prints `WARNING` for each provider whose default model is not in the list. Fix warnings before you restart, or calls without `llm_model` fail.

## Test

1. Run the policy tests:

   ```bash
   pytest tests/test_mcp_hardening.py -q
   ```

   These check the example file. If you changed `config/models.example.yaml`, they must pass.
2. Restart the server and make one call per changed model with your MCP client, for example `ask_advisor` with `llm_provider` and `llm_model` set.
3. Confirm the call in the audit log:

   ```sql
   SELECT occurred_at, provider, model, outcome
   FROM mcp_audit_events
   WHERE occurred_at > now() - interval '15 minutes'
   ORDER BY occurred_at DESC;
   ```

   `denied` means the pair is not in the list. `error` with a reference ID means the provider rejected the call; look up the ID in the server log.

## Roll back

```bash
cp config/models.yaml.bak config/models.yaml
python -m app.mcp_server.model_policy config/models.yaml
```

Restore `.env` if you changed a default, then restart. If the file is in your own config repository, `git revert` the commit instead.

## Change the example file in this repository

`config/models.example.yaml` is the starting point for new deployments. When you update it, set `as_of`, keep a `notes` line on each model, run the tests above, and add a CHANGELOG entry.
