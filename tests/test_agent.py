from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miniharness.agent import run_agent_loop
from miniharness.config import AgentConfig, LabConfig, ModelConfig
from miniharness.events import EventLogger
from miniharness.tools import ToolRegistry
from miniharness.types import Message, ModelTurn, ToolCall, ToolDefinition


class FakeAlwaysToolModel:
    def generate_turn(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> ModelTurn:
        return ModelTurn(
            text="listing",
            tool_calls=(
                ToolCall(
                    id="call-loop",
                    name="list_files",
                    arguments={"path": ".", "max_depth": 1},
                ),
            ),
            input_tokens=1,
            output_tokens=2,
        )


class FakeUnknownThenStopModel:
    def __init__(self) -> None:
        self.calls = 0

    def generate_turn(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
    ) -> ModelTurn:
        self.calls += 1
        if self.calls == 1:
            return ModelTurn(
                text="trying shell",
                tool_calls=(
                    ToolCall(
                        id="call-shell",
                        name="shell",
                        arguments={"command": "ls"},
                    ),
                ),
                input_tokens=3,
                output_tokens=4,
            )
        return ModelTurn(
            text="blocked without shell",
            tool_calls=(),
            input_tokens=5,
            output_tokens=6,
        )


def _config(tmp: Path, max_turns: int) -> LabConfig:
    return LabConfig(
        runs_dir=tmp / "runs",
        repo_root=tmp,
        model=ModelConfig(
            profile="openai_luna",
            provider="openai",
            model="gpt-5.6-luna",
            max_output_tokens=128,
        ),
        agent=AgentConfig(max_turns=max_turns),
    )


class AgentLoopTests(unittest.TestCase):
    def test_max_turns_terminates(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        (tmp / "notes.txt").write_text("x\n", encoding="utf-8")
        run_dir = tmp / "run"
        run_dir.mkdir()
        events = EventLogger(run_dir)
        result = run_agent_loop(
            task="inspect the repo",
            model=FakeAlwaysToolModel(),
            registry=ToolRegistry(tmp),
            events=events,
            config=_config(tmp, max_turns=3),
        )
        self.assertEqual(result.outcome, "max_turns_exceeded")
        self.assertEqual(result.model_calls, 3)
        self.assertEqual(result.tool_calls, 3)

        event_names = [
            line.split('"event": "')[1].split('"')[0]
            for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        self.assertIn("model_request", event_names)
        self.assertIn("model_response", event_names)
        self.assertIn("tool_requested", event_names)
        self.assertIn("tool_started", event_names)
        self.assertIn("tool_finished", event_names)

    def test_unknown_tool_is_returned_and_loop_continues(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        (tmp / "notes.txt").write_text("x\n", encoding="utf-8")
        run_dir = tmp / "run"
        run_dir.mkdir()
        fake = FakeUnknownThenStopModel()
        result = run_agent_loop(
            task="inspect the repo",
            model=fake,
            registry=ToolRegistry(tmp),
            events=EventLogger(run_dir),
            config=_config(tmp, max_turns=5),
        )
        self.assertEqual(result.outcome, "completed")
        self.assertEqual(result.text, "blocked without shell")
        self.assertEqual(result.model_calls, 2)
        self.assertEqual(result.tool_calls, 1)
        tool_message = result.messages[2]
        self.assertEqual(tool_message.role, "tool")
        assert tool_message.tool_result is not None
        self.assertFalse(tool_message.tool_result.ok)
        self.assertIn("Unknown tool", tool_message.tool_result.output)


if __name__ == "__main__":
    unittest.main()
