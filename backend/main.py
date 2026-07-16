"""
Nexa Agent — FastAPI Gateway
============================

This module creates the FastAPI application that exposes Nexa Agent via:

- ``GET  /api/health`` — health check.
- ``GET  /api/conversations`` — list all conversations.
- ``POST /api/conversations`` — create a new conversation.
- ``GET  /api/conversations/{id}`` — get a conversation's messages.
- ``DELETE /api/conversations/{id}`` — delete a conversation.
- ``WS   /ws/chat`` — streaming chat over WebSocket.

The WebSocket endpoint receives JSON ``{"conversation_id": "...", "message": "..."}``
and streams back event dicts (``thinking``, ``token``, ``tool_call``, ``done``,
``error``).

Run with::

    cd backend
    uvicorn main:app --reload --port 8000

Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import json
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import NexaAgent
from config import NEXA_NAME, NEXA_VERSION
from storage import ConversationDB

# Singleton instances (initialized on startup).
_db: ConversationDB = ConversationDB()
_agent: NexaAgent = NexaAgent(db=_db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler — initialize the database on startup.

    Args:
        app: The FastAPI application instance.
    """
    await _db.init()
    yield


app = FastAPI(
    title=NEXA_NAME,
    version=NEXA_VERSION,
    description=f"{NEXA_NAME} — Python backend with streaming WebSocket chat.",
    lifespan=lifespan,
)

# Allow the Next.js frontend (port 3000) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class CreateConversationRequest(BaseModel):
    """Request body for creating a conversation."""

    title: str = "new session"


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
async def health() -> Dict[str, Any]:
    """
    Health check endpoint.

    Returns:
        A dict with ``status``, ``name``, and ``version``.
    """
    return {"status": "ok", "name": NEXA_NAME, "version": NEXA_VERSION}


@app.get("/api/conversations")
async def list_conversations() -> Dict[str, Any]:
    """
    List all conversations, newest first.

    Returns:
        A dict with a ``conversations`` list.
    """
    convs = await _db.list_conversations()
    return {"conversations": convs}


@app.post("/api/conversations")
async def create_conversation(req: CreateConversationRequest) -> Dict[str, Any]:
    """
    Create a new conversation.

    Args:
        req: The request body containing an optional ``title``.

    Returns:
        The newly created conversation dict.
    """
    return await _db.create_conversation(title=req.title)


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str) -> Dict[str, Any]:
    """
    Get all messages for a conversation.

    Args:
        conversation_id: The conversation ID.

    Returns:
        A dict with ``conversation_id`` and ``messages``.
    """
    messages = await _db.get_messages(conversation_id)
    return {"conversation_id": conversation_id, "messages": messages}


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str) -> Dict[str, bool]:
    """
    Delete a conversation and all its messages.

    Args:
        conversation_id: The conversation ID.

    Returns:
        A dict with ``ok: True``.
    """
    await _db.delete_conversation(conversation_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# WebSocket streaming endpoint
# ---------------------------------------------------------------------------
@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket) -> None:
    """
    WebSocket endpoint for streaming chat.

    The client sends JSON messages of the form::

        {"conversation_id": "conv-...", "message": "Hello"}

    If ``conversation_id`` is omitted or unknown, a new conversation is
    created and a ``session`` event is sent back.

    The server streams back events:

    - ``{"type": "session", "conversation_id": "...", "is_new": true}``
    - ``{"type": "thinking"}``
    - ``{"type": "token", "text": "..."}``
    - ``{"type": "tool_call", "name": "...", "result": {...}}``
    - ``{"type": "done", "answer": "..."}``
    - ``{"type": "error", "message": "..."}``

    Args:
        ws: The incoming WebSocket connection.
    """
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            message = str(data.get("message", "")).strip()
            if not message:
                await ws.send_json({"type": "error", "message": "message is required"})
                continue

            conv_id = data.get("conversation_id")
            is_new = False
            if not conv_id:
                conv = await _db.create_conversation(title=message[:48])
                conv_id = conv["id"]
                is_new = True
                await ws.send_json(
                    {"type": "session", "conversation_id": conv_id, "is_new": True}
                )

            # Load history from DB.
            db_msgs = await _db.get_messages(conv_id)
            history = [
                {"role": m["role"], "content": m["content"], "tool_name": m.get("tool_name")}
                for m in db_msgs
                if m["role"] != "system"
            ]

            # Stream the agent turn.
            async for event in _agent.run_streaming(message, conv_id, history):
                await ws.send_json(event)

    except WebSocketDisconnect:
        # Client disconnected — clean exit.
        pass
    except Exception as exc:
        # Send the error to the client if the connection is still open.
        try:
            await ws.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass


if __name__ == "__main__":
    """
    Entry point for running the app directly with ``python main.py``.

    This starts uvicorn on ``0.0.0.0:8000`` with auto-reload enabled.
    """
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
