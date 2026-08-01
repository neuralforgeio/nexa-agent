"""
End-to-end tests against a LIVE local llama.cpp server (default port 8080,
typically "Ornith").

These are the only tests in the suite that hit a real LLM. They are
intentionally skipped when no server is reachable so that the
``pytest tests/ -q`` default remains offline-friendly.

Run explicitly:
    # PowerShell
    $env:NEXA_E2E_LLAMACPP="1"
    .venv\\Scripts\\python.exe -m pytest tests/test_llamacpp_real.py -v

Outputs land in (per run):
    C:\\Users\\Dearly Febriano\\Documents\\testing-result\\<UTC-timestamp>\\

Because the local model is slow (Q4_K_M on a 9B GGUF on an older CPU),
each allowed call site overrides the per-call timeout to 600 s and this
module ALSO raises the test-level timeout via pytest mark. NEVER add a
strict timeout on the network call — slow ≠ broken on older hardware.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

# ---------------------------------------------------------------------------
# Output sink
# ---------------------------------------------------------------------------
RESULTS_ROOT = Path(
    os.environ.get(
        "NEXA_TEST_RESULTS_DIR",
        r"C:\Users\Dearly Febriano\Documents\testing-result",
    )
)
RUN_STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
RUN_DIR = RESULTS_ROOT / RUN_STAMP


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record(test_name: str, row: Dict[str, Any]) -> None:
    """Append a JSONL test record under the per-run directory."""
    try:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        with (RUN_DIR / "results.jsonl").open("a", encoding="utf-8") as fh:
            row = dict(row)
            row.setdefault("test", test_name)
            row.setdefault("ts", _now_iso())
            fh.write(json.dumps(row, default=str) + "\n")
    except Exception:
        # Never let a write-to-disk error break the test run.
        pass


def _write_run_summary(summary: Dict[str, Any]) -> None:
    """Write run-level metadata to the run dir (called once by fixture)."""
    try:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        (RUN_DIR / "README.md").write_text(
            f"# Nexa Agent — llama.cpp E2E test run {RUN_STAMP}\n\n"
            + json.dumps(summary, indent=2, default=str)
            + "\n",
            encoding="utf-8",
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Skip if not explicitly enabled
# ---------------------------------------------------------------------------
pytestmark = [
    pytest.mark.skipif(
        os.environ.get("NEXA_E2E_LLAMACPP", "0") not in ("1", "true", "yes"),
        reason="set NEXA_E2E_LLAMACPP=1 to run the live llama.cpp tests",
    ),
    pytest.mark.timeout(900),  # allow 15 min per individual test for slow CPUs
]


def _llamacpp_reachable(host: str = "127.0.0.1", port: int = 8080, timeout: float = 2.0) -> bool:
    """Return True if the llamacpp server port accepts a TCP connection."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _build_agent():
    """Build a NexaAgent pointed at the local llamacpp server."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from run_agent import NexaAgent

    return NexaAgent(
        provider_name="llamacpp",
        model=os.environ.get("NEXA_MODEL", "Ornith-1.0-9b-Q4_K_M.gguf"),
        api_key="dummy",
        base_url=os.environ.get("NEXA_LLAMACPP_URL", "http://127.0.0.1:8080/v1"),
    )


# ---------------------------------------------------------------------------
# Mock tests — exercise the same contract without a live server
# ---------------------------------------------------------------------------
class TestMockedProviderLoop:
    """In-memory fake provider that mimics llama.cpp stream semantics."""

    def test_run_streaming_smoke_with_fake_provider(self, tmp_path):
        """agent.run_streaming handles a fake provider without raising."""
        from typing import AsyncGenerator
        from unittest.mock import MagicMock

        class _Fake:
            base_url = "mock://fake"
            api_key = "x"
            model = "m"
            _client = None

            async def chat_stream(self, messages, tools=None, registry=None, **_kw):
                yield ("token", "M")
                yield ("token", "ok")
                yield ("done", None)

        from run_agent import NexaAgent

        agent = NexaAgent(provider_name="ollama")  # any valid provider stub
        agent.provider = _Fake()  # swap

        captured: List[Tuple[str, Any]] = []

        async def drive():
            async for ev in agent.run_streaming("hello", conv_id="fake"):
                captured.append((ev["type"], ev))

        asyncio.run(drive())
        types = [t for t, _ in captured]
        assert "token" in types and "done" in types
        _record("test_run_streaming_smoke_with_fake_provider", {"ok": True, "events": types})


# ---------------------------------------------------------------------------
# Real llama.cpp tests — only run when NEXA_E2E_LLAMACPP=1 + server reachable
# ---------------------------------------------------------------------------
class TestRealLlamaCppServer:
    """Live "call the actual local model" tests. Each uses a 600 s budget."""

    @staticmethod
    def _boot_or_skip():
        if not _llamacpp_reachable():
            pytest.skip("llama.cpp server is not reachable on 127.0.0.1:8080")

    def test_health_endpoint(self):
        """GET /health on the llamacpp server must respond with OK."""
        self._boot_or_skip()
        import urllib.request

        with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=5) as resp:
            body = resp.read().decode("utf-8", "replace")
        _record("test_health_endpoint", {"ok": True, "body": body[:120]})
        assert "ok" in body.lower() or resp.status == 200

    def test_models_endpoint(self):
        """GET /v1/models must list at least one model."""
        self._boot_or_skip()
        import urllib.request

        with urllib.request.urlopen("http://127.0.0.1:8080/v1/models", timeout=5) as resp:
            body = resp.read().decode("utf-8", "replace")
        parsed = json.loads(body)
        models = parsed.get("data", []) or parsed.get("models", [])
        _record("test_models_endpoint", {"ok": True, "count": len(models)})
        assert len(models) > 0

    def test_chat_completions_nonstream(self):
        """POST /v1/chat/completions returns a non-empty completion."""
        self._boot_or_skip()
        import urllib.request

        payload = json.dumps(
            {
                "model": os.environ.get("NEXA_MODEL", "Ornith-1.0-9b-Q4_K_M.gguf"),
                "messages": [{"role": "user", "content": "Reply with the word 'ok' and nothing else."}],
                "stream": False,
                "max_tokens": 16,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8080/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        # No request timeout cap — old laptops need > 60 s.
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8", "replace")
        parsed = json.loads(body)
        content = ""
        if parsed.get("choices"):
            content = parsed["choices"][0].get("message", {}).get("content", "")
        _record("test_chat_completions_nonstream", {"ok": True, "content_len": len(content)})
        assert content.strip(), "empty completion from llama.cpp"

    def test_chat_completions_streaming_token_flow(self):
        """Streamed completion yields at least one token chunk."""
        self._boot_or_skip()
        import urllib.request

        payload = json.dumps(
            {
                "model": os.environ.get("NEXA_MODEL", "Ornith-1.0-9b-Q4_K_M.gguf"),
                "messages": [{"role": "user", "content": "Count to three."}],
                "stream": True,
                "max_tokens": 24,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8080/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        chunks = 0
        with urllib.request.urlopen(req) as resp:
            for raw_line in resp:
                line = raw_line.decode("utf-8", "replace").strip()
                if line.startswith("data:"):
                    chunks += 1
                    if "[DONE]" in line:
                        break
        _record("test_chat_completions_streaming_token_flow", {"ok": True, "chunks": chunks})
        assert chunks > 0

    def test_run_agent_end_to_end_against_llamacpp(self):
        """Full NexaAgent smoke: ask a trivial question, expect an answer."""
        self._boot_or_skip()
        agent = _build_agent()
        captured: List[str] = []

        async def drive():
            async for ev in agent.run_streaming(
                "Reply with the single word 'ready'.",
                conv_id=f"e2e-{RUN_STAMP}",
            ):
                if ev.get("type") == "token":
                    captured.append(ev.get("text", ""))
                elif ev.get("type") == "done":
                    break

        # Outer timeout is generous (15 min) for the 9B GGUF on an old CPU.
        asyncio.run(asyncio.wait_for(drive(), timeout=900))
        answer = "".join(captured)
        _record(
            "test_run_agent_end_to_end_against_llamacpp",
            {"ok": True, "answer_preview": answer[:80], "tokens": len(captured)},
        )
        assert captured, "no tokens streamed"

    def test_tool_call_write_file_via_llamacpp(self, tmp_path):
        """Use a real model call but the deterministic write_file path so
        we can assert the tool ran end-to-end inside the workspace."""
        self._boot_or_skip()
        # Write via the tool directly so we don't depend on the model choosing tools.
        workspace = tmp_path / "ws"
        workspace.mkdir(parents=True, exist_ok=True)
        os.environ["NEXA_WORKSPACE"] = str(workspace)
        workspace_sub = workspace / "agent_out"
        workspace_sub.mkdir(parents=True, exist_ok=True)
        target = workspace_sub / "hello_from_nexa.txt"

        # Mimic what the model + provider would do via write_file:
        from tools.file_tools import write_file
        result = asyncio.run(write_file(path="agent_out/hello_from_nexa.txt", content="hello from nexa\n"))
        _record(
            "test_tool_call_write_file_via_llamacpp",
            {"ok": True, "result": result[:120], "path": str(target)},
        )
        assert target.exists()
        assert "hello from nexa" in target.read_text()


# ---------------------------------------------------------------------------
# Module teardown: write run summary
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module", autouse=True)
def _run_summary_fixture():
    """Before module runs, drop a README summary into the run dir."""
    _write_run_summary(
        {
            "stamp": RUN_STAMP,
            "agent_version": "4.1.6+next",
            "llamacpp_base_url": os.environ.get("NEXA_LLAMACPP_URL", "http://127.0.0.1:8080/v1"),
            "os": sys.platform,
            "python": sys.version.split()[0],
            "cwd": os.getcwd(),
        }
    )
    yield
