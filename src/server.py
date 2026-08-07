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
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from nexa import bootstrap as nexa_bootstrap  # noqa: F401 — must be imported first for UTF-8 stdio.
from agent.core.self_health import SelfHealth
from nexa.config import NEXA_NAME, NEXA_VERSION
from nexa.provider_failover import is_failover_enabled
from src.run_agent import NexaAgent
from nexa.state import ConversationDB


# ---------------------------------------------------------------------------
# v4.1.0 Security — API token auth + CORS restriction
# ---------------------------------------------------------------------------
def _generate_api_token() -> str:
    """Return (and print) the API token, generating a random one if unset."""
    token = os.environ.get("NEXA_API_TOKEN", "").strip()
    if not token:
        token = secrets.token_urlsafe(32)
        # Print once at startup so the operator can store it in the frontend.
        print(f"\n[{NEXA_NAME}] NEXA_API_TOKEN not set — generated one:")
        print(f"[{NEXA_NAME}]   {token}\n", flush=True)
    return token


#: Resolved once at import time so all requests share the same token.
_API_TOKEN = _generate_api_token()

#: Auth gate toggle. Defaults OFF for backwards-compatible local usage;
#: set NEXA_REQUIRE_AUTH=1 in production/exposed deployments to enforce
#: Bearer-token auth on every /api/* route and the /ws/terminal socket.
_REQUIRE_AUTH = os.environ.get("NEXA_REQUIRE_AUTH", "0").lower() in (
    "1", "true", "yes",
)


def _allowed_origins() -> List[str]:
    """Return the CORS allow-list, overridable via NEXA_ALLOWED_ORIGINS."""
    raw = os.environ.get("NEXA_ALLOWED_ORIGINS", "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return ["http://localhost:3000", "http://127.0.0.1:3000"]


def _unauthorized(detail: str = "unauthorized") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": detail},
    )


async def verify_token(authorization: Optional[str] = Header(None)) -> None:
    """
    FastAPI dependency: require ``Authorization: Bearer <token>``.

    No-op when :data:`_REQUIRE_AUTH` is ``False`` (default), so local
    single-user setups keep working without a token. Set
    ``NEXA_REQUIRE_AUTH=1`` to enforce.

    Raises:
        HTTPException: 401 JSON ``{"error": "unauthorized"}`` on mismatch.
    """
    if not _REQUIRE_AUTH:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise _unauthorized()
    if authorization[7:].strip() != _API_TOKEN:
        raise _unauthorized()


def verify_token_ws(token: Optional[str]) -> None:
    """Validate the WebSocket ``?token=`` query param (raise on mismatch)."""
    if not _REQUIRE_AUTH:
        return
    if (token or "").strip() != _API_TOKEN:
        raise _unauthorized()

# ---------------------------------------------------------------------------
# Singleton instances
# ---------------------------------------------------------------------------
from src.run_agent import set_active_agent  # for the delegate tool

_db: ConversationDB = ConversationDB()
_agent: NexaAgent = NexaAgent(db=_db)
# Register the singleton as the active agent so tools like ``delegate`` and
# ``terminal_exec`` can find the running instance at runtime.
set_active_agent(_agent)


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

# B-06: per-IP rate limiting. slowapi is an optional dependency — when it is
# absent the server still runs with a no-op decorator so tests stay green.
try:
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    _limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
    app.state.limiter = _limiter

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            {"error": "rate limit exceeded"}, status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )

    _SLOWAPI = True
except Exception:  # pragma: no cover - slowapi missing
    _SLOWAPI = False

    class _NoLimiter:
        def limit(self, _rule: str):
            def _wrap(fn):
                return fn
            return _wrap

    _limiter = _NoLimiter()  # type: ignore[assignment]

