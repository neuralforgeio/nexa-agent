# Nexa Agent — Provider Setup Guide (v3.0.0)

Nexa Agent supports any OpenAI-compatible LLM provider. Configure via
interactive CLI, env vars, or the Web UI Settings panel.

## Quick Start

```bash
# 1. List available providers (catalog + custom)
nexa provider list

# 2. Add TokenRouter (interactive — prompts for API key + model)
nexa provider add tokenrouter

# 3. Activate it
nexa provider use tokenrouter

# 4. Start chatting
nexa-chat
```

## Supported Providers (8)

| Provider | Base URL | Default Model | Auth |
|----------|----------|---------------|------|
| openai | https://api.openai.com/v1 | gpt-4o | OPENAI_API_KEY (sk-...) |
| openrouter | https://openrouter.ai/api/v1 | anthropic/claude-3.5-sonnet | OPENROUTER_API_KEY |
| ollama | http://localhost:11434/v1 | llama3.2 | dummy (local) |
| llamacpp | http://localhost:8080/v1 | local-model | dummy (local) |
| lmstudio | http://localhost:1234/v1 | loaded-model | dummy (local) |
| vllm | http://localhost:8000/v1 | meta-llama/Llama-3.1-8B-Instruct | dummy (local) |
| **tokenrouter** | https://api.tokenrouter.io/v1 | auto:balance | TOKENROUTER_API_KEY (tr_...) |
| **databricks** | (set NEXA_BASE_URL) | databricks-claude-sonnet-4-6 | DATABRICKS_TOKEN (dapi...) |

## TokenRouter (v3.0.0 new)

TokenRouter is an OpenAI-compatible LLM routing gateway. It picks the cheapest/
fastest/best model per request.

### Setup

1. Sign up at https://tokenrouter.io/signup
2. Console → API Keys → create, copy the `tr_...` value immediately
3. Add to Nexa:

```bash
nexa provider add tokenrouter
# ? API key (input hidden): tr_your_key_here
# ? Model ID [auto:balance]:
✓ Saved tokenrouter to ~/.nexa/secrets/providers.json

nexa provider use tokenrouter
✓ Switched to tokenrouter (auto:balance)
```

### Model IDs

- **Routing modes** (recommended — TokenRouter picks the upstream model):
  - `auto:balance` (default; 40% cost / 40% quality / 20% latency)
  - `auto:cost` (80% cost optimization)
  - `auto:quality` (80% quality)
  - `auto:latency` (80% latency)
- **Pinned models**: `gpt-4o`, `claude-3-7-sonnet-latest:quality`,
  `anthropic:claude-3-5-sonnet`, `gemini:...`, `mistral:...`, `deepseek:...`

### Python SDK usage (drop-in OpenAI)

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key="tr_...",
    base_url="https://api.tokenrouter.io/v1",
)
stream = await client.chat.completions.create(
    model="auto:balance",
    messages=[{"role": "user", "content": "Hello!"}],
    stream=True,
)
```

## Databricks (v3.0.0 new)

Databricks Foundation Model APIs / AI Gateway.

### Setup

1. Get a Databricks Personal Access Token (PAT) from your workspace
   (Settings → User → Access Tokens). Prefix `dapi...`.
2. Note your workspace host (e.g. `https://my-workspace.cloud.databricks.com`).
3. Add to Nexa:

```bash
# Set env vars first (databricks has no default base_url)
export DATABRICKS_TOKEN="dapi..."
export NEXA_BASE_URL="https://my-workspace.cloud.databricks.com/serving-endpoints"

nexa provider add databricks \
  --base-url "https://my-workspace.cloud.databricks.com/serving-endpoints" \
  --api-key "dapi..." \
  --model "databricks-claude-sonnet-4-6"

nexa provider use databricks
```

### Model IDs (current)

- `databricks-claude-sonnet-4-6`, `databricks-claude-opus-4-8`
- `databricks-gpt-oss-20b`, `databricks-gpt-oss-120b`
- `databricks-meta-llama-3-3-70b-instruct`
- `databricks-qwen35-122b-a10b`
- See full list at https://docs.databricks.com/en/machine-learning/model-serving/

## Custom Endpoint (any OpenAI-compatible)

For providers not in the catalog (e.g. a private vLLM, Azure OpenAI, Together AI):

```bash
nexa provider add my-custom-llm \
  --base-url "https://my-llm.example.com/v1" \
  --api-key "sk-mykey" \
  --model "my-model-v1"

nexa provider use my-custom-llm
```

## Provider Management Commands

```bash
nexa provider list                 # show all + active
nexa provider add <name>           # interactive add (or use --flags)
nexa provider use <name>           # activate
nexa provider remove <name>        # delete from registry
nexa provider test <name>          # health-check (GET /v1/models)
```

## Web UI

Click the gear icon (⚙) in the sidebar footer to open the Settings panel.
Add/remove/test providers without restarting the server.

## Slash Commands (CLI / TUI)

```
/provider               # show current
/provider list          # list all
/provider use <name>    # switch
/provider test <name>   # health-check
/provider add            # interactive (CLI only; TUI uses terminal)
/provider remove <name>  # delete
```

## Security (v3.0.0)

- API keys are stored in `~/.nexa/secrets/providers.json` (chmod 600 on Unix).
- `run_terminal_command` blocks access to `~/.nexa/` entirely — the LLM cannot
  exfiltrate your API keys via shell commands.
- `list_all()` masks API keys as `tr_...wxyz` in display.
- The Web UI Settings panel never receives the full key back from the server
  (only the masked version).

## Failover (optional)

Set `NEXA_FAILOVER_ENABLED=1` and `NEXA_FAILOVER_CHAIN=tokenrouter,openai` to
enable automatic provider failover. When the active provider fails 3 times in
a row, the agent switches to the next healthy provider in the chain.

```bash
export NEXA_FAILOVER_ENABLED=1
export NEXA_FAILOVER_CHAIN=tokenrouter,openai,ollama
```

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXA_PROVIDER` | openai | Active provider name |
| `NEXA_MODEL` | gpt-4o | Model override |
| `NEXA_BASE_URL` | (empty) | Custom base URL (for "custom" provider) |
| `OPENAI_API_KEY` | (empty) | Universal API key fallback |
| `NEXA_API_KEY` | (empty) | Universal API key fallback |
| `<NAME>_API_KEY` | (empty) | Provider-specific key (e.g. TOKENROUTER_API_KEY) |
| `DATABRICKS_TOKEN` | (empty) | Databricks PAT (alternative to DATABRICKS_API_KEY) |
| `NEXA_FAILOVER_ENABLED` | 0 | Enable provider failover |
| `NEXA_FAILOVER_CHAIN` | (empty) | Comma-separated provider names for failover |
| `NEXA_AUTONOMOUS_LEARNING` | 0 | Enable autonomous web learning |

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
