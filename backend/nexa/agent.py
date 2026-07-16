"""
Nexa Agent — Core Agent Loop
Copyright (c) 2026 Dearly Febriano Irwansyah
SPDX-License-Identifier: MIT
"""

import json
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from .constants import NEXA_MAX_TOOL_ITERATIONS, NEXA_NAME
from .memory import MemoryManager
from .provider import LLMProvider
from .tools.base import NexaTool, ToolResult
from .tools.builtin_tools import (
    CalculateTool,
    EchoTool,
    GenerateUuidTool,
    GetTimeTool,
)
from .tools.file_tools import ListDirTool, ReadFileTool, WriteFileTool
from .tools.registry import ToolRegistry
from .tools.terminal_tool import RunTerminalCommandTool


def create_default_tools() -> List[NexaTool]:
    return [
        EchoTool(),
        GetTimeTool(),
        CalculateTool(),
        GenerateUuidTool(),
        ReadFileTool(),
        WriteFileTool(),
        ListDirTool(),
        RunTerminalCommandTool(),
    ]


class NexaAgent:
    """Orchestrates one conversation turn with iterative tool calling."""

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        tools: Optional[List[NexaTool]] = None,
    ):
        self.provider = provider or LLMProvider()
        self.registry = ToolRegistry()
        self.memory = MemoryManager()
        for tool in tools or create_default_tools():
            self.registry.register(tool)

    async def run_conversation(
        self,
        user_input: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Run a full conversation turn (non-streaming)."""
        steps: List[Dict[str, Any]] = []
        system_prompt = self._build_system_prompt()
        transcript: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for m in (history or [])[-30:]:
            if m.get("role") != "system":
                transcript.append({"role": m["role"], "content": m["content"]})
        transcript.append({"role": "user", "content": user_input})

        tools_schema = self.registry.get_openai_schemas()
        iterations = 0

        while iterations < NEXA_MAX_TOOL_ITERATIONS:
            iterations += 1
            response = await self.provider.chat_completion(transcript, tools=tools_schema)
            tool_calls = response.get("tool_calls")

            if not tool_calls:
                answer = response["content"]
                steps.append({"kind": "answer", "text": answer})
                return {"answer": answer, "steps": steps, "iterations": iterations}

            # Process each tool call.
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": response["content"],
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tool_calls
                ],
            }
            transcript.append(assistant_msg)

            for tc in tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                steps.append({"kind": "tool_call", "tool": name, "arguments": args})
                result: ToolResult = await self.registry.execute(name, args)
                steps.append({"kind": "tool_result", "result": result.to_dict()})
                transcript.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result.output,
                })

        answer = f"[{NEXA_NAME}] reached the tool-call iteration cap."
        steps.append({"kind": "answer", "text": answer})
        return {"answer": answer, "steps": steps, "iterations": iterations}

    async def run_streaming(
        self,
        user_input: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Streaming variant — yields events as they happen."""
        steps: List[Dict[str, Any]] = []
        system_prompt = self._build_system_prompt()
        transcript: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for m in (history or [])[-30:]:
            if m.get("role") != "system":
                transcript.append({"role": m["role"], "content": m["content"]})
        transcript.append({"role": "user", "content": user_input})

        tools_schema = self.registry.get_openai_schemas()
        iterations = 0

        yield {"type": "thinking"}

        while iterations < NEXA_MAX_TOOL_ITERATIONS:
            iterations += 1
            try:
                response = await self.provider.chat_completion(transcript, tools=tools_schema)
            except Exception as e:
                yield {"type": "error", "message": str(e)}
                return

            tool_calls = response.get("tool_calls")
            if not tool_calls:
                answer = response["content"]
                steps.append({"kind": "answer", "text": answer})
                yield {"type": "done", "answer": answer, "iterations": iterations}
                return

            # Yield each tool call + result.
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": response["content"],
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tool_calls
                ],
            }
            transcript.append(assistant_msg)

            for tc in tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                yield {"type": "tool_call", "tool": name, "arguments": args}
                result: ToolResult = await self.registry.execute(name, args)
                yield {"type": "tool_result", "result": result.to_dict()}
                transcript.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result.output,
                })

        yield {"type": "done", "answer": f"[{NEXA_NAME}] iteration cap reached", "iterations": iterations}

    def _build_system_prompt(self) -> str:
        tool_catalog = self.registry.describe()
        memory_digest = self.memory.digest()
        body = (
            f"# Tools\nYou have access to the following tools:\n\n{tool_catalog}\n\n"
            f"# Long-term memory\n{memory_digest}\n\n"
            "Use tools when needed. If no tool is needed, answer directly."
        )
        return LLMProvider.build_system_prompt(body)
