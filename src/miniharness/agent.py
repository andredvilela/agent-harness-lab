from __future__ import annotations

from .config import LabConfig
from .events import EventLogger
from .tools import ToolRegistry
from .types import AgentRunResult, Message, ModelTurn


def _add_tokens(total: int | None, value: int | None) -> int | None:
    if value is None:
        return total
    return (0 if total is None else total) + value


def run_agent_loop(
    *,
    task: str,
    model: object,
    registry: ToolRegistry,
    events: EventLogger,
    config: LabConfig,
) -> AgentRunResult:
    tools = registry.definitions()
    tool_names = [tool.name for tool in tools]
    messages: list[Message] = [Message(role="user", content=task)]

    model_calls = 0
    tool_call_count = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    last_text = ""

    max_turns = config.agent.max_turns

    for turn in range(1, max_turns + 1):
        events.emit(
            "model_request",
            turn=turn,
            provider=config.model.provider,
            model=config.model.model,
            message_count=len(messages),
            available_tools=tool_names,
        )

        try:
            model_turn: ModelTurn = model.generate_turn(messages, tools, turn=turn)
        except Exception as exc:
            return AgentRunResult(
                text=last_text,
                outcome="error",
                model_calls=model_calls,
                tool_calls=tool_call_count,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                error=str(exc),
                messages=messages,
            )

        model_calls += 1
        last_text = model_turn.text
        input_tokens = _add_tokens(input_tokens, model_turn.input_tokens)
        output_tokens = _add_tokens(output_tokens, model_turn.output_tokens)

        events.emit(
            "model_response",
            turn=turn,
            input_tokens=model_turn.input_tokens,
            output_tokens=model_turn.output_tokens,
            text_present=bool(model_turn.text.strip()),
            tool_call_count=len(model_turn.tool_calls),
        )

        if not model_turn.tool_calls:
            return AgentRunResult(
                text=model_turn.text,
                outcome="completed",
                model_calls=model_calls,
                tool_calls=tool_call_count,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                messages=messages,
            )

        messages.append(
            Message(
                role="assistant",
                content=model_turn.text,
                tool_calls=model_turn.tool_calls,
                raw_output=model_turn.raw_output,
            )
        )

        for call in model_turn.tool_calls:
            events.emit(
                "tool_requested",
                turn=turn,
                tool_call_id=call.id,
                tool=call.name,
                arguments=call.arguments,
            )
            events.emit(
                "tool_started",
                turn=turn,
                tool_call_id=call.id,
                tool=call.name,
            )
            result = registry.execute(call)
            tool_call_count += 1
            events.emit(
                "tool_finished",
                turn=turn,
                tool_call_id=call.id,
                tool=call.name,
                ok=result.ok,
                output_chars=len(result.output),
            )
            messages.append(Message(role="tool", tool_result=result))

    return AgentRunResult(
        text=last_text,
        outcome="max_turns_exceeded",
        model_calls=model_calls,
        tool_calls=tool_call_count,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        messages=messages,
    )