# Allow only the Next.js frontend (port 3000) by default (v4.1.0).
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_gate(request: Request, call_next):
    """
    Bearer-token gate for every ``/api/*`` route.

    Active only when :data:`_REQUIRE_AUTH` is true (``NEXA_REQUIRE_AUTH=1``).
    The health endpoint stays open so load balancers / uptime checks still
    work; everything else returns ``401 {"error": "unauthorized"}``.
    """
    if _REQUIRE_AUTH and request.url.path.startswith("/api/"):
        if request.url.path != "/api/health":
            auth = request.headers.get("authorization") or ""
            if not auth.startswith("Bearer ") or auth[7:].strip() != _API_TOKEN:
                return JSONResponse(
                    {"error": "unauthorized"}, status_code=status.HTTP_401_UNAUTHORIZED
                )
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Attach CSP to every response (v4.1.0 iframe-sandbox hardening)."""
    response = await call_next(request)
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self' 'unsafe-inline'; connect-src 'self' ws: wss:",
    )
    return response


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
# B-05: maximum accepted user message length (chars). Over → 400.
_MAX_MESSAGE_CHARS = 10_240


@app.post("/api/chat/stream")
@_limiter.limit("60/minute")
async def chat_stream(request: Request, req: ChatStreamRequest) -> StreamingResponse:
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
    # B-05: reject oversized input before any work is done.
    if len(message) > _MAX_MESSAGE_CHARS:
        return JSONResponse(
            {"error": f"message too long (max {_MAX_MESSAGE_CHARS} chars)"},
            status_code=400,
        )

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
        """
        Generate SSE events from the agent's streaming output, with keepalive.

        v4.1.0: emits a ``: ping`` comment every 15 s of inactivity so that
        (a) browsers don't close the connection during a long llamacpp
        prompt-processing phase, and (b) llama-server doesn't interpret a
        silent socket as a stalled client. This directly fixes the
        "auto-close" the user saw (llama-server log: ``stop: cancel task``).
        """
        encoder = json.dumps

        # Send session event first.
        yield f"data: {encoder({'type': 'session', 'sessionId': conv_id, 'isNew': is_new})}\n\n"

        # v4.1.0: announce which virtual-agent persona is driving this turn
        # (Planner/Explorer/Coder/Reviewer) so the UI can render the badge
        # above the reasoning bubble. Only emitted when the orchestrator
        # protocol is activated via NEXA_ORCHESTRATOR=1.
        import os as _os_orch
        if _agent.persona_manager is not None and _os_orch.environ.get(
            "NEXA_ORCHESTRATOR", "0"
        ).lower() in ("1", "true", "yes"):
            try:
                badge = _agent.persona_manager.badge()
                yield f"data: {encoder({'type': 'agent_persona', 'persona': badge})}\n\n"
            except Exception:
                pass

        # Wrap the agent generator so we can interleave keepalive pings.
        agent_gen = _agent.run_streaming(message, conv_id, history)
        pending: Optional[asyncio.Task] = None
        try:
            pending = asyncio.ensure_future(agent_gen.__anext__())

            # B-03: hard wall-clock ceiling for the entire agent stream.
            # If a single turn takes > 60 s of *processing* we abandon it and
            # surface an explicit error event instead of hanging the browser.
            async def _stream_loop():
                nonlocal pending
                while True:
                    done, _ = await asyncio.wait({pending}, timeout=15.0)
                    if not done:
                        # 15s with no agent event — keepalive ping.
                        yield ": ping\n\n"
                        continue
                    try:
                        event = pending.result()
                    except StopAsyncIteration:
                        return
                    finally:
                        pending = None

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
                    elif ev_type == "patterns":
                        yield f"data: {encoder({'type': 'patterns', 'detail': event.get('detail', '')})}\n\n"
                    elif ev_type == "heal":
                        yield f"data: {encoder({'type': 'heal', 'plan': event.get('plan', {})})}\n\n"
                    elif ev_type == "failover":
                        yield f"data: {encoder({'type': 'failover', 'from': event.get('from'), 'to': event.get('to'), 'reason': event.get('reason', '')})}\n\n"
                    elif ev_type == "expand":
                        yield f"data: {encoder({'type': 'expand', 'expanded': event.get('expanded', '')})}\n\n"
                    elif ev_type == "intent":
                        yield f"data: {encoder({'type': 'intent', 'intent': event.get('intent', {})})}\n\n"
                    elif ev_type == "confidence":
                        yield f"data: {encoder({'type': 'confidence', 'score': event.get('score'), 'should_enrich': event.get('should_enrich', False)})}\n\n"
                    elif ev_type == "reflection":
                        yield f"data: {encoder({'type': 'reflection', 'summary': event.get('summary', '')})}\n\n"
                    elif ev_type == "suggestions":
                        yield f"data: {encoder({'type': 'suggestions', 'items': event.get('items', [])})}\n\n"
                    elif ev_type == "autolearn":
                        yield f"data: {encoder({'type': 'autolearn', 'query': event.get('query', ''), 'fact': event.get('fact')})}\n\n"
                    elif ev_type == "done":
                        yield f"data: {encoder({'type': 'done', 'answer': event['answer']})}\n\n"
                    elif ev_type == "error":
                        yield f"data: {encoder({'type': 'error', 'message': event['message']})}\n\n"

                    pending = asyncio.ensure_future(agent_gen.__anext__())

            try:
                async with asyncio.timeout(60.0):
                    async for chunk in _stream_loop():
                        yield chunk
            except (asyncio.TimeoutError, TimeoutError):
                yield f"data: {encoder({'type': 'error', 'message': 'response timed out after 60s'})}\n\n"
        finally:
            if pending is not None and not pending.done():
                pending.cancel()
            aclose = getattr(agent_gen, "aclose", None)
            if aclose is not None:
                try:
                    await aclose()
                except Exception:
                    pass

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
async def list_sessions(q: str = "", includeArchived: bool = False) -> Dict[str, Any]:
    """
    List conversations, pinned-first then newest (camelCase for frontend).

    F-03: ``q`` filters title + message content. F-04: archived conversations
    are hidden unless ``includeArchived=true``.
    """
    convs = await _db.list_conversations(query=q, include_archived=includeArchived)
    result = []
    for c in convs:
        msgs = await _db.get_messages(c["id"])
        result.append({
            "id": c["id"],
            "title": c["title"],
            "createdAt": c["created_at"],
            "updatedAt": c["updated_at"],
            "messageCount": len(msgs),
            "pinned": bool(c.get("pinned")),
            "archived": bool(c.get("archived")),
        })
    return {"sessions": result}


@app.post("/api/sessions")
async def create_session(req: CreateSessionRequest) -> Dict[str, Any]:
    """Create a new conversation."""
    return await _db.create_conversation(title=req.title)


async def _session_exists(session_id: str) -> bool:
    """True when the conversation id exists (B-01: so endpoints can 404)."""
    convs = await _db.list_conversations(limit=10000)
    return any(c["id"] == session_id for c in convs)


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str) -> Dict[str, Any]:
    """Get all messages for a conversation. B-01: 404 when missing."""
    if not await _session_exists(session_id):
        return JSONResponse({"error": f"no such session: {session_id}"}, status_code=404)
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
    """Delete a conversation and all its messages. B-01: 404 when missing."""
    if not await _session_exists(session_id):
        return JSONResponse({"error": f"no such session: {session_id}"}, status_code=404)
    await _db.delete_conversation(session_id)
    return {"ok": True}


class RenameSessionRequest(BaseModel):
    """Request body for PATCH /api/sessions/{id}."""

    title: Optional[str] = None
    pinned: Optional[bool] = None
    archived: Optional[bool] = None


@app.patch("/api/sessions/{session_id}")
async def rename_session(session_id: str, req: RenameSessionRequest) -> Dict[str, Any]:
    """
    Update a conversation.

    F-03/F-04: supports renaming plus the pinned/archived flags. At least one
    field must be provided; returns 404 when the session does not exist.
    """
    did_anything = False

    if req.title is not None:
        title = req.title.strip()
        if not title:
            return JSONResponse({"error": "title is required"}, status_code=400)
        ok = await _db.rename_conversation(session_id, title)
        if not ok:
            return JSONResponse({"error": "session not found"}, status_code=404)
        did_anything = True

    if req.pinned is not None or req.archived is not None:
        ok = await _db.set_conversation_flags(
            session_id, pinned=req.pinned, archived=req.archived
        )
        if not ok:
            return JSONResponse({"error": "session not found"}, status_code=404)
        did_anything = True

    if not did_anything:
        return JSONResponse({"error": "nothing to update"}, status_code=400)
    return {"ok": True, "id": session_id}


class BranchSessionRequest(BaseModel):
    """Request body for POST /api/sessions/branch."""

    sessionId: str
    messageId: str


@app.post("/api/sessions/branch")
async def branch_session(req: BranchSessionRequest) -> Dict[str, Any]:
    """
    Fork a conversation at ``messageId`` into a new session.

    v4.6.5 (F-02): used by the "Branch" action on any message bubble. The
    new session contains the source conversation's history up to and
    including the given message.
    """
    result = await _db.branch_conversation(req.sessionId, req.messageId)
    if result is None:
        return JSONResponse({"error": "session or message not found"}, status_code=404)
    return {"ok": True, "id": result["id"], "title": result["title"]}


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
    """Delete a memory by ID. B-01: 404 when the id does not exist."""
    removed = await _db.delete_memory(id)
    if not removed:
        return JSONResponse({"error": f"no such memory: {id}"}, status_code=404)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Export endpoint
# ---------------------------------------------------------------------------
@app.get("/api/export/{session_id}")
async def export_session(session_id: str, format: str = "md") -> JSONResponse:
    """
    Export a conversation as Markdown (default) or JSON.

    B-01: returns 404 when the session does not exist.
    B-02: tool blocks (rendered as raw HTML <details>) have their content
    HTML-escaped so a stored payload cannot execute when the exported
    Markdown is opened in a browser.
    """
    import html as _html

    convs = await _db.list_conversations(limit=10000)
    if not any(c["id"] == session_id for c in convs):
        return JSONResponse({"error": f"no such session: {session_id}"}, status_code=404)

    messages = await _db.get_messages(session_id)

    if format.lower() in ("json", "js"):
        return JSONResponse({
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
        })

    lines = [f"# Nexa Agent Conversation", f"Session: {session_id}", ""]
    for m in messages:
        role = m["role"]
        content = m["content"]
        if role == "user":
            lines.append(f"## User\n\n{content}\n")
        elif role == "assistant":
            lines.append(f"## Nexa\n\n{content}\n")
        elif role == "tool":
            # B-02: the <details> block is raw HTML inside the Markdown, so
            # escape its contents to prevent stored-XSS on export.
            tool_name = _html.escape(str(m.get("tool_name", "?")), quote=True)
            safe_content = _html.escape(content)
            lines.append(
                f"<details><summary>Tool: {tool_name}</summary>\n\n````\n{safe_content}\n````\n</details>\n"
            )
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
    from agent.error.error_memory import ErrorMemory
    from agent.memory.knowledge_cache import KnowledgeCache
    from agent.error.self_healer import SelfHealer
    from agent.learning.self_improvement import SelfImprovementLoop

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
    from agent.persona.adaptive_persona import AdaptivePersona
    p = AdaptivePersona().persona()
    return p.to_dict()


@app.get("/api/orchestrator")
async def orchestrator_state() -> Dict[str, Any]:
    """
    Return the virtual multi-agent orchestrator state (v4.1.0).

    Includes the active phase, persona badge, review-loop counter, and the
    timestamped transition history — so the Web UI's "Work Process" dropdown
    can render ``[10:00:01] PLANNING → CODING ...`` lines.
    """
    if _agent.orchestrator is None or _agent.persona_manager is None:
        return {"enabled": False}
    st = _agent.orchestrator.state
    return {
        "enabled": True,
        "phase": st.phase.value,
        "round_count": st.round_count,
        "persona": _agent.persona_manager.badge(),
        "history": st.history[-25:],
    }


@app.get("/api/knowledge")
async def knowledge_list() -> Dict[str, Any]:
    """List all cached learned facts."""
    from agent.memory.knowledge_cache import KnowledgeCache
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
    from agent.memory.knowledge_cache import KnowledgeCache
    cache = KnowledgeCache()
    n = cache.clear()
    return {"cleared": n}


@app.get("/api/patterns")
async def patterns() -> Dict[str, Any]:
    """Return recognized conversation patterns (empty until observed)."""
    from agent.understanding.pattern_recognizer import PatternRecognizer
    r = PatternRecognizer()
    return r.report().to_dict()


@app.post("/api/expand")
async def expand_prompt_endpoint(req: Dict[str, Any]) -> Dict[str, Any]:
    """
    Expand a terse user message into a structured prompt.

    Request body: ``{"message": "fix it"}``
    """
    from agent.prompt.prompt_expander import expand_prompt
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
    from agent.understanding.intent_classifier import classify_intent
    message = (req.get("message") or "").strip()
    if not message:
        return JSONResponse(
            status_code=400, content={"error": "message is required"}
        )
    return classify_intent(message).to_dict()


@app.post("/api/reformulate")
async def reformulate_endpoint(req: Dict[str, Any]) -> Dict[str, Any]:
    """Reformulate a vague user message into precise search queries."""
    from agent.understanding.query_reformulator import reformulate
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
    """
    Activate a provider by name. Body: ``{"name": "..."}``.

    B-04: pre-flight health check first — if the target provider fails its
    connection test, the request is rejected (HTTP 400) and the previously
    active provider is left untouched (no blind hot-swap).
    """
    from nexa.provider_registry import ProviderRegistry
    reg = ProviderRegistry()
    name = (req.get("name") or "").strip()
    if not name:
        return JSONResponse(status_code=400, content={"error": "name is required"})

    if name not in [p.name for p in reg.list_all()]:
        return JSONResponse(status_code=404, content={"error": f"no such provider: {name}"})

    # B-04: pre-flight — refuse to activate a provider that doesn't respond.
    try:
        healthy = await reg.test(name)
    except Exception:
        healthy = False
    if not healthy:
        return JSONResponse(
            status_code=400,
            content={"error": f"provider '{name}' failed its connection test; activation refused"},
        )

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
# v3.2.0 — WebSocket terminal endpoint (real PTY for xterm.js)
# ---------------------------------------------------------------------------
import sys as _sys

@app.websocket("/ws/terminal")
async def ws_terminal(websocket) -> None:
    """
    WebSocket endpoint for the Web UI terminal panel (xterm.js).

    Provides a real PTY (pseudo-terminal) so the browser can run a real
    shell with full color support, escape sequences, and stdin interaction.
    Falls back to command-based execution if PTY deps are unavailable.

    All commands still go through the v3.0.0 security boundary
    (~/.nexa/ access blocked). The ``cwd`` is always ``NEXA_WORKSPACE``.

    Message formats (server → client):
        ``{"type": "output", "data": "..."}`` — raw PTY output (ANSI included).
        ``{"type": "error", "message": "..."}`` — blocked or merged error.
    Message formats (client → server):
        ``{"type": "input", "data": "..."}`` — stdin bytes to shell.
        ``{"type": "resize", "cols": N, "rows": M}`` — resize the PTY.
        ``{"type": "ping"}`` — keepalive.
    """
    import asyncio
    import json

    from nexa.config import NEXA_WORKSPACE

    # v4.1.0: validate token BEFORE accepting the socket (raise on failure).
    try:
        verify_token_ws(websocket.query_params.get("token"))
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    # v4.1.0: PTY mode is opt-in via NEXA_ENABLE_PTY=1 (default off —
    # command-mode fallback has the v3.0.0 blocklist already). When PTY is
    # enabled we scrub the environment and pin cwd so the shell cannot leak
    # ``*_API_KEY`` / ``*_TOKEN`` secrets or escape the workspace.
    pty_enabled = os.environ.get("NEXA_ENABLE_PTY", "0").lower() in ("1", "true", "yes")
    pty = None
    if pty_enabled:
        print(
            f"[{NEXA_NAME}] WARNING: PTY terminal mode ENABLED (NEXA_ENABLE_PTY=1) "
            "— command blocklist bypassed; env secrets scrubbed.",
            flush=True,
        )

        def _scrub_env() -> Dict[str, str]:
            """Return a whitelisted env for the spawned shell.

            Removes every ``*_API_KEY`` / ``*_TOKEN`` / ``*_SECRET`` variable
            and pins HOME to the workspace so the shell starts sandboxed.
            """
            import os as _os
            allowed = {
                "PATH", "LANG", "LC_ALL", "TERM", "SHELL", "USER",
                "TMPDIR", "TMP", "TEMP", "SYSTEMROOT", "WINDIR",
                "COMSPEC", "PATHEXT", "OS", "NUMBER_OF_PROCESSORS",
            }
            env = {
                k: v for k, v in _os.environ.items()
                if k.upper() in allowed
                and not k.upper().endswith(("_API_KEY", "_TOKEN", "_SECRET"))
            }
            env["HOME"] = str(NEXA_WORKSPACE)
            env["NEXA_SANDBOXED"] = "1"
            return env

        if _sys.platform == "win32":
            try:
                from winpty import PtyProcess  # type: ignore[import-not-found]
                pty = PtyProcess.spawn(
                    ["cmd.exe", "/k"],
                    cwd=str(NEXA_WORKSPACE),
                    dimensions=(24, 80),
                    env=_scrub_env(),
                )
            except Exception:
                pty = None
        else:
            try:
                import ptyprocess
                pty = ptyprocess.PtyProcess.spawn(
                    ["/bin/bash"],
                    cwd=str(NEXA_WORKSPACE),
                    dimensions=(24, 80),
                    env=_scrub_env(),
                )
            except Exception:
                pty = None

    if pty is None:
        # No PTY (or disabled via NEXA_ENABLE_PTY=0) — command-based fallback.
        reason = "disabled (NEXA_ENABLE_PTY=0)" if not pty_enabled else "not available on this system"
        await websocket.send_text(json.dumps({
            "type": "output",
            "data": f"PTY {reason}. Using guarded command mode.\r\n$ ",
        }))
        await _ws_terminal_command_mode(websocket)
        return

    # Real PTY: spawn reader/writer tasks.
    async def pty_to_ws() -> None:
        """Forward PTY output to WebSocket."""
        try:
            while pty.isalive():
                data = pty.read()
                if not data:
                    break
                await websocket.send_text(json.dumps({"type": "output", "data": data}))
        except Exception:
            pass
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    async def ws_to_pty() -> None:
        """Forward WebSocket input to PTY."""
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                mtype = msg.get("type")
                if mtype == "ping":
                    continue
                elif mtype == "input":
                    data = msg.get("data", "")
                    try:
                        pty.write(data)
                    except Exception:
                        break
                elif mtype == "resize":
                    try:
                        pty.setwinsize(msg.get("rows", 24), msg.get("cols", 80))
                    except Exception:
                        pass
        except Exception:
            pass

    try:
        await asyncio.gather(pty_to_ws(), ws_to_pty())
    finally:
        try:
            if pty.isalive():
                pty.terminate(force=True)
        except Exception:
            pass


async def _ws_terminal_command_mode(websocket) -> None:
    """
    Fallback terminal mode (no PTY) — executes commands via run_terminal_command.
    """
    import json
    from tools.terminal_tool import run_terminal_command
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("type") == "ping":
                continue
            if msg.get("type") != "input":
                continue
            cmd = (msg.get("data") or "").strip()
            if not cmd:
                continue
            if cmd == "exit":
                await websocket.send_text(json.dumps({"type": "output", "data": "exit\r\n"}))
                break
            try:
                result = await run_terminal_command(cmd, timeout=30.0)
                await websocket.send_text(json.dumps({"type": "output", "data": result + "\r\n$ "}))
            except ValueError as exc:
                await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
            except Exception as exc:
                await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# B-07 — usage / cost tracking
# ---------------------------------------------------------------------------
@app.get("/api/usage")
async def api_usage(session: Optional[str] = None, days: int = 7) -> Dict[str, Any]:
    """Aggregate token usage (messages.token_count) per day and per session."""
    stats = await _db.usage_stats(session_id=session, days=days)
    return {"ok": True, **stats}


# ---------------------------------------------------------------------------
# B-08 — orchestrator live SSE stream
# ---------------------------------------------------------------------------
@app.get("/api/orchestrator/stream")
async def orchestrator_stream() -> StreamingResponse:
    """
    Stream orchestrator phase/persona transitions as SSE until the client
    disconnects. Emits a snapshot immediately, then polls for changes.
    """
    async def gen():
        last = None
        try:
            while True:
                enabled = _agent is not None and getattr(_agent, "orchestrator", None) is not None
                if enabled:
                    st = _agent.orchestrator.state
                    payload = {
                        "type": "state",
                        "phase": st.phase.value,
                        "round_count": st.round_count,
                        "persona": _agent.persona_manager.badge() if _agent.persona_manager else None,
                    }
                else:
                    payload = {"type": "state", "enabled": False}
                if payload != last:
                    last = payload
                    yield f"data: {json.dumps(payload)}\n\n"
                if await _is_disconnected():
                    break
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass

    async def _is_disconnected():
        return False

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "Connection": "keep-alive"},
    )


# ---------------------------------------------------------------------------
# v4.1.0 — Sandbox endpoints (Web Preview + Terminal sidebar)
# ---------------------------------------------------------------------------
from pathlib import Path as _Path

from fastapi.responses import HTMLResponse as _HTMLResponse

from nexa.config import NEXA_WORKSPACE as _WORKSPACE

# Extensions the sandbox can render natively in a browser <iframe>.
_PREVIEWABLE = {
    ".html", ".htm", ".css", ".js", ".mjs", ".jsx",
    ".md", ".markdown", ".txt", ".json", ".svg",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico",
}

_MIME = {
    ".html": "text/html", ".htm": "text/html", ".css": "text/css",
    ".js": "text/javascript", ".mjs": "text/javascript",
    ".json": "application/json", ".svg": "image/svg+xml",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".txt": "text/plain",
    ".md": "text/plain", ".markdown": "text/plain",
}

# Framework markers → how to build/preview them. Used by /api/sandbox/build
# to auto-detect the project type and produce sensible npm/bun commands.
_FRAMEWORK_MARKERS = {
    "next.config.ts": "next", "next.config.js": "next", "next.config.mjs": "next",
    "angular.json": "angular",
    "vite.config.ts": "vite", "vite.config.js": "vite",
    "astro.config.mjs": "astro",
    "svelte.config.js": "svelte",
    "nuxt.config.ts": "nuxt",
}


def _resolve_in_sandbox(rel_path: str) -> _Path:
    """
    Resolve ``rel_path`` inside :data:`NEXA_WORKSPACE`, rejecting traversal.

    Raises:
        ValueError: If the path escapes the workspace or is absolute.
    """
    if not rel_path:
        raise ValueError("path is required")
    # Disallow absolute paths outright.
    p = _Path(rel_path)
    if p.is_absolute() or rel_path.startswith(("\\", "/")) or ":" in rel_path.split("/")[0]:
        raise ValueError("absolute paths are not allowed")
    target = (_WORKSPACE / rel_path.lstrip("./\\")).resolve()
    try:
        target.relative_to(_WORKSPACE.resolve())
    except ValueError:
        raise ValueError("path escapes the workspace sandbox") from None
    return target


# ---------------------------------------------------------------------------
# v4.7.0 (F-11) — File upload (multipart)
# ---------------------------------------------------------------------------

#: Maximum upload size (10 MiB). Larger payloads are rejected with 413.
_UPLOAD_MAX_BYTES = 10 * 1024 * 1024


def _sanitize_filename(name: str) -> str:
    """
    Reduce a client-supplied filename to a safe, workspace-local basename.

    Strips any directory components and keeps only alphanumerics plus a small
    whitelist; falls back to "upload.bin" when nothing safe remains.
    """
    import re as _re

    base = name.replace("\\", "/").split("/")[-1]
    base = _re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    return base or "upload.bin"


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Accept a single multipart file upload and store it in the workspace.

    Saves to ``NEXA_WORKSPACE/uploads/<sanitized-name>`` and returns a
    workspace-relative ``path`` the assistant can inspect with read tools.
    """
    data = await file.read()
    if not data:
        return JSONResponse({"error": "empty file"}, status_code=400)
    if len(data) > _UPLOAD_MAX_BYTES:
        return JSONResponse({"error": "file too large (max 10 MiB)"}, status_code=413)

    uploads = _WORKSPACE / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)

    name = _sanitize_filename(file.filename or "upload.bin")
    target = (uploads / name)
    # De-duplicate on collision: "report.pdf" → "report-1.pdf", "report-2.pdf"…
    stem, dot, ext = name.rpartition(".")
    for i in range(1, 1000):
        if not target.exists():
            break
        candidate = f"{stem}-{i}.{ext}" if dot else f"{name}-{i}"
        target = uploads / candidate

    target.write_bytes(data)
    rel = str(target.relative_to(_WORKSPACE)).replace("\\", "/")
    return {
        "ok": True,
        "filename": target.name,
        "path": rel,
        "size": len(data),
        "mime": file.content_type or "application/octet-stream",
    }


