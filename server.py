"""
Nexa Agent — WebSocket/SSE Server for Web UI Integration
========================================================

This module provides a FastAPI server that exposes the Nexa Agent to the
Next.js web frontend via SSE (Server-Sent Events) streaming. The server
runs on port 8000 and is accessed by the frontend through the Caddy
gateway proxy via ``?XTransformPort=8000``.

The web frontend (Next.js) stays **local only** — it is never pushed to
GitHub. Only the Python agent (including this server) is published. When
you test the web UI in the preview panel, you are testing the real Python
agent backend.

Endpoints:
    POST /api/chat/stream   — SSE streaming chat (main endpoint)
    POST /api/chat           — Persist a completed turn (action=persist)
    GET  /api/sessions       — List conversations
    GET  /api/sessions/{id}  — Get conversation messages
    POST /api/sessions       — Create a new conversation
    DELETE /api/sessions/{id} — Delete a conversation
    GET  /api/memory         — List memories
    GET  /api/health         — Health check

Run::
    python server.py
    # or: uvicorn server:app --host 0.0.0.0 --port 8000

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from nexa import bootstrap as nexa_bootstrap  # noqa: F401 — must be imported first for UTF-8 stdio.
from agent.self_health import SelfHealth
from nexa.config import NEXA_NAME, NEXA_VERSION
from nexa.provider_failover import is_failover_enabled
from run_agent import NexaAgent
from nexa.state import ConversationDB

# ---------------------------------------------------------------------------
# Singleton instances
# ---------------------------------------------------------------------------
_db: ConversationDB = ConversationDB()
_agent: NexaAgent = NexaAgent(db=_db)


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------
class ChatStreamRequest(BaseModel):
    """Request body for POST /api/chat/stream."""

    message: str
    sessionId: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = None


class PersistRequest(BaseModel):
    """Request body for POST /api/chat (action=persist)."""

    action: Optional[str] = None
    sessionId: Optional[str] = None
    userMessage: Optional[str] = None
    assistantAnswer: Optional[str] = None
    toolResults: Optional[List[Dict[str, str]]] = None


class CreateSessionRequest(BaseModel):
    """Request body for POST /api/sessions."""

    title: str = "new session"


# ---------------------------------------------------------------------------
# Lifespan (startup/shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler — initialize the database on startup.

    Args:
        app: The FastAPI application instance.
    """
    await _db.init()
    yield


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title=NEXA_NAME,
    version=NEXA_VERSION,
    description=f"{NEXA_NAME} — Python agent server for web UI integration.",
    lifespan=lifespan,
)

# Allow the Next.js frontend (port 3000) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health() -> Dict[str, Any]:
    """
    Health check endpoint.

    Returns:
        A dict with status, name, version, and tool count.
    """
    return {
        "status": "ok",
        "name": NEXA_NAME,
        "version": NEXA_VERSION,
        "tools": _agent.registry.list_names(),
        "model": _agent.provider.model,
        "base_url": _agent.provider.base_url,
    }


