# OpenForge — Provider Setup Guide (v4.2.0)

OpenForge supports any OpenAI-compatible LLM provider. Configure via
interactive CLI, env vars, or the Web UI Settings panel.

## Quick Start

```bash
# 1. List available providers (catalog + custom)
forge provider list

# 2. Add TokenRouter (interactive — prompts for API key + model)
forge provider add tokenrouter

# 3. Activate it
forge provider use tokenrouter

# 4. Start chatting
forge-chat
```

## Supported Providers (24 in v4.2.0)

### Cloud providers (paid or free tier)

| Provider | Base URL | Default Model | Env var | Free tier |
|----------|----------|---------------|---------|-----------|
| **openai** | https://api.openai.com/v1 | gpt-4o | OPENAI_API_KEY | – |
| **anthropic** | https://api.anthropic.com/v1 | claude-sonnet-4 | ANTHROPIC_API_KEY | – |
| **cohere** | https://api.cohere.com/compatibility/v1 | command-r-plus | COHERE_API_KEY | ✓ |
| **databricks** | (set `FORGE_BASE_URL`) | databricks-claude-sonnet-4-6 | DATABRICKS_TOKEN | – |
| **deepseek** | https://api.deepseek.com/v1 | deepseek-chat | DEEPSEEK_API_KEY | ✓ |
| **fireworks** | https://api.fireworks.ai/inference/v1 | llama-v3p3-70b | FIREWORKS_API_KEY | ✓ |
| **gemini** | https://generativelanguage.googleapis.com/v1beta/openai | gemini-2.0-flash | GEMINI_API_KEY / GOOGLE_API_KEY | ✓ |
| **groq** | https://api.groq.com/openai/v1 | llama-3.3-70b-versatile | GROQ_API_KEY | ✓ |
| **mistral** | https://api.mistral.ai/v1 | mistral-large-latest | MISTRAL_API_KEY | ✓ |
| **perplexity** | https://api.perplexity.ai | sonar-pro | PPLX_API_KEY | – |
| **together** | https://api.together.xyz/v1 | Llama-3.3-70B-Instruct-Turbo | TOGETHER_API_KEY | ✓ |
| **xai** | https://api.x.ai/v1 | grok-2-latest | XAI_API_KEY | – |

### Local / self-hosted

| Provider | Base URL | Default model |
|----------|----------|---------------|
| **jan** | http://localhost:1337/v1 | llama3.2 |
| **koboldcpp** | http://localhost:5001/v1 | loaded-model |
| **llamacpp** | http://localhost:8080/v1 | local-model |
| **lmstudio** | http://localhost:1234/v1 | loaded-model |
| **localai** | http://localhost:8080/v1 | gpt-3.5-turbo |
| **ollama** | http://localhost:11434/v1 | llama3.2 |
| **textgen** | http://localhost:5000/v1 | loaded-model |
| **vllm** | http://localhost:8000/v1 | meta-llama/Llama-3.1-8B-Instruct |

### Routers / gateways

| Provider | Base URL | Default model | Notes |
|----------|----------|---------------|-------|
| **helicone** | https://oai.hconeai.com/v1 | gpt-4o | Observability + caching proxy |
| **litellm** | http://localhost:4000/v1 | gpt-3.5-turbo | Front door for 100+ models |
| **openrouter** | https://openrouter.ai/api/v1 | anthropic/claude-3.5-sonnet | 100+ downstreams |
| **tokenrouter** | https://api.tokenrouter.io/v1 | auto:balance | Cost/latency/quality routing |

## TokenRouter (v3.0.0 new)

TokenRouter is an OpenAI-compatible LLM routing gateway. It picks the cheapest/
fastest/best model per request.

### Setup

1. Sign up at https://tokenrouter.io/signup
2. Console → API Keys → create, copy the `tr_...` value immediately
3. Add to Forge:

```bash
forge provider add tokenrouter
# ? API key (input hidden): tr_your_key_here
# ? Model ID [auto:balance]:
✓ Saved tokenrouter to ~/.openforge/secrets/providers.json

forge provider use tokenrouter
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
3. Add to Forge:

```bash
# Set env vars first (databricks has no default base_url)
export DATABRICKS_TOKEN="dapi..."
export FORGE_BASE_URL="https://my-workspace.cloud.databricks.com/serving-endpoints"

forge provider add databricks \
  --base-url "https://my-workspace.cloud.databricks.com/serving-endpoints" \
  --api-key "dapi..." \
  --model "databricks-claude-sonnet-4-6"

forge provider use databricks
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
forge provider add my-custom-llm \
  --base-url "https://my-llm.example.com/v1" \
  --api-key "sk-mykey" \
  --model "my-model-v1"

forge provider use my-custom-llm
```

## Provider Management Commands

```bash
forge provider list                 # show all + active
forge provider add <name>           # interactive add (or use --flags)
forge provider use <name>           # activate
forge provider remove <name>        # delete from registry
forge provider test <name>          # health-check (GET /v1/models)
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

- API keys are stored in `~/.openforge/secrets/providers.json` (chmod 600 on Unix).
- `run_terminal_command` blocks access to `~/.openforge/` entirely — the LLM cannot
  exfiltrate your API keys via shell commands.
- `list_all()` masks API keys as `tr_...wxyz` in display.
- The Web UI Settings panel never receives the full key back from the server
  (only the masked version).

## Failover (optional)

Set `FORGE_FAILOVER_ENABLED=1` and `FORGE_FAILOVER_CHAIN=tokenrouter,openai` to
enable automatic provider failover. When the active provider fails 3 times in
a row, the agent switches to the next healthy provider in the chain.

```bash
export FORGE_FAILOVER_ENABLED=1
export FORGE_FAILOVER_CHAIN=tokenrouter,openai,ollama
```

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `FORGE_PROVIDER` | openai | Active provider name |
| `FORGE_MODEL` | gpt-4o | Model override |
| `FORGE_BASE_URL` | (empty) | Custom base URL (for "custom" provider) |
| `OPENAI_API_KEY` | (empty) | Universal API key fallback |
| `FORGE_API_KEY` | (empty) | Universal API key fallback |
| `<NAME>_API_KEY` | (empty) | Provider-specific key (e.g. TOKENROUTER_API_KEY) |
| `DATABRICKS_TOKEN` | (empty) | Databricks PAT (alternative to DATABRICKS_API_KEY) |
| `FORGE_FAILOVER_ENABLED` | 0 | Enable provider failover |
| `FORGE_FAILOVER_CHAIN` | (empty) | Comma-separated provider names for failover |
| `FORGE_AUTONOMOUS_LEARNING` | 0 | Enable autonomous web learning |

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
