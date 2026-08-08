"""
Nexa Agent — Real E2E test script for Ornith (llama.cpp).

Run:
    .venv/Scripts/python.exe scripts/e2e_hello_world.py

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import asyncio
import os
import sys
from pathlib import Path

# Use repo-local imports.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("FORGE_QUICK_MODE", "0")  # ensure tools engage


async def main() -> int:
    from run_agent import OpenForgeAgent

    agent = OpenForgeAgent(provider_name="ornith")
    conv = await agent.db.create_conversation(title="e2e-hello-world")

    prompt = (
        "Create a file called hello_e2e.py that prints the string "
        "'Nexa E2E Hello'. Then use run_terminal_command to execute it "
        "with python and confirm the output."
    )

    tool_output = ""
    final_answer = ""
    tool_calls = []

    async for event in agent.run_streaming(prompt, conv["id"]):
        t = event.get("type")
        if t == "token":
            print(event.get("text", ""), end="", flush=True)
        elif t == "tool_result":
            tr = event["result"]
            tool_calls.append(tr)
            tool_output = tr.get("output", "")
            print(f"\n[TOOL:{tr['tool']}] ok={tr['ok']}")
            print(tr.get("output", "")[:400])
        elif t == "error":
            print(f"\n[ERROR] {event.get('message')}")
        elif t == "done":
            final_answer = event.get("answer", "")
            print(f"\n[DONE]")

    print("\n=== SUMMARY ===")
    print(f"Tools called: {[tc['tool'] for tc in tool_calls]}")
    print(f"Final answer (first 300 chars): {final_answer[:300]}")

    # Validate everything we expect from the hello-world scenario.
    ws = ROOT / "forge-workspace"
    target = ws / "hello_e2e.py"
    file_exists = target.exists()
    content_mentions = (
        file_exists and "Nexa E2E Hello" in target.read_text(encoding="utf-8")
    )
    run_ok = "Nexa E2E Hello" in tool_output
    answer_mentions = "Nexa E2E Hello" in final_answer

    print(f"file written?               {file_exists}")
    print(f"file content has marker?    {content_mentions}")
    print(f"terminal ran successfully?  {run_ok}")
    print(f"assistant mentions marker?  {answer_mentions}")

    all_pass = file_exists and content_mentions and run_ok and answer_mentions
    print(f"\nE2E RESULT: {'PASS' if all_pass else 'PARTIAL/FAIL'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