# ---------------------------------------------------------------------------
# SSE Streaming Chat
# ---------------------------------------------------------------------------
@app.post("/api/chat/stream")
async def chat_stream(req: ChatStreamRequest) -> StreamingResponse:
    """
    Stream a chat completion via Server-Sent Events.

    The response is ``text/event-stream`` with events matching the format
    the Next.js frontend expects::

        data: {"type":"session","sessionId":"...","isNew":true}
        data: {"type":"thinking"}
        data: {"type":"token","text":"..."}
        data: {"type":"tool_result","toolResult":{...}}
        data: {"type":"done","answer":"..."}
        data: {"type":"end"}

    Args:
        req: The :class:`ChatStreamRequest` body.

    Returns:
        A :class:`StreamingResponse` with SSE events.
    """
    message = req.message.strip()
    if not message:
        return JSONResponse({"error": "message is required"}, status_code=400)

    # Resolve or create conversation.
    conv_id = req.sessionId
    is_new = False
    if not conv_id:
        conv = await _db.create_conversation(title=message[:48])
        conv_id = conv["id"]
        is_new = True

    # Load history from DB if not provided.
    history = req.history or []
    if not history:
        db_msgs = await _db.get_messages(conv_id)
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in db_msgs
            if m["role"] != "system"
        ]

    async def event_generator():
        """Generate SSE events from the agent's streaming output."""
        encoder = json.dumps

        # Send session event first.
        yield f"data: {encoder({'type': 'session', 'sessionId': conv_id, 'isNew': is_new})}\n\n"

        # Stream agent events.
        async for event in _agent.run_streaming(message, conv_id, history):
            # Map Python agent events to frontend-expected format.
            ev_type = event.get("type")

            if ev_type == "thinking":
                yield f"data: {encoder({'type': 'thinking'})}\n\n"

            elif ev_type == "token":
                yield f"data: {encoder({'type': 'token', 'text': event['text']})}\n\n"

            elif ev_type == "tool_result":
                yield f"data: {encoder({'type': 'tool_result', 'toolResult': event['result']})}\n\n"

            elif ev_type == "compressing":
                yield f"data: {encoder({'type': 'compressing', 'detail': event.get('detail', '')})}\n\n"

            elif ev_type == "memory":
                yield f"data: {encoder({'type': 'memory', 'memories': event.get('memories', [])})}\n\n"

            elif ev_type == "done":
                yield f"data: {encoder({'type': 'done', 'answer': event['answer']})}\n\n"

            elif ev_type == "error":
                yield f"data: {encoder({'type': 'error', 'message': event['message']})}\n\n"

        # End event.
        yield f"data: {encoder({'type': 'end'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Persist endpoint (for non-streaming saves)
# ---------------------------------------------------------------------------
@app.post("/api/chat")
async def chat_persist(req: PersistRequest) -> JSONResponse:
    """
    Persist a completed chat turn without running the agent.

    Called by the frontend after a streaming turn completes, to ensure
    the conversation is saved even if the stream was interrupted.

    Args:
        req: The :class:`PersistRequest` body.

    Returns:
        A JSON response with the session ID.
    """
    if req.action != "persist":
        return JSONResponse({"error": "use /api/chat/stream for streaming"}, status_code=400)

    user_msg = (req.userMessage or "").strip()
    answer = req.assistantAnswer or ""
    tool_results = req.toolResults or []

    conv_id = req.sessionId
    if not conv_id:
        conv = await _db.create_conversation(title=user_msg[:48] or "new session")
        conv_id = conv["id"]

    if user_msg:
        await _db.add_message(conv_id, "user", user_msg)
    for tr in tool_results:
        await _db.add_message(conv_id, "tool", tr.get("output", ""), tr.get("tool"))
    if answer:
        await _db.add_message(conv_id, "assistant", answer)

    return JSONResponse({"ok": True, "sessionId": conv_id})


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------
@app.get("/api/sessions")
async def list_sessions() -> Dict[str, Any]:
    """List all conversations, newest first (camelCase for frontend compat)."""
    convs = await _db.list_conversations()
    result = []
    for c in convs:
        msgs = await _db.get_messages(c["id"])
        result.append({
            "id": c["id"],
            "title": c["title"],
            "createdAt": c["created_at"],
            "updatedAt": c["updated_at"],
            "messageCount": len(msgs),
        })
    return {"sessions": result}


