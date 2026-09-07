from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic
from openai import OpenAI

from .config import ModelConfig
from .trace import LLMTracer
from .types import Message, ModelTurn, ToolCall, ToolDefinition


@dataclass(frozen=True)
class ModelResult:
    text: str
    input_tokens: int | None
    output_tokens: int | None


def _dump_item(item: Any) -> Any:
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json", exclude_none=True)
    if isinstance(item, dict):
        return item
    return item


def _parse_json_object(raw: str) -> dict[str, Any]:
    if not raw or not str(raw).strip():
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if isinstance(value, dict):
        return value
    return {}


def _openai_tools(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
        for tool in tools
    ]


def _anthropic_tools(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters,
        }
        for tool in tools
    ]


def _dump_anthropic_block(block: Any) -> Any:
    if hasattr(block, "model_dump"):
        return block.model_dump(mode="json", exclude_none=True)
    if isinstance(block, dict):
        return dict(block)
    if hasattr(block, "__dict__"):
        dumped = {
            key: value
            for key, value in vars(block).items()
            if not key.startswith("_") and value is not None
        }
        return dumped
    return block


def _tool_use_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def _anthropic_request_kwargs(
    *,
    model: str,
    max_tokens: int,
    messages: list[Message],
    tools: list[ToolDefinition] | None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": _messages_to_anthropic(messages),
    }
    if tools:
        kwargs["tools"] = _anthropic_tools(tools)
    return kwargs


def _anthropic_turn_from_content(content: Any, usage: Any = None) -> ModelTurn:
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    raw_blocks: list[Any] = []

    for block in content:
        raw_blocks.append(_dump_anthropic_block(block))
        block_type = getattr(block, "type", None)
        if block_type is None and isinstance(block, dict):
            block_type = block.get("type")

        if block_type == "text":
            text = getattr(block, "text", None)
            if text is None and isinstance(block, dict):
                text = block.get("text", "")
            text_parts.append(text or "")
            continue

        if block_type == "tool_use":
            if isinstance(block, dict):
                tool_id = block["id"]
                name = block["name"]
                arguments = _tool_use_arguments(block.get("input"))
            else:
                tool_id = block.id
                name = block.name
                arguments = _tool_use_arguments(getattr(block, "input", None))
            tool_calls.append(
                ToolCall(
                    id=tool_id,
                    name=name,
                    arguments=arguments,
                )
            )

    return ModelTurn(
        text="".join(text_parts),
        tool_calls=tuple(tool_calls),
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        raw_output=tuple(raw_blocks),
    )


def _messages_to_openai_input(messages: list[Message]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "user":
            items.append({"role": "user", "content": message.content})
            continue
        if message.role == "assistant":
            if message.raw_output:
                items.extend(dict(item) for item in message.raw_output)
            else:
                if message.content:
                    items.append({"role": "assistant", "content": message.content})
                for call in message.tool_calls:
                    items.append(
                        {
                            "type": "function_call",
                            "call_id": call.id,
                            "name": call.name,
                            "arguments": json.dumps(call.arguments),
                        }
                    )
            continue
        if message.role == "tool" and message.tool_result is not None:
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": message.tool_result.tool_call_id,
                    "output": message.tool_result.output,
                }
            )
    return items


def _messages_to_anthropic(messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    index = 0
    while index < len(messages):
        message = messages[index]
        if message.role == "user":
            out.append({"role": "user", "content": message.content})
            index += 1
            continue
        if message.role == "assistant":
            if message.raw_output:
                content: Any = list(message.raw_output)
            else:
                content = []
                if message.content:
                    content.append({"type": "text", "text": message.content})
                for call in message.tool_calls:
                    content.append(
                        {
                            "type": "tool_use",
                            "id": call.id,
                            "name": call.name,
                            "input": call.arguments,
                        }
                    )
            out.append({"role": "assistant", "content": content})
            index += 1
            continue
        if message.role == "tool":
            results = []
            while index < len(messages) and messages[index].role == "tool":
                result = messages[index].tool_result
                if result is None:
                    index += 1
                    continue
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": result.tool_call_id,
                        "content": result.output,
                        "is_error": not result.ok,
                    }
                )
                index += 1
            out.append({"role": "user", "content": results})
            continue
        index += 1
    return out


