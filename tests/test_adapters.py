from __future__ import annotations

import unittest

from miniharness.model import (
    _anthropic_tools,
    _messages_to_anthropic,
    _messages_to_openai_input,
    _openai_tools,
)
from miniharness.run import infer_stage
from miniharness.tools import LIST_FILES, READ_FILE, RUN_PYTEST
from miniharness.types import Message, ToolCall, ToolResult
from pathlib import Path


TOOLS = [LIST_FILES, READ_FILE]


class AdapterMappingTests(unittest.TestCase):
    def test_openai_tool_schema_includes_both_tools(self) -> None:
        mapped = _openai_tools(TOOLS)
        names = [item["name"] for item in mapped]
        self.assertEqual(names, ["list_files", "read_file"])
        self.assertTrue(all(item["type"] == "function" for item in mapped))

    def test_anthropic_tool_schema_includes_both_tools(self) -> None:
        mapped = _anthropic_tools(TOOLS)
        names = [item["name"] for item in mapped]
        self.assertEqual(names, ["list_files", "read_file"])
        self.assertIn("input_schema", mapped[0])

    def test_openai_replays_function_call_then_output(self) -> None:
        messages = [
            Message(role="user", content="inspect"),
            Message(
                role="assistant",
                content="",
                tool_calls=(
                    ToolCall(id="call_1", name="list_files", arguments={"path": "."}),
                ),
            ),
            Message(
                role="tool",
                tool_result=ToolResult(tool_call_id="call_1", ok=True, output="./"),
            ),
        ]
        items = _messages_to_openai_input(messages)
        self.assertEqual(items[0]["role"], "user")
        self.assertEqual(items[1]["type"], "function_call")
        self.assertEqual(items[1]["call_id"], "call_1")
        self.assertEqual(items[2]["type"], "function_call_output")
        self.assertEqual(items[2]["call_id"], "call_1")

    def test_anthropic_groups_tool_results_in_one_user_message(self) -> None:
        messages = [
            Message(role="user", content="inspect"),
            Message(
                role="assistant",
                content="looking",
                tool_calls=(
                    ToolCall(id="toolu_1", name="read_file", arguments={"path": "a.py"}),
                    ToolCall(id="toolu_2", name="read_file", arguments={"path": "b.py"}),
                ),
            ),
            Message(
                role="tool",
                tool_result=ToolResult(tool_call_id="toolu_1", ok=True, output="a"),
            ),
            Message(
                role="tool",
                tool_result=ToolResult(tool_call_id="toolu_2", ok=False, output="missing"),
            ),
        ]
        mapped = _messages_to_anthropic(messages)
        self.assertEqual(mapped[1]["role"], "assistant")
        self.assertEqual(mapped[2]["role"], "user")
        self.assertEqual(len(mapped[2]["content"]), 2)
        self.assertEqual(mapped[2]["content"][0]["type"], "tool_result")
        self.assertTrue(mapped[2]["content"][1]["is_error"])

    def test_infer_stage_from_scenario_directory(self) -> None:
        self.assertEqual(
            infer_stage(Path("scenarios/01_read_only_agent/task.md")),
            "01_read_only_agent",
        )
        self.assertEqual(
            infer_stage(Path("scenarios/00_model_only/task.md")),
            "00_model_only",
        )
        self.assertEqual(
            infer_stage(Path("scenarios/02_verify_only_agent/task.md")),
            "02_verify_only_agent",
        )

    def test_openai_and_anthropic_map_run_pytest(self) -> None:
        tools = [LIST_FILES, READ_FILE, RUN_PYTEST]
        openai_names = [item["name"] for item in _openai_tools(tools)]
        anthropic_mapped = _anthropic_tools(tools)
        anthropic_names = [item["name"] for item in anthropic_mapped]
        self.assertEqual(openai_names, ["list_files", "read_file", "run_pytest"])
        self.assertEqual(anthropic_names, ["list_files", "read_file", "run_pytest"])
        self.assertEqual(
            anthropic_mapped[2]["input_schema"],
            RUN_PYTEST.parameters,
        )
        self.assertEqual(
            _openai_tools(tools)[2]["parameters"],
            RUN_PYTEST.parameters,
        )


if __name__ == "__main__":
    unittest.main()
