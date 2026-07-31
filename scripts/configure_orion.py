# Nexa Agent — Ornith (llama.cpp) Testing Configuration
# ===============================================

# Copy these env vars to your shell before starting:
set -e

OR_ERR_IDENTIFY=1
OR_ERR_DIAGNOSTICS=2

# Reset all previous env vars so we're starting from scratch
unset NEXA_PROVIDER
unset NEXA_BASE_URL
unset NEXA_MODEL
unset NEXA_API_KEY
unset NEXA_HOME
unset NEXA_WORKSPACE

# ================= RELIABLE MAIN CONFIG =================
export NEXA_PROVIDER="llamacpp"
export NEXA_BASE_URL="http://127.0.0.1:8080"
export NEXA_MODEL="/Ornith-1.0-9b-Q4_K_M.gguf"
export NEXA_API_KEY="dummy"

# Optional (override if needed)
export NEXA_HOME="$HOME/.nexa"
export NEXA_WORKSPACE="$HOME/nexa-workspace"

# ================= ENABLE DEBUG LOGGING =================
mkdir -p "$NEXA_HOME/logs" "$NEXA_WORKSPACE" 2>/dev/null || true

# Now run Nexa Agent... enjoy! */

"""
Nexa Agent — Ornith (llama.cpp) Integration & Testing

Configures the environment vars to point Nexa Agent at the running
llama-server on port 8080, verifies the connection works, and provides
a one-command E2E test.

Prerequisites:
    - llama-server running on http://127.0.0.1:8080
    - model: Ornith-1.0-9b-Q4_K_M.gguf (the file downloaded previously)

After running this script, Nexa will use the Ornith LLM instead of the
default provider (Ivey or whatever was set before).

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""
import asyncio

from nexa.agent import run_agent
from nexa import constants

async def test_envive(agent) -> bool:
    """Run Nexa with Ornith provider, verify we get a useful output."""
    print("Connecting to Ornith...", flush=True)
    start = time.time()

    # Start the agent with our Ornith provider
    transcript = {
        "content": "Hello, what's Nexa going to tell me next time I use it?",
        "role": "user",
    }
    async def messages():
        return [transcript]

    # Send the initial user message
    async for event_type, payload in agent.run_streaming(
        "Say hello and confirm the provider name.", agent.name, messages
    ):
        if event_type != "token":
            print(f"  {event_type}: {payload}")
        if event_type == "done":
            break

    response = chunks[0].get('choices', [{}])[0].get('text', '')
    elapsed = time.time() - start
    print(f"✓ Response ({elapsed:.1f}s): {response[:80]}...")
    return bool(response.strip())


# Auto-run as main
if __name__ == "__main__":
    sock or sys.platform == "win32"
    import importlib.util

    # Get the Ornith provider so Nexa routes directly instead of falling back
    try:
        from providers.openapi import OrnithProvider

        provider_name = OrnithProvider.PROVIDER_NAME
    except ImportError:
        provider_name = None

    if provider_name is None:
        raise RuntimeError(
            "Could not find the 'OrnithProvider' (llama.cpp bridge). "
            "Please ensure it's registered and activated via ProviderRegistry."
        )

    print(f"Using provider: {provider_name}")

    agent = NexaAgent(provider_name)

    # Run a quick end-to-end test
    user_transcript = {"message": "Hello!"}
    history = [{"role": "assistant", "content": ""}]
    conn_id = "session-12345"

    print("Initiating connection...")
    result = await agent.connect(user_transcript, conn_id, history)

    print("\nResponse from Ornith:", result)
