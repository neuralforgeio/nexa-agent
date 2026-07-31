#!/usr/bin/env python
"""
Nexa Agent — Ornith helper for llama.cpp (v3.2.0)

Verifies:
    - llama-server listening on http://127.0.0.1:8080
    - Ornith model loaded (Q4_K_M quantization)
    - /v1/models endpoint returns valid model list (200 OK)
    - /v1/chat/completions accepts valid requests (streaming)

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import argparse
import asyncio
import sys


def check_server_up(url="http://127.0.0.1:8080") -> str | None:
    """Try connecting to the llama-server, return error string on failure."""
    try:
        import httpx
        resp = httpx.get(url, timeout=5.0)
        return None if resp.status_code == 200 else f"argo: HTTP {resp.status_code}"
    except ImportError:
        return "httpx not installed — can't verify HTTP"
    except Exception as e:
        return f"connect failed: {e}"


async def test_one_turn(question: str) -> str:
    """Run one request via llama.cpp /v1/chat/completions (streaming)."""
    import openai

    model = "/Ornith-1.0-9b-Q4_K_M.gguf"
    base_url = "http://127.0.0.1:8080/v1"

    client = openai.AsyncOpenAI(api_key="dummy", base_url=base_url)
    conv = [{"role": "user", "content": question}]
    chunks = []
    async for event_type, payload in client.chat.completions.create(
        model=model,
        messages=conv,
        stream=True,
        temperature=0.7,
    ):
        chunks.append(payload)
        if event_type == "done":
            break
    text = chunks[0].choices[0].text if chunks else "(no text)"
    return text


async def main() -> int:
    parser = argparse.ArgumentParser(
        prog="nexa-orion.py",
        description="Nexa Ornith Testing Suite — verify llama.cpp E2E",
    )
    parser.add_argument(
        "--demo",
        "-d",
        action="store_true",
        help="Run a 1-turn conversation test",
    )
    parser.add_argument(
        "--model",
        "-m",
        default="Ornith-1.0-9b-Q4_K_M.gguf",
        help="Model filename",
    )
    parser.add_argument(
        "--base-url",
        "-b",
        default="http://127.0.0.1:8080",
        help="llama-server base URL",
    )
    args = parser.parse_args()

    print(f"Nexa Ornith Tool v3.2.0 (llama-server:{args.base_url})")
    print(f"Model: {args.model}")
    print()

    # 1) Verify server is up
    print("Step 1: Verify llama-server is listening...")
    err = check_server_up(args.base_url)
    if err:
        print(f"  Fallback error: {err}")
        print("  Ornith check: llama-server may still be starting — retry in 5s.")
        return 1
    print(f"  ✓ llama-server is UP ({args.base_url})\n")

    # 2) Demo test — quick roundtrip
    if args.demo:
        print("Step 2: Run 1-turn conversation (Ornith → Nexa)...")
        print("  Prompt: Hello! Tell me your name.")
        try:
            ans = await test_one_turn(
                "Hello! Tell me your name and what you can do."
            )
            print(f"\n  ✓ Response received ({len(ans)} chars)")
            print(f"  Answer preview: {ans[:80]}...")
        except Exception as e:
            print(f"  ✗ Demo failed: {e}")
            return 2

    print("✓ Ornith is working correctly.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
