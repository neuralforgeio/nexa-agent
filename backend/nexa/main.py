"""
Nexa Agent — FastAPI Gateway
Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT

Run: uvicorn nexa.main:app --reload --port 8000
"""

import json
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agent import NexaAgent
from .constants import NEXA_NAME, NEXA_VERSION
from .state import (
    add_message,
    create_conversation,
    delete_conversation,
    get_messages,
    init_db,
    list_conversations,
)

app = FastAPI(title=NEXA_NAME, version=NEXA_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singleton agent.
_agent: NexaAgent | None = None


def get_agent() -> NexaAgent:
    global _agent
    if _agent is None:
        _agent = NexaAgent()
    return _agent


@app.on_event("startup")
async def startup():
    await init_db()


# ---- REST endpoints ----


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    history: list[Dict[str, str]] | None = None


@app.get("/api/conversations")
async def api_list_conversations():
    return {"conversations": await list_conversations()}


@app.post("/api/conversations")
async def api_create_conversation(title: str = "new session"):
    return await create_conversation(title)


@app.get("/api/conversations/{conversation_id}")
async def api_get_conversation(conversation_id: str):
    messages = await get_messages(conversation_id)
    return {"conversation_id": conversation_id, "messages": messages}


@app.delete("/api/conversations/{conversation_id}")
async def api_delete_conversation(conversation_id: str):
    await delete_conversation(conversation_id)
    return {"ok": True}


@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    """Non-streaming chat endpoint."""
    agent = get_agent()

    # Resolve conversation.
    conv_id = req.conversation_id
    if not conv_id:
        conv = await create_conversation(title=req.message[:48])
        conv_id = conv["id"]

    # Load history from DB if not provided.
    history = req.history
    if not history:
        db_msgs = await get_messages(conv_id)
        history = [{"role": m["role"], "content": m["content"]} for m in db_msgs if m["role"] != "system"]

    # Persist user message.
    await add_message(conv_id, "user", req.message)

    # Run agent.
    result = await agent.run_conversation(req.message, history)

    # Persist tool results + answer.
    for step in result["steps"]:
        if step["kind"] == "tool_result":
            await add_message(conv_id, "tool", step["result"]["output"], step["result"]["tool"])
    await add_message(conv_id, "assistant", result["answer"])

    return {
        "conversation_id": conv_id,
        "answer": result["answer"],
        "steps": result["steps"],
        "iterations": result["iterations"],
    }


@app.get("/api/models")
async def api_models():
    return {"models": [{"id": "gpt-4o", "name": "GPT-4o"}, {"id": "gpt-4o-mini", "name": "GPT-4o Mini"}]}


@app.get("/api/health")
async def health():
    return {"status": "ok", "name": NEXA_NAME, "version": NEXA_VERSION}


# ---- WebSocket streaming endpoint ----


@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    """
    WebSocket chat with streaming events.

    Client sends: {"message": "...", "conversation_id": "...", "history": [...]}
    Server sends: {"type": "thinking" | "token" | "tool_call" | "tool_result" | "done" | "error"}
    """
    await ws.accept()
    agent = get_agent()
    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            message = data.get("message", "").strip()
            if not message:
                await ws.send_json({"type": "error", "message": "message is required"})
                continue

            conv_id = data.get("conversation_id")
            if not conv_id:
                conv = await create_conversation(title=message[:48])
                conv_id = conv["id"]
                await ws.send_json({"type": "session", "conversation_id": conv_id, "is_new": True})

            history = data.get("history", [])
            if not history:
                db_msgs = await get_messages(conv_id)
                history = [{"role": m["role"], "content": m["content"]} for m in db_msgs if m["role"] != "system"]

            await add_message(conv_id, "user", message)

            tool_results = []
            final_answer = ""
            async for event in agent.run_streaming(message, history):
                await ws.send_json(event)
                if event["type"] == "tool_result":
                    tr = event["result"]
                    tool_results.append(tr)
                    await add_message(conv_id, "tool", tr["output"], tr["tool"])
                elif event["type"] == "done":
                    final_answer = event["answer"]
                elif event["type"] == "error":
                    final_answer = f"[Nexa] {event['message']}"

            if final_answer:
                await add_message(conv_id, "assistant", final_answer)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("nexa.main:app", host="0.0.0.0", port=8000, reload=True)