def _detect_framework(project_path: str) -> Dict[str, Any]:
    """
    Detect the project framework and package manager for a sandbox path.

    Returns a dict with ``framework``, ``package_manager``, ``install_cmd``,
    ``build_cmd``, ``preview_cmd``, and a human-friendly ``reason``.
    """
    try:
        root = _resolve_in_sandbox(project_path)
    except ValueError:
        root = _WORKSPACE
    pkg = root / "package.json"

    framework = "static"
    for marker, name in _FRAMEWORK_MARKERS.items():
        if (root / marker).exists():
            framework = name
            break

    package_manager = "npm"
    install_cmd = "npm install"
    if (root / "bun.lockb").exists() or (root / "bun.lock").exists():
        package_manager = "bun"
        install_cmd = "bun install"
    elif (root / "pnpm-lock.yaml").exists():
        package_manager = "pnpm"
        install_cmd = "pnpm install"
    elif (root / "yarn.lock").exists():
        package_manager = "yarn"
        install_cmd = "yarn"

    is_web = framework != "static" or pkg.exists()

    build_cmd = {
        "next": f"{package_manager} run build",
        "angular": f"{package_manager} run build",
        "vite": f"{package_manager} run build",
        "astro": f"{package_manager} run build",
        "svelte": f"{package_manager} run build",
        "nuxt": f"{package_manager} run build",
        "static": "",
    }.get(framework, f"{package_manager} run build")

    preview_cmd = {
        "next": f"{package_manager} run dev",
        "angular": f"{package_manager} run start",
        "vite": f"{package_manager} run dev",
        "astro": f"{package_manager} run dev",
        "svelte": f"{package_manager} dev",
        "nuxt": f"{package_manager} run dev",
        "static": "",
    }.get(framework, f"{package_manager} run dev")

    return {
        "path": project_path,
        "exists": root.exists(),
        "framework": framework,
        "package_manager": package_manager,
        "is_web_project": is_web,
        "install_cmd": install_cmd,
        "build_cmd": build_cmd,
        "preview_cmd": preview_cmd,
    }


