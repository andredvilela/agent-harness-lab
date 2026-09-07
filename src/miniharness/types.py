from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    tool_call_id: str
    ok: bool
    output: str


@dataclass(frozen=True)
class Message:
    role: str
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_result: ToolResult | None = None
    raw_output: tuple[Any, ...] | None = None


@dataclass(frozen=True)
class ModelTurn:
    text: str
    tool_calls: tuple[ToolCall, ...]
    input_tokens: int | None
    output_tokens: int | None
    raw_output: tuple[Any, ...] | None = None


@dataclass
class AgentRunResult:
    text: str
    outcome: str
    model_calls: int
    tool_calls: int
    input_tokens: int | None
    output_tokens: int | None
    error: str | None = None
    messages: list[Message] = field(default_factory=list)
