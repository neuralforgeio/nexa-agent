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
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    """
    Entry point for running the server directly.

    Starts uvicorn on ``0.0.0.0:8000``.
    """
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