class SandboxBuildRequest(BaseModel):
    """Request body for POST /api/sandbox/build."""

    path: str = ""
    command: Optional[str] = None


@app.get("/api/sandbox/tree")
async def sandbox_tree(path: str = "", depth: int = 3) -> Dict[str, Any]:
    """
    List the file tree of a sandbox directory for the Web Preview picker.

    Returns a nested tree up to ``depth`` levels, with file metadata.
    """
    try:
        root = _resolve_in_sandbox(path) if path else _WORKSPACE
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if not root.exists():
        return {"path": path, "tree": []}

    def _node(p: _Path, d: int) -> Dict[str, Any]:
        node: Dict[str, Any] = {
            "name": p.name or str(p),
            "path": str(p.relative_to(_WORKSPACE)),
            "is_dir": p.is_dir(),
            "previewable": p.suffix.lower() in _PREVIEWABLE,
        }
        if p.is_dir() and d > 0 and p.name not in ("node_modules", ".git", ".next", "__pycache__"):
            try:
                node["children"] = [
                    _node(c, d - 1) for c in sorted(p.iterdir())[:50]
                ]
            except OSError:
                node["children"] = []
        return node

    return {"path": path, "tree": _node(root, depth)}


@app.get("/api/sandbox/preview")
async def sandbox_preview(path: str = "") -> Any:
    """
    Serve a workspace file for preview in the <iframe> sandbox.

    Static web assets (HTML/CSS/JS/images) are served inline so the
    Web Preview can render them. Everything else returns 415.
    """
    try:
        target = _resolve_in_sandbox(path)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    if not target.exists():
        return JSONResponse({"error": f"not found: {path}"}, status_code=404)

    # Directory → render an index page listing previewable children.
    if target.is_dir():
        try:
            entries = []
            for child in sorted(target.iterdir()):
                if child.name.startswith(".") or child.name in ("node_modules", "__pycache__"):
                    continue
                rel = str(child.relative_to(_WORKSPACE)).replace("\\", "/")
                if child.suffix.lower() in _PREVIEWABLE or child.is_dir():
                    icon = "📁" if child.is_dir() else "📄"
                    entries.append(
                        f'<li><a href="/api/sandbox/preview?path={rel}">{icon} {child.name}</a></li>'
                    )
        except OSError:
            entries = []
        body = (
            "<html><head><meta charset='utf-8'>"
            "<style>body{font-family:system-ui;background:#141618;color:#ececec;padding:24px}"
            "a{color:#4A9EFF;text-decoration:none}li{margin:6px 0}</style></head><body>"
            f"<h2>📂 {target.name or 'workspace'}</h2><ul>{''.join(entries) or '<li>No previewable files.</li>'}</ul>"
            "</body></html>"
        )
        return _HTMLResponse(body)

    mime = _MIME.get(target.suffix.lower())
    if mime is None:
        return JSONResponse(
            {"error": f"file type '{target.suffix}' cannot be previewed in a browser"},
            status_code=415,
        )

    # Wrap bare JS in an <html> shell so it executes in the iframe.
    if target.suffix.lower() in (".js", ".mjs"):
        code = target.read_text(encoding="utf-8", errors="replace")
        body = (
            "<html><head><meta charset='utf-8'>"
            "<style>body{background:#141618;color:#0f0}</style></head><body>"
            "<pre id='log' style='font-family:monospace;font-size:13px'></pre>"
            "<script>"
            "const log=(...a)=>{document.getElementById('log').textContent+=a.join(' ')+'\\n'};"
            "console.log=log;console.error=log;console.warn=log;"
            "</script>"
            f"<script type='module'>{code}</script></body></html>"
        )
        return _HTMLResponse(body)

    from fastapi.responses import Response

    data = target.read_bytes()
    return Response(content=data, media_type=mime)


