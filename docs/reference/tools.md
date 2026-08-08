# Nexa Agent — Tools Reference

This document describes all available tools in Nexa Agent.

## Tool Registry

Tools are managed by `ToolRegistry` (`tools/registry.py`). Each tool has:
- A unique name
- A description (shown to the LLM)
- A parameter schema (OpenAI function-calling format)
- An async execute function

## Available Tools

### read_file

Read the contents of a text file from the Nexa workspace.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | Yes | Relative path to the file |

- **Sandbox**: Confined to `forge-workspace/`
- **Size limit**: 100KB max
- **Truncation**: Content truncated to 4000 chars
- **Errors**: Returns `ok=False` for missing files, directories, or path escapes

### write_file

Write text content to a file in the Nexa workspace.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `path` | string | Yes | Relative path to the file |
| `content` | string | Yes | The text content to write |

- Creates parent directories if needed
- Overwrites existing files
- Sandboxed to `forge-workspace/`

### run_terminal_command

Execute a shell command in the Nexa workspace.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `command` | string | Yes | The shell command to execute |

- **Timeout**: 15 seconds
- **Output cap**: stdout 2000 chars, stderr 1000 chars
- **Blocked patterns**: `rm -rf /`, `mkfs`, `shutdown`, `reboot`, etc.
- **Working directory**: `forge-workspace/`

### generate_uuid

Generate a random UUID v4 string.

No parameters.

Returns a 36-character UUID string (e.g., `550e8400-e29b-41d4-a716-446655440000`).

### delegate

Spawn a sub-agent to handle a specific subtask in isolation.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task` | string | Yes | The subtask description |
| `context` | string | No | Additional context for the sub-agent |
| `max_iterations` | number | No | Max tool-call iterations (default 3) |

The sub-agent inherits the parent's provider and tool registry but gets:
- A fresh conversation transcript
- A focused system prompt
- A lower iteration budget (default 3 vs parent's 8)

Returns a summary of the sub-agent's work including any tool results.

## Adding Custom Tools

```python
from tools.registry import ToolRegistry

async def my_tool(param: str, **_) -> str:
    """My custom tool."""
    return f"Processed: {param}"

registry = ToolRegistry()
registry.register(
    name="my_tool",
    fn=my_tool,
    description="Does something useful.",
    parameters={
        "type": "object",
        "properties": {
            "param": {"type": "string", "description": "Input parameter"}
        },
        "required": ["param"],
    },
)
```

## OpenAI Function-Calling Schema

All tool schemas are exposed via `registry.get_openai_schemas()`, which returns
the standard OpenAI function-calling format:

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Read the contents of a text file...",
    "parameters": {
      "type": "object",
      "properties": { "path": { "type": "string", "description": "..." } },
      "required": ["path"]
    }
  }
}
```