@app.post("/api/sessions")
async def create_session(req: CreateSessionRequest) -> Dict[str, Any]:
    """Create a new conversation."""
    return await _db.create_conversation(title=req.title)


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str) -> Dict[str, Any]:
    """Get all messages for a conversation."""
    messages = await _db.get_messages(session_id)
    return {
        "session": {"id": session_id},
        "messages": [
            {
                "id": m["id"],
                "role": m["role"],
                "content": m["content"],
                "toolName": m.get("tool_name"),
                "createdAt": m["created_at"],
            }
            for m in messages
        ],
    }


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str) -> Dict[str, bool]:
    """Delete a conversation and all its messages."""
    await _db.delete_conversation(session_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Memory endpoints
# ---------------------------------------------------------------------------
@app.get("/api/memory")
async def list_memory() -> Dict[str, Any]:
    """List accumulated agent memories."""
    memories = await _db.list_memories(limit=100)
    return {
        "memories": [
            {
                "id": m["id"],
                "kind": m["kind"],
                "content": m["content"],
                "confidence": m["confidence"],
                "timesUsed": m["times_used"],
                "createdAt": m["created_at"],
            }
            for m in memories
        ]
    }


class MemoryRequest(BaseModel):
    """Request body for POST /api/memory."""

    kind: str = "note"
    content: str = ""


@app.post("/api/memory")
async def add_memory(req: MemoryRequest) -> Dict[str, Any]:
    """Add a new memory to the learning store."""
    if not req.content.strip():
        return JSONResponse({"error": "content is required"}, status_code=400)
    mem_id = await _db.add_memory(req.kind, req.content, source="user", confidence=0.8)
    return {"memory": {"id": mem_id, "kind": req.kind, "content": req.content}}


@app.delete("/api/memory")
async def delete_memory(id: str) -> Dict[str, bool]:
    """Delete a memory by ID."""
    await _db.delete_memory(id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Export endpoint
# ---------------------------------------------------------------------------
@app.get("/api/export/{session_id}")
async def export_session(session_id: str) -> JSONResponse:
    """Export a conversation as markdown."""
    messages = await _db.get_messages(session_id)
    lines = [f"# Nexa Agent Conversation", f"Session: {session_id}", ""]
    for m in messages:
        role = m["role"]
        content = m["content"]
        if role == "user":
            lines.append(f"## User\n\n{content}\n")
        elif role == "assistant":
            lines.append(f"## Nexa\n\n{content}\n")
        elif role == "tool":
            lines.append(f"<details><summary>Tool: {m.get('tool_name', '?')}</summary>\n\n```\n{content}\n```\n</details>\n")
    return JSONResponse({"markdown": "\n".join(lines)})


# ---------------------------------------------------------------------------
# Doctor (self-health) endpoint
# ---------------------------------------------------------------------------
@app.get("/api/doctor")
async def doctor() -> Dict[str, Any]:
    """Run self-health diagnostics and return the report."""
    health = SelfHealth(_db)
    report = await health.run_full_check()
    return {
        "all_healthy": report.all_healthy,
        "checks": [
            {"name": c.name, "healthy": c.healthy, "detail": c.detail}
            for c in report.checks
        ],
    }


# ---------------------------------------------------------------------------
# v2.0 Intelligence endpoints
# ---------------------------------------------------------------------------
@app.get("/api/intelligence")
async def intelligence() -> Dict[str, Any]:
    """
    Return a summary of every v2.0 intelligence subsystem.

    Aggregates: provider failover status, knowledge cache stats,
    self-improvement stats, healer stats, and error memory stats.
    """
    from agent.error_memory import ErrorMemory
    from agent.knowledge_cache import KnowledgeCache
    from agent.self_healer import SelfHealer
    from agent.self_improvement import SelfImprovementLoop

    healer = SelfHealer()
    loop = SelfImprovementLoop()
    cache = KnowledgeCache()
    err_mem = ErrorMemory()

    return {
        "version": "2.0.0",
        "failover_enabled": is_failover_enabled(),
        "knowledge_cache": {
            "count": len(cache.list_all()),
        },
        "self_improvement": loop.stats(),
        "healer": healer.stats(),
        "error_memory": err_mem.stats(),
    }


@app.get("/api/persona")
async def persona() -> Dict[str, Any]:
    """Return the current adaptive persona state (neutral default)."""
    from agent.adaptive_persona import AdaptivePersona
    p = AdaptivePersona().persona()
    return p.to_dict()


@app.get("/api/knowledge")
async def knowledge_list() -> Dict[str, Any]:
    """List all cached learned facts."""
    from agent.knowledge_cache import KnowledgeCache
    cache = KnowledgeCache()
    facts = cache.list_all()
    return {
        "count": len(facts),
        "facts": [
            {
                "entity": f.entity,
                "summary": f.summary,
                "source_url": f.source_url,
                "source_title": f.source_title,
                "confidence": f.confidence,
                "hits": f.hits,
                "learned_at": f.learned_at,
            }
            for f in facts
        ],
    }


@app.delete("/api/knowledge")
async def knowledge_clear() -> Dict[str, Any]:
    """Clear all cached learned facts."""
    from agent.knowledge_cache import KnowledgeCache
    cache = KnowledgeCache()
    n = cache.clear()
    return {"cleared": n}


@app.get("/api/patterns")
async def patterns() -> Dict[str, Any]:
    """Return recognized conversation patterns (empty until observed)."""
    from agent.pattern_recognizer import PatternRecognizer
    r = PatternRecognizer()
    return r.report().to_dict()


@app.post("/api/expand")
async def expand_prompt_endpoint(req: Dict[str, Any]) -> Dict[str, Any]:
    """
    Expand a terse user message into a structured prompt.

    Request body: ``{"message": "fix it"}``
    """
    from agent.prompt_expander import expand_prompt
    message = (req.get("message") or "").strip()
    if not message:
        return JSONResponse(
            status_code=400, content={"error": "message is required"}
        )
    result = expand_prompt(message)
    return result.to_dict()


@app.post("/api/intent")
async def intent_endpoint(req: Dict[str, Any]) -> Dict[str, Any]:
    """Classify the intent of a user message."""
    from agent.intent_classifier import classify_intent
    message = (req.get("message") or "").strip()
    if not message:
        return JSONResponse(
            status_code=400, content={"error": "message is required"}
        )
    return classify_intent(message).to_dict()


@app.post("/api/reformulate")
async def reformulate_endpoint(req: Dict[str, Any]) -> Dict[str, Any]:
    """Reformulate a vague user message into precise search queries."""
    from agent.query_reformulator import reformulate
    message = (req.get("message") or "").strip()
    if not message:
        return JSONResponse(
            status_code=400, content={"error": "message is required"}
        )
    return reformulate(message).to_dict()


# ---------------------------------------------------------------------------
# v3.0.0 — Provider management endpoints
# ---------------------------------------------------------------------------
@app.get("/api/provider")
async def provider_list() -> Dict[str, Any]:
    """List all providers and return the active one."""
    from nexa.provider_registry import ProviderRegistry
    reg = ProviderRegistry()
    all_providers = reg.list_all()
    active = reg.get_active()
    return {
        "active": active.name if active else None,
        "providers": [
            {
                "name": p.name,
                "base_url": p.base_url,
                "model": p.model,
                "api_key": p.api_key,  # already masked by list_all()
                "is_active": bool(active and active.name == p.name),
            }
            for p in all_providers
        ],
    }


@app.post("/api/provider")
async def provider_add(req: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add or update a provider, then optionally activate it.

    Body: ``{"name": "...", "base_url": "...", "api_key": "...", "model": "...", "activate": true}``
    """
    from nexa.provider_registry import ProviderRegistry, StoredProviderConfig
    reg = ProviderRegistry()
    name = (req.get("name") or "").strip()
    if not name:
        return JSONResponse(status_code=400, content={"error": "name is required"})
    base_url = (req.get("base_url") or "").strip()
    api_key = (req.get("api_key") or "").strip()
    model = (req.get("model") or "").strip()
    if not base_url:
        return JSONResponse(status_code=400, content={"error": "base_url is required"})
    cfg = StoredProviderConfig(
        name=name, base_url=base_url, api_key=api_key, model=model,
    )
    reg.add(name, cfg)
    activated = False
    if req.get("activate"):
        activated = reg.set_active(name)
        # Hot-swap the live agent's provider.
        if activated and _agent is not None:
            _agent.provider.base_url = cfg.base_url
            _agent.provider.api_key = cfg.api_key
            _agent.provider.model = cfg.model
            _agent.provider._client = None
    return {
        "ok": True,
        "name": name,
        "base_url": base_url,
        "model": model,
        "api_key_masked": cfg.masked_api_key(),
        "activated": activated,
    }


@app.delete("/api/provider")
async def provider_remove(req: Dict[str, Any]) -> Dict[str, Any]:
    """Remove a provider by name. Body: ``{"name": "..."}``."""
    from nexa.provider_registry import ProviderRegistry
    reg = ProviderRegistry()
    name = (req.get("name") or "").strip()
    if not name:
        return JSONResponse(status_code=400, content={"error": "name is required"})
    if reg.remove(name):
        return {"ok": True, "removed": name}
    return JSONResponse(status_code=404, content={"error": f"no such provider: {name}"})


@app.post("/api/provider/use")
async def provider_use(req: Dict[str, Any]) -> Dict[str, Any]:
    """Activate a provider by name. Body: ``{"name": "..."}``."""
    from nexa.provider_registry import ProviderRegistry
    reg = ProviderRegistry()
    name = (req.get("name") or "").strip()
    if not name:
        return JSONResponse(status_code=400, content={"error": "name is required"})
    if not reg.set_active(name):
        return JSONResponse(status_code=404, content={"error": f"no such provider: {name}"})
    cfg = reg.get_active()
    # Hot-swap the live agent's provider.
    if cfg is not None and _agent is not None:
        _agent.provider.base_url = cfg.base_url
        _agent.provider.api_key = cfg.api_key
        _agent.provider.model = cfg.model
        _agent.provider._client = None
    return {"ok": True, "active": name, "base_url": cfg.base_url if cfg else None}


@app.post("/api/provider/test")
async def provider_test(req: Dict[str, Any]) -> Dict[str, Any]:
    """Health-check a provider by name. Body: ``{"name": "..."}``."""
    from nexa.provider_registry import ProviderRegistry
    reg = ProviderRegistry()
    name = (req.get("name") or "").strip()
    if not name:
        return JSONResponse(status_code=400, content={"error": "name is required"})
    try:
        healthy = await reg.test(name)
    except Exception as exc:
        return {"ok": False, "name": name, "error": str(exc)}
    return {"ok": healthy, "name": name}


# ---------------------------------------------------------------------------
# v3.0.0 — WebSocket terminal endpoint
# ---------------------------------------------------------------------------
@app.websocket("/ws/terminal")
async def ws_terminal(websocket) -> None:
    """
    WebSocket endpoint for the Web UI terminal panel.

    Receives shell commands from the browser, executes them via
    ``run_terminal_command`` (with all v3.0.0 security boundaries:
    NEXA_WORKSPACE cwd + NEXA_HOME access blocked), and streams the
    output back as JSON messages.

    Message formats (server → client):
        ``{"type": "output", "text": "..."}`` — stdout/stderr chunk.
        ``{"type": "done", "exit_code": 0}`` — command finished.
        ``{"type": "error", "message": "..."}`` — blocked or failed.

    Message formats (client → server):
        ``{"type": "command", "command": "..."}`` — run a shell command.
        ``{"type": "ping"}`` — keepalive.
    """
    import json
    from tools.terminal_tool import run_terminal_command
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error", "message": "invalid JSON"
                }))
                continue
            mtype = msg.get("type")
            if mtype == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue
            if mtype != "command":
                await websocket.send_text(json.dumps({
                    "type": "error", "message": f"unknown type: {mtype}"
                }))
                continue
            command = (msg.get("command") or "").strip()
            if not command:
                await websocket.send_text(json.dumps({
                    "type": "error", "message": "empty command"
                }))
                continue
            try:
                result = await run_terminal_command(command, timeout=30.0)
                await websocket.send_text(json.dumps({
                    "type": "output", "text": result,
                }))
                await websocket.send_text(json.dumps({
                    "type": "done", "exit_code": 0,
                }))
            except ValueError as exc:
                # Blocked command (e.g. ~/.nexa access attempt).
                await websocket.send_text(json.dumps({
                    "type": "error", "message": str(exc),
                }))
            except Exception as exc:
                await websocket.send_text(json.dumps({
                    "type": "error", "message": f"execution failed: {exc}",
                }))
    except Exception:
        # Connection closed by client — exit gracefully.
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    """
    Entry point for running the server directly.

    Starts uvicorn on ``0.0.0.0:8000``.
    """
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