@app.post("/api/sandbox/build")
async def sandbox_build(req: SandboxBuildRequest) -> Dict[str, Any]:
    """
    Auto-detect a project's framework and return the commands to install,
    build, and preview it. Optionally run a command right away.
    """
    info = _detect_framework(req.path)
    result: Dict[str, Any] = {"ok": True, "detected": info}

    if req.command:
        from tools.terminal_tool import run_terminal_command

        # Resolve the sandbox-relative path to an absolute workspace path
        # so terminal_tool's cwd validation accepts it.
        try:
            cwd_abs = str(_resolve_in_sandbox(req.path)) if req.path else None
        except ValueError:
            cwd_abs = None

        try:
            out = await run_terminal_command(
                req.command,
                cwd=cwd_abs,
                timeout=180.0,
            )
            result["ran"] = {"command": req.command, "output": out}
        except Exception as exc:  # noqa: BLE001
            result["ok"] = False
            result["error"] = str(exc)
    return result


# ---------------------------------------------------------------------------
# Skills API (Batch 8 — v4.4.0)
# ---------------------------------------------------------------------------

# Lazily resolved provider used for skills that call the LLM via the server.
# Mirrors the pattern used by /api/provider/add: mutate the shared module-level
# provider rather than re-constructing the agent.
_provider_lock = False  # simple once-guard