class OpenAIModelClient:
    def __init__(
        self,
        model: str,
        max_output_tokens: int,
        tracer: LLMTracer | None = None,
    ):
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.tracer = tracer or LLMTracer(mode="off")
        self.client = OpenAI()

    def generate(self, prompt: str) -> ModelResult:
        payload = {
            "model": self.model,
            "input": prompt,
            "max_output_tokens": self.max_output_tokens,
        }
        self.tracer.request(
            turn=1,
            provider="openai",
            model=self.model,
            endpoint="responses",
            payload=payload,
        )
        response = self.client.responses.create(**payload)
        self.tracer.response(
            turn=1,
            provider="openai",
            model=self.model,
            endpoint="responses",
            payload=response,
        )

        usage = getattr(response, "usage", None)
        return ModelResult(
            text=response.output_text,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )

    def generate_turn(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        *,
        turn: int | None = None,
    ) -> ModelTurn:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "input": _messages_to_openai_input(messages),
            "max_output_tokens": self.max_output_tokens,
        }
        if tools:
            kwargs["tools"] = _openai_tools(tools)

        trace_turn = 1 if turn is None else turn
        self.tracer.request(
            turn=trace_turn,
            provider="openai",
            model=self.model,
            endpoint="responses",
            payload=kwargs,
        )
        response = self.client.responses.create(**kwargs)
        self.tracer.response(
            turn=trace_turn,
            provider="openai",
            model=self.model,
            endpoint="responses",
            payload=response,
        )
        usage = getattr(response, "usage", None)

        tool_calls: list[ToolCall] = []
        for item in response.output:
            if getattr(item, "type", None) != "function_call":
                continue
            tool_calls.append(
                ToolCall(
                    id=item.call_id,
                    name=item.name,
                    arguments=_parse_json_object(item.arguments),
                )
            )

        raw_output = tuple(_dump_item(item) for item in response.output)
        return ModelTurn(
            text=response.output_text or "",
            tool_calls=tuple(tool_calls),
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            raw_output=raw_output,
        )


class AnthropicModelClient:
    def __init__(
        self,
        model: str,
        max_output_tokens: int,
        tracer: LLMTracer | None = None,
    ):
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.tracer = tracer or LLMTracer(mode="off")
        self.client = Anthropic()

    def generate(self, prompt: str) -> ModelResult:
        payload = {
            "model": self.model,
            "max_tokens": self.max_output_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }
        self.tracer.request(
            turn=1,
            provider="anthropic",
            model=self.model,
            endpoint="messages",
            payload=payload,
        )
        response = self.client.messages.create(**payload)
        self.tracer.response(
            turn=1,
            provider="anthropic",
            model=self.model,
            endpoint="messages",
            payload=response,
        )

        text_parts = [
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        ]

        usage = getattr(response, "usage", None)
        return ModelResult(
            text="".join(text_parts),
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )

    def generate_turn(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        *,
        turn: int | None = None,
    ) -> ModelTurn:
        kwargs = _anthropic_request_kwargs(
            model=self.model,
            max_tokens=self.max_output_tokens,
            messages=messages,
            tools=tools,
        )
        trace_turn = 1 if turn is None else turn
        self.tracer.request(
            turn=trace_turn,
            provider="anthropic",
            model=self.model,
            endpoint="messages",
            payload=kwargs,
        )
        response = self.client.messages.create(**kwargs)
        self.tracer.response(
            turn=trace_turn,
            provider="anthropic",
            model=self.model,
            endpoint="messages",
            payload=response,
        )
        return _anthropic_turn_from_content(
            response.content,
            getattr(response, "usage", None),
        )


def create_model_client(
    config: ModelConfig,
    tracer: LLMTracer | None = None,
) -> OpenAIModelClient | AnthropicModelClient:
    if config.provider == "openai":
        return OpenAIModelClient(
            model=config.model,
            max_output_tokens=config.max_output_tokens,
            tracer=tracer,
        )

    if config.provider == "anthropic":
        return AnthropicModelClient(
            model=config.model,
            max_output_tokens=config.max_output_tokens,
            tracer=tracer,
        )

    raise ValueError(f"Unsupported provider: {config.provider}")
