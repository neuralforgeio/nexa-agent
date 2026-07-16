# Nexa Agent — Provider Setup Guide

This document explains how to configure each LLM provider.

## Provider Overview

| Provider | Local? | API Key Required | Best For |
|----------|--------|------------------|----------|
| OpenAI | No | Yes | GPT-4o, best quality |
| OpenRouter | No | Yes | Access 100+ models with one key |
| Ollama | Yes | No (dummy) | Free local models |
| llama.cpp | Yes | No (dummy) | Custom GGUF models |
| LM Studio | Yes | No (dummy) | GUI model loading |
| vLLM | Yes | No (dummy) | High-throughput inference |

## Configuration Methods

### Method 1: Environment Variables (.env)

```bash
# Copy template
cp .env.example .env

# Edit .env:
NEXA_PROVIDER=ollama
NEXA_MODEL=llama3.2
OPENAI_API_KEY=sk-your-key  # only for OpenAI/OpenRouter
```

### Method 2: CLI Flags

```bash
python cli.py --provider ollama --model llama3.2
python cli.py --provider openai --model gpt-4o --api-key sk-your-key
python cli.py --provider llamacpp --base-url http://localhost:8080/v1
```

### Method 3: TUI Slash Commands

```
nexa > /provider ollama
nexa > /model llama3.2
```

## Provider Setup Guides

### OpenAI

1. Get an API key from https://platform.openai.com/api-keys
2. Set environment:
   ```bash
   export NEXA_PROVIDER=openai
   export OPENAI_API_KEY=sk-your-key
   export NEXA_MODEL=gpt-4o
   ```
3. Run: `python cli.py`

**Models**: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo

### OpenRouter

1. Get an API key from https://openrouter.ai/keys
2. Set environment:
   ```bash
   export NEXA_PROVIDER=openrouter
   export OPENAI_API_KEY=sk-or-your-key
   export NEXA_MODEL=anthropic/claude-3.5-sonnet
   ```
3. Run: `python cli.py`

**Models**: anthropic/claude-3.5-sonnet, google/gemini-pro, meta-llama/llama-3.1-70b, and 100+ more

### Ollama (Local AI — Recommended for privacy)

1. Install Ollama: https://ollama.com
2. Pull a model:
   ```bash
   ollama pull llama3.2
   # or: ollama pull qwen2.5
   # or: ollama pull mistral
   ```
3. Set environment:
   ```bash
   export NEXA_PROVIDER=ollama
   export NEXA_MODEL=llama3.2
   ```
4. Run: `python cli.py --provider ollama --model llama3.2`

**No API key needed** — Ollama accepts any non-empty string.

**Models**: llama3.2, qwen2.5, mistral, phi3, gemma2, and more

### llama.cpp

1. Build llama.cpp with server support
2. Start the server:
   ```bash
   ./llama-server -m model.gguf --port 8080
   ```
3. Set environment:
   ```bash
   export NEXA_PROVIDER=llamacpp
   ```
4. Run: `python cli.py --provider llamacpp`

**No API key needed.**

### LM Studio

1. Download LM Studio: https://lmstudio.ai
2. Load a model in the GUI
3. Start the local server (default port 1234)
4. Run: `python cli.py --provider lmstudio`

**No API key needed.**

### vLLM

1. Install vLLM: https://docs.vllm.ai
2. Start the server:
   ```bash
   python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-3.1-8B-Instruct
   ```
3. Run: `python cli.py --provider vllm`

**No API key needed.**

## Custom Provider

Any OpenAI-compatible endpoint can be used:

```bash
export NEXA_BASE_URL=https://your-endpoint.com/v1
export NEXA_MODEL=your-model
export OPENAI_API_KEY=your-key
python cli.py
```

Or via CLI flags:
```bash
python cli.py --base-url https://your-endpoint.com/v1 --model your-model --api-key your-key
```

## Provider Resolution Order

The `resolve_provider()` function in `providers/catalog.py` resolves the
provider in this order:

1. `--provider` CLI flag (highest priority)
2. `NEXA_PROVIDER` environment variable
3. `NEXA_BASE_URL` environment variable (treated as custom provider)
4. Default: `openai`

The API key is resolved from:
1. `OPENAI_API_KEY`
2. `NEXA_API_KEY`
3. `<PROVIDER>_API_KEY` (e.g., `OLLAMA_API_KEY`)
4. For local providers (ollama, llamacpp, lmstudio, vllm): `"dummy"` if none set
