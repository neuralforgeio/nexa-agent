"""
Skills — REAL-LLM end-to-end tests against a LIVE llama.cpp server (Ornith).

These exercise the full skill path — registry → input validation → handler →
provider.chat_stream → output validation — with a real local model instead of a
scripted provider. They are skipped unless ``NEXA_E2E_LLAMACPP=1`` is set and a
llama.cpp server is reachable on 127.0.0.1:8080.

Run explicitly:
    $env:NEXA_E2E_LLAMACPP="1"
    .venv\\Scripts\\python.exe -m pytest tests/test_skills_real_llm.py -v

Notes:
  * NO aggressive per-call network timeout — the local Q4_K_M model can be slow
    on older CPUs. A generous per-test wall clock (900 s) matches the existing
    test_llamacpp_real.py convention. Slow ≠ broken here.
  * Assertions are schema-level, not content-literal: the model must return an
    output that passes the manifest's output_schema. We do not demand exact
    wording from a nondeterministic model — that would be a dishonest test.
  * Workspace-pointing skills are given a real temp file; NEXA_WORKSPACE and
    tools._paths.NEXA_WORKSPACE are both repointed (captured at import time).
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import pytest

import skills
from skills import registry as R

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("NEXA_E2E_LLAMACPP", "0") not in ("1", "true", "yes"),
        reason="set NEXA_E2E_LLAMACPP=1 to run the live llama.cpp skill tests",
    ),
    pytest.mark.timeout(900),
]


def _reachable(host: str = "127.0.0.1", port: int = 8080, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _provider():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from nexa.provider import LLMProvider

    return LLMProvider(
        api_key="dummy",
        base_url=os.environ.get("NEXA_LLAMACPP_URL", "http://127.0.0.1:8080/v1"),
        model=os.environ.get("NEXA_MODEL", "Ornith-1.0-9b-Q4_K_M.gguf"),
    )


@pytest.fixture(scope="module")
def provider():
    if not _reachable():
        pytest.skip("llama.cpp server not reachable on 127.0.0.1:8080")
    return _provider()


CODE = '''def add(a, b):
    """Add two numbers."""
    return a + b


def div(a, b):
    # BUG: crashes when b is 0
    return a / b
'''


@pytest.fixture
def ws(tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text(CODE, encoding="utf-8")
    monkeypatch.setenv("NEXA_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tools._paths.NEXA_WORKSPACE", tmp_path)
    return tmp_path


async def _run(name: str, payload: dict, provider) -> dict:
    out = await skills.execute_skill(name, payload, provider)
    m = skills.get_skill(name).manifest
    errors = R.validate_schema(m.output_schema, out)
    assert errors == [], f"{name} output failed schema: {errors}\nout={out!r}"
    return out


# === code_intelligence (real LLM) ===========================================


@pytest.mark.asyncio
async def test_real_code_explanation(provider, ws):
    out = await _run(
        "code_explanation", {"file_path": "app.py", "detail_level": "brief"}, provider
    )
    assert isinstance(out["explanation"], str) and out["explanation"].strip()
    assert isinstance(out["flow_steps"], list)


@pytest.mark.asyncio
async def test_real_code_review(provider, ws):
    out = await _run("code_review", {"file_path": "app.py", "focus": "bugs"}, provider)
    assert isinstance(out["issues"], list)  # content is model-dependent
    assert isinstance(out["summary"], str)


@pytest.mark.asyncio
async def test_real_test_generation(provider, ws):
    out = await _run(
        "test_generation",
        {"file_path": "app.py", "function_name": "add", "framework": "pytest"},
        provider,
    )
    assert isinstance(out["test_code"], str) and out["test_code"].strip()
    assert 0 <= int(out["coverage_estimate"]) <= 100


@pytest.mark.asyncio
async def test_real_bug_diagnosis(provider):
    out = await _run(
        "bug_diagnosis",
        {"stack_trace": 'Traceback...\n  File "app.py", line 9, in div\nZeroDivisionError: division by zero'},
        provider,
    )
    assert isinstance(out["root_cause"], str) and out["root_cause"].strip()
    assert 0.0 <= float(out["confidence"]) <= 1.0


@pytest.mark.asyncio
async def test_real_documentation_generation(provider, ws):
    out = await _run(
        "documentation_generation", {"file_path": "app.py", "doc_type": "docstring"}, provider
    )
    assert isinstance(out["documentation"], str) and out["documentation"].strip()


# === web_research (real LLM) ================================================


@pytest.mark.asyncio
async def test_real_translation(provider):
    out = await _run(
        "translation", {"text": "Hello world", "from": "en", "to": "id"}, provider
    )
    assert isinstance(out["translated_text"], str)
    assert 0.0 <= float(out["confidence"]) <= 1.0


@pytest.mark.asyncio
async def test_real_summarization(provider):
    article = (
        "Nexa Agent is a local AI agent written in Python. It exposes tools for "
        "file and terminal operations and uses llama.cpp for local inference. "
        "The project keeps memory persistent and supports pluggable providers."
    )
    out = await _run(
        "summarization", {"content": article, "length": "brief", "style": "bullet"}, provider
    )
    assert isinstance(out["summary"], str) and out["summary"].strip()
    assert int(out["word_count"]) >= 0


@pytest.mark.asyncio
async def test_real_sentiment_analysis(provider):
    out = await _run(
        "sentiment_analysis",
        {"text": "I absolutely love this feature, it works beautifully!", "detail_level": "basic"},
        provider,
    )
    assert out["sentiment"] in ("positive", "negative", "neutral")
    assert 0.0 <= float(out["score"]) <= 1.0


# === communication (real LLM) ===============================================


@pytest.mark.asyncio
async def test_real_email_drafting(provider):
    out = await _run(
        "email_drafting",
        {
            "bullet_points": ["Project milestone reached", "Tests are green", "Thanks team"],
            "tone": "formal",
            "recipient": "team@example.com",
            "include_signature": False,
        },
        provider,
    )
    assert isinstance(out["email_body"], str) and out["email_body"].strip()


# === devops_operations (real LLM) ===========================================


@pytest.mark.asyncio
async def test_real_log_analysis(provider, ws):
    (ws / "app.log").write_text(
        "2026-08-03 12:00 INFO start\n"
        "2026-08-03 12:01 ERROR connect refused\n"
        "2026-08-03 12:01 ERROR connect refused\n"
        "2026-08-03 12:02 INFO recovered\n",
        encoding="utf-8",
    )
    out = await _run(
        "log_analysis",
        {"log_source": "app.log", "log_format": "generic", "analysis_type": "error"},
        provider,
    )
    assert isinstance(out.get("anomalies"), list)