def _get_skill_provider():
    """Return (and cache) a provider for skill execution, or None if unavailable."""
    global _provider_lock
    from nexa.provider import LLMProvider

    if _provider_lock and hasattr(_get_skill_provider, "_cache"):
        return _get_skill_provider._cache
    try:
        provider = LLMProvider()
        _get_skill_provider._cache = provider
        _provider_lock = True
        return provider
    except Exception:
        return None


@app.get("/api/skills")
async def skills_list(category: str = "") -> Dict[str, Any]:
    """
    List all discovered skills; optionally filtered by category.

    Returns a JSON-safe summary for each skill (name, version, description,
    category, permissions, tags, examples, enabled flag). The full manifest is
    available server-side at skills/<category>/<name>/manifest.yaml.
    """
    import skills

    return {"skills": skills.list_skills(category=category or None)}


@app.post("/api/skills/{name}/execute")
async def skills_execute(name: str, req: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a skill by name against the current active provider.

    Body: ``{"input": {...}}`` — the skill's input payload (validated against
    its manifest input_schema).

    Returns the skill's structured output, or a 4xx/5xx with a clear error.
    The skill handler runs via ``skills.execute_skill()`` — which enforces
    input validation, permission gates (when set), and output validation.
    """
    import asyncio

    import skills

    try:
        input_data = req.get("input") or {}
        provider = _get_skill_provider()
        if provider is None:
            return JSONResponse(
                status_code=503,
                content={"error": "LLM provider unavailable — cannot execute skill"},
            )
        result = await asyncio.wait_for(
            skills.execute_skill(name, input_data, provider),
            timeout=600.0,  # skills may be slow on local LLMs
        )
        return {"ok": True, "skill": name, "result": result}
    except skills.SkillNotFoundError:
        return JSONResponse(status_code=404, content={"error": f"unknown skill {name!r}"})
    except skills.SkillDisabledError as exc:
        return JSONResponse(
            status_code=403,
            content={"error": f"skill {name!r} is disabled (env-gated)", "detail": str(exc)},
        )
    except skills.SkillInputError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except (skills.SkillOutputError, ValueError) as exc:
        return JSONResponse(status_code=502, content={"error": f"invalid skill output: {exc}"})
    except asyncio.TimeoutError:
        return JSONResponse(status_code=504, content={"error": "skill execution timed out (600s)"})
    except Exception as exc:  # noqa: BLE001 — provider/LLM unreachable, etc.
        return JSONResponse(status_code=502, content={"error": str(exc)})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    """
    Entry point for running the server directly.

    Acquires the ``server`` singleton lock first so a second ``server.py``
    process fails fast with remediation steps instead of silently
    double-binding port 8000 (the "2 processes" bug).
    """
    import sys

    import uvicorn

    from nexa.process_manager import SingletonConflict, acquire_singleton

    try:
        _server_lock = acquire_singleton("server", label="server.py:8000")
    except SingletonConflict as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
