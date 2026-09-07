from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from miniharness.model import (
    AnthropicModelClient,
    _anthropic_request_kwargs,
    _anthropic_tools,
    _anthropic_turn_from_content,
    _messages_to_anthropic,
)
from miniharness.tools import LIST_FILES, READ_FILE
from miniharness.trace import LLMTracer
from miniharness.types import Message, ToolCall, ToolResult


TOOLS = [LIST_FILES, READ_FILE]


def _ns(**kwargs: object) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


class AnthropicAdapterTests(unittest.TestCase):
    def test_tool_definitions_map_parameters_to_input_schema(self) -> None:
        mapped = _anthropic_tools(TOOLS)
        self.assertEqual(
            [item["name"] for item in mapped],
            ["list_files", "read_file"],
        )
        self.assertEqual(mapped[0]["description"], LIST_FILES.description)
        self.assertEqual(mapped[0]["input_schema"], LIST_FILES.parameters)
        self.assertEqual(mapped[1]["input_schema"], READ_FILE.parameters)
        self.assertNotIn("parameters", mapped[0])
        self.assertEqual(mapped[1]["input_schema"]["required"], ["path"])

    def test_tool_use_parses_to_tool_call(self) -> None:
        turn = _anthropic_turn_from_content(
            [
                _ns(
                    type="tool_use",
                    id="toolu_abc",
                    name="list_files",
                    input={"path": ".", "max_depth": 2},
                )
            ],
            _ns(input_tokens=11, output_tokens=7),
        )
        self.assertEqual(turn.text, "")
        self.assertEqual(len(turn.tool_calls), 1)
        call = turn.tool_calls[0]
        self.assertEqual(call.id, "toolu_abc")
        self.assertEqual(call.name, "list_files")
        self.assertEqual(call.arguments, {"path": ".", "max_depth": 2})
        self.assertEqual(turn.input_tokens, 11)
        self.assertEqual(turn.output_tokens, 7)

    def test_multiple_tool_use_blocks_are_preserved(self) -> None:
        turn = _anthropic_turn_from_content(
            [
                _ns(type="tool_use", id="toolu_a", name="read_file", input={"path": "a.py"}),
                _ns(type="tool_use", id="toolu_b", name="read_file", input={"path": "b.py"}),
                _ns(type="tool_use", id="toolu_c", name="read_file", input={"path": "c.py"}),
            ]
        )
        self.assertEqual([call.id for call in turn.tool_calls], ["toolu_a", "toolu_b", "toolu_c"])
        self.assertEqual(
            [call.arguments["path"] for call in turn.tool_calls],
            ["a.py", "b.py", "c.py"],
        )

    def test_text_and_tool_use_are_both_preserved(self) -> None:
        turn = _anthropic_turn_from_content(
            [
                _ns(type="text", text="I'll inspect the fixture. "),
                _ns(type="text", text="Reading files next."),
                _ns(
                    type="tool_use",
                    id="toolu_1",
                    name="read_file",
                    input={"path": "fixtures/tiny_checkout/discount.py"},
                ),
            ]
        )
        self.assertEqual(
            turn.text,
            "I'll inspect the fixture. Reading files next.",
        )
        self.assertEqual(turn.tool_calls[0].id, "toolu_1")

    def test_thinking_is_not_exposed_as_visible_text(self) -> None:
        turn = _anthropic_turn_from_content(
            [
                _ns(type="thinking", thinking="secret chain", signature="sig_1"),
                _ns(type="redacted_thinking", data="opaque"),
                _ns(type="text", text="visible"),
                _ns(type="tool_use", id="toolu_1", name="list_files", input={"path": "."}),
            ]
        )
        self.assertEqual(turn.text, "visible")
        self.assertNotIn("secret chain", turn.text)
        self.assertNotIn("opaque", turn.text)

    def test_thinking_blocks_are_preserved_for_replay(self) -> None:
        thinking = {
            "type": "thinking",
            "thinking": "secret chain",
            "signature": "sig_1",
        }
        redacted = {"type": "redacted_thinking", "data": "opaque"}
        tool_use = {
            "type": "tool_use",
            "id": "toolu_keep",
            "name": "list_files",
            "input": {"path": "."},
        }
        turn = _anthropic_turn_from_content([thinking, redacted, tool_use])
        messages = [
            Message(role="user", content="inspect"),
            Message(
                role="assistant",
                content=turn.text,
                tool_calls=turn.tool_calls,
                raw_output=turn.raw_output,
            ),
            Message(
                role="tool",
                tool_result=ToolResult(
                    tool_call_id="toolu_keep",
                    ok=True,
                    output="./",
                ),
            ),
        ]
        mapped = _messages_to_anthropic(messages)
        assistant_content = mapped[1]["content"]
        self.assertEqual(assistant_content[0], thinking)
        self.assertEqual(assistant_content[1], redacted)
        self.assertEqual(assistant_content[2]["type"], "tool_use")
        self.assertEqual(assistant_content[2]["id"], "toolu_keep")

    def test_successful_tool_result_mapping(self) -> None:
        mapped = _messages_to_anthropic(
            [
                Message(role="user", content="inspect"),
                Message(
                    role="assistant",
                    tool_calls=(
                        ToolCall(id="toolu_ok", name="read_file", arguments={"path": "a.py"}),
                    ),
                ),
                Message(
                    role="tool",
                    tool_result=ToolResult(
                        tool_call_id="toolu_ok",
                        ok=True,
                        output="PRICE = 1\n",
                    ),
                ),
            ]
        )
        result = mapped[2]["content"][0]
        self.assertEqual(result["type"], "tool_result")
        self.assertEqual(result["tool_use_id"], "toolu_ok")
        self.assertEqual(result["content"], "PRICE = 1\n")
        self.assertFalse(result["is_error"])

    def test_failed_tool_result_sets_is_error(self) -> None:
        mapped = _messages_to_anthropic(
            [
                Message(role="user", content="inspect"),
                Message(
                    role="assistant",
                    tool_calls=(
                        ToolCall(id="toolu_err", name="read_file", arguments={"path": "nope.py"}),
                    ),
                ),
                Message(
                    role="tool",
                    tool_result=ToolResult(
                        tool_call_id="toolu_err",
                        ok=False,
                        output="File not found: nope.py",
                    ),
                ),
            ]
        )
        result = mapped[2]["content"][0]
        self.assertEqual(
            result,
            {
                "type": "tool_result",
                "tool_use_id": "toolu_err",
                "content": "File not found: nope.py",
                "is_error": True,
            },
        )

    def test_tool_use_id_is_preserved_on_tool_result(self) -> None:
        original_id = "toolu_original_id"
        turn = _anthropic_turn_from_content(
            [
                _ns(
                    type="tool_use",
                    id=original_id,
                    name="list_files",
                    input={"path": "."},
                )
            ]
        )
        mapped = _messages_to_anthropic(
            [
                Message(role="user", content="inspect"),
                Message(
                    role="assistant",
                    tool_calls=turn.tool_calls,
                    raw_output=turn.raw_output,
                ),
                Message(
                    role="tool",
                    tool_result=ToolResult(
                        tool_call_id=turn.tool_calls[0].id,
                        ok=True,
                        output="./",
                    ),
                ),
            ]
        )
        self.assertEqual(turn.tool_calls[0].id, original_id)
        self.assertEqual(mapped[2]["content"][0]["tool_use_id"], original_id)

    def test_multiple_tool_results_share_one_user_message(self) -> None:
        mapped = _messages_to_anthropic(
            [
                Message(role="user", content="inspect"),
                Message(
                    role="assistant",
                    tool_calls=(
                        ToolCall(id="toolu_a", name="read_file", arguments={"path": "a.py"}),
                        ToolCall(id="toolu_b", name="read_file", arguments={"path": "b.py"}),
                    ),
                ),
                Message(
                    role="tool",
                    tool_result=ToolResult(tool_call_id="toolu_a", ok=True, output="a"),
                ),
                Message(
                    role="tool",
                    tool_result=ToolResult(tool_call_id="toolu_b", ok=False, output="missing"),
                ),
            ]
        )
        self.assertEqual(mapped[2]["role"], "user")
        self.assertEqual(
            [block["tool_use_id"] for block in mapped[2]["content"]],
            ["toolu_a", "toolu_b"],
        )
        self.assertFalse(mapped[2]["content"][0]["is_error"])
        self.assertTrue(mapped[2]["content"][1]["is_error"])

    def test_request_omits_tools_when_empty(self) -> None:
        kwargs = _anthropic_request_kwargs(
            model="claude-haiku-4-5-20251001",
            max_tokens=128,
            messages=[Message(role="user", content="hello")],
            tools=[],
        )
        self.assertEqual(kwargs["model"], "claude-haiku-4-5-20251001")
        self.assertEqual(kwargs["max_tokens"], 128)
        self.assertEqual(
            kwargs["messages"],
            [{"role": "user", "content": "hello"}],
        )
        self.assertNotIn("tools", kwargs)
        self.assertNotIn("system", kwargs)
        self.assertNotIn("temperature", kwargs)
        self.assertNotIn("tool_choice", kwargs)

    def test_request_includes_tools_with_input_schema(self) -> None:
        kwargs = _anthropic_request_kwargs(
            model="claude-haiku-4-5-20251001",
            max_tokens=128,
            messages=[Message(role="user", content="inspect")],
            tools=TOOLS,
        )
        self.assertEqual(kwargs["tools"][0]["input_schema"], LIST_FILES.parameters)
        self.assertEqual(kwargs["tools"][1]["name"], "read_file")

    def test_stage_00_generate_does_not_send_tools(self) -> None:
        client = AnthropicModelClient.__new__(AnthropicModelClient)
        client.model = "claude-haiku-4-5-20251001"
        client.max_output_tokens = 128
        client.tracer = LLMTracer(mode="off")
        fake_messages = Mock()
        fake_messages.create.return_value = _ns(
            content=[_ns(type="text", text="no tools here")],
            usage=_ns(input_tokens=3, output_tokens=4),
        )
        client.client = _ns(messages=fake_messages)

        result = client.generate("hello")

        self.assertEqual(result.text, "no tools here")
        kwargs = fake_messages.create.call_args.kwargs
        self.assertNotIn("tools", kwargs)
        self.assertEqual(
            kwargs["messages"],
            [{"role": "user", "content": "hello"}],
        )

    def test_generate_turn_uses_messages_api_not_tool_runner(self) -> None:
        client = AnthropicModelClient.__new__(AnthropicModelClient)
        client.model = "claude-haiku-4-5-20251001"
        client.max_output_tokens = 128
        client.tracer = LLMTracer(mode="off")
        fake_messages = Mock()
        fake_messages.create.return_value = _ns(
            content=[
                _ns(
                    type="tool_use",
                    id="toolu_live",
                    name="list_files",
                    input={"path": "."},
                )
            ],
            usage=_ns(input_tokens=5, output_tokens=6),
        )
        fake_messages.tool_runner = Mock()
        client.client = _ns(messages=fake_messages)

        turn = client.generate_turn(
            [Message(role="user", content="inspect")],
            TOOLS,
        )

        fake_messages.create.assert_called_once()
        fake_messages.tool_runner.assert_not_called()
        self.assertEqual(turn.tool_calls[0].id, "toolu_live")
        self.assertEqual(
            fake_messages.create.call_args.kwargs["tools"][0]["input_schema"],
            LIST_FILES.parameters,
        )


if __name__ == "__main__":
    unittest.main()
