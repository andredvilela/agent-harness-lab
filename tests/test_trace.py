from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from miniharness.agent import run_agent_loop
from miniharness.config import AgentConfig, DebugConfig, LabConfig, ModelConfig, load_config
from miniharness.events import EventLogger
from miniharness.model import AnthropicModelClient, OpenAIModelClient
from miniharness.run import parse_args, resolve_llm_trace_mode
from miniharness.tools import LIST_FILES, READ_FILE, ToolRegistry
from miniharness.trace import LLMTracer, to_jsonable
from miniharness.types import Message, ToolResult


TOOLS = [LIST_FILES, READ_FILE]


def _ns(**kwargs: object) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


def _debug_config(mode: str = "off") -> LabConfig:
    return LabConfig(
        runs_dir=Path("runs"),
        repo_root=Path("."),
        model=ModelConfig(
            profile="openai_luna",
            provider="openai",
            model="gpt-5.6-luna",
            max_output_tokens=128,
        ),
        agent=AgentConfig(max_turns=5),
        debug=DebugConfig(llm_trace=mode),
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class Dumpable:
    def __init__(self, **kwargs: object):
        self.__dict__.update(kwargs)

    def model_dump(self, mode: str = "json", exclude_none: bool = True) -> dict:
        data = dict(self.__dict__)
        if exclude_none:
            return {key: value for key, value in data.items() if value is not None}
        return data


class FakeOpenAIResponse:
    def __init__(self, *, text: str = "", tool: bool = False):
        if tool:
            self.output = [
                Dumpable(
                    type="function_call",
                    call_id="call_1",
                    name="list_files",
                    arguments='{"path": ".", "max_depth": 1}',
                )
            ]
            self.output_text = ""
        else:
            self.output = [Dumpable(type="message", content=text)]
            self.output_text = text
        self.usage = _ns(input_tokens=9, output_tokens=4)
        self.id = "resp_123"
        self.status = "completed"
        self.incomplete_details = {"reason": "max_output_tokens"}
        self.parallel_tool_calls = True

    def model_dump(self, mode: str = "json", exclude_none: bool = True) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "output": [
                {
                    "type": getattr(item, "type", None),
                    "call_id": getattr(item, "call_id", None),
                    "name": getattr(item, "name", None),
                    "arguments": getattr(item, "arguments", None),
                    "content": getattr(item, "content", None),
                }
                for item in self.output
            ],
            "usage": {"input_tokens": 9, "output_tokens": 4},
            "incomplete_details": self.incomplete_details,
            "parallel_tool_calls": self.parallel_tool_calls,
        }


class FakeAnthropicResponse:
    def __init__(self) -> None:
        self.id = "msg_123"
        self.type = "message"
        self.role = "assistant"
        self.model = "claude-haiku-4-5-20251001"
        self.stop_reason = "tool_use"
        self.stop_sequence = None
        self.content = [
            _ns(type="text", text="looking"),
            _ns(
                type="tool_use",
                id="toolu_abc",
                name="list_files",
                input={"path": "."},
            ),
        ]
        self.usage = _ns(input_tokens=11, output_tokens=7)

    def model_dump(self, mode: str = "json", exclude_none: bool = True) -> dict:
        dumped = {
            "id": self.id,
            "type": self.type,
            "role": self.role,
            "model": self.model,
            "stop_reason": self.stop_reason,
            "content": [
                {"type": "text", "text": "looking"},
                {
                    "type": "tool_use",
                    "id": "toolu_abc",
                    "name": "list_files",
                    "input": {"path": "."},
                },
            ],
            "usage": {"input_tokens": 11, "output_tokens": 7},
        }
        if not exclude_none:
            dumped["stop_sequence"] = self.stop_sequence
        return dumped


def _openai_client(tracer: LLMTracer, create) -> OpenAIModelClient:
    client = OpenAIModelClient.__new__(OpenAIModelClient)
    client.model = "gpt-5.6-luna"
    client.max_output_tokens = 128
    client.tracer = tracer
    client.client = _ns(responses=_ns(create=create))
    return client


def _anthropic_client(tracer: LLMTracer, create) -> AnthropicModelClient:
    client = AnthropicModelClient.__new__(AnthropicModelClient)
    client.model = "claude-haiku-4-5-20251001"
    client.max_output_tokens = 128
    client.tracer = tracer
    client.client = _ns(messages=_ns(create=create))
    return client


class TracerCoreTests(unittest.TestCase):
    def test_off_writes_no_file_and_no_stdout(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        path = tmp / "llm_trace.jsonl"
        tracer = LLMTracer(mode="off", file_path=path)
        buf = io.StringIO()
        with redirect_stdout(buf):
            tracer.request(
                turn=1,
                provider="openai",
                model="gpt-5.6-luna",
                endpoint="responses",
                payload={"model": "gpt-5.6-luna"},
            )
            tracer.response(
                turn=1,
                provider="openai",
                model="gpt-5.6-luna",
                endpoint="responses",
                payload={"id": "resp_1"},
            )
        self.assertFalse(path.exists())
        self.assertEqual(buf.getvalue(), "")

    def test_file_appends_chronological_jsonl(self) -> None:
        path = Path(tempfile.mkdtemp()) / "llm_trace.jsonl"
        tracer = LLMTracer(mode="file", file_path=path)
        tracer.request(
            turn=1,
            provider="openai",
            model="gpt-5.6-luna",
            endpoint="responses",
            payload={"hello": "one"},
        )
        tracer.response(
            turn=1,
            provider="openai",
            model="gpt-5.6-luna",
            endpoint="responses",
            payload={"hello": "two"},
        )
        records = _read_jsonl(path)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["type"], "request")
        self.assertEqual(records[1]["type"], "response")
        self.assertEqual(records[0]["turn"], 1)
        self.assertEqual(records[0]["payload"], {"hello": "one"})
        self.assertEqual(records[1]["payload"], {"hello": "two"})
        self.assertEqual(records[0]["endpoint"], "responses")

    def test_stdout_prints_and_does_not_create_file(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        path = tmp / "llm_trace.jsonl"
        tracer = LLMTracer(mode="stdout", file_path=path)
        buf = io.StringIO()
        with redirect_stdout(buf):
            tracer.request(
                turn=2,
                provider="anthropic",
                model="claude-haiku-4-5-20251001",
                endpoint="messages",
                payload={"model": "claude-haiku-4-5-20251001"},
            )
            tracer.response(
                turn=2,
                provider="anthropic",
                model="claude-haiku-4-5-20251001",
                endpoint="messages",
                payload={"id": "msg_1"},
            )
        output = buf.getvalue()
        self.assertIn("=== LLM REQUEST — TURN 2 — ANTHROPIC / MESSAGES ===", output)
        self.assertIn("=== LLM RESPONSE — TURN 2 — ANTHROPIC / MESSAGES ===", output)
        self.assertFalse(path.exists())

    def test_invalid_config_trace_mode_fails(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        config_path = tmp / "config.toml"
        config_path.write_text(
            "\n".join(
                [
                    "[lab]",
                    'runs_dir = "runs"',
                    "[debug]",
                    'llm_trace = "banana"',
                    "[models.openai_luna]",
                    'provider = "openai"',
                    'model = "gpt-5.6-luna"',
                    "max_output_tokens = 16",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        env = {"CONFIG_PATH": str(config_path), "MODEL_PROFILE": "openai_luna"}
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaises(ValueError) as ctx:
                load_config()
        self.assertIn("llm_trace", str(ctx.exception))
        self.assertIn("banana", str(ctx.exception))

    def test_cli_flags_conflict(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(
                [
                    "scenarios/01_read_only_agent/task.md",
                    "--llm-trace",
                    "--llm-trace-stdout",
                ]
            )

    def test_cli_overrides_config(self) -> None:
        args = parse_args(["scenarios/01_read_only_agent/task.md", "--llm-trace"])
        self.assertEqual(resolve_llm_trace_mode(args, _debug_config("off")), "file")
        args = parse_args(["scenarios/01_read_only_agent/task.md", "--llm-trace-stdout"])
        self.assertEqual(resolve_llm_trace_mode(args, _debug_config("file")), "stdout")
        args = parse_args(["scenarios/01_read_only_agent/task.md"])
        self.assertEqual(resolve_llm_trace_mode(args, _debug_config("off")), "off")


class TracerFidelityTests(unittest.TestCase):
    def test_openai_traced_request_matches_sdk_kwargs(self) -> None:
        path = Path(tempfile.mkdtemp()) / "llm_trace.jsonl"
        captured: dict = {}

        def create(**kwargs):
            captured["kwargs"] = kwargs
            return FakeOpenAIResponse(tool=True)

        client = _openai_client(LLMTracer(mode="file", file_path=path), create)
        client.generate_turn(
            [Message(role="user", content="inspect")],
            TOOLS,
            turn=1,
        )
        records = _read_jsonl(path)
        self.assertEqual(records[0]["type"], "request")
        self.assertEqual(records[0]["payload"], to_jsonable(captured["kwargs"]))
        self.assertEqual(captured["kwargs"]["input"][0]["content"], "inspect")
        self.assertEqual(captured["kwargs"]["tools"][0]["name"], "list_files")

    def test_anthropic_traced_request_matches_sdk_kwargs(self) -> None:
        path = Path(tempfile.mkdtemp()) / "llm_trace.jsonl"
        captured: dict = {}

        def create(**kwargs):
            captured["kwargs"] = kwargs
            return FakeAnthropicResponse()

        client = _anthropic_client(LLMTracer(mode="file", file_path=path), create)
        client.generate_turn(
            [Message(role="user", content="inspect")],
            TOOLS,
            turn=1,
        )
        records = _read_jsonl(path)
        self.assertEqual(records[0]["payload"], to_jsonable(captured["kwargs"]))
        self.assertEqual(captured["kwargs"]["tools"][0]["input_schema"], LIST_FILES.parameters)
        self.assertEqual(records[0]["endpoint"], "messages")

    def test_anthropic_response_keeps_unused_metadata(self) -> None:
        path = Path(tempfile.mkdtemp()) / "llm_trace.jsonl"
        client = _anthropic_client(
            LLMTracer(mode="file", file_path=path),
            lambda **kwargs: FakeAnthropicResponse(),
        )
        turn = client.generate_turn(
            [Message(role="user", content="inspect")],
            TOOLS,
            turn=1,
        )
        payload = _read_jsonl(path)[1]["payload"]
        self.assertEqual(payload["id"], "msg_123")
        self.assertEqual(payload["role"], "assistant")
        self.assertEqual(payload["stop_reason"], "tool_use")
        self.assertEqual(payload["model"], "claude-haiku-4-5-20251001")
        self.assertIn("usage", payload)
        self.assertEqual(turn.text, "looking")
        self.assertNotIn("stop_reason", turn.__dict__)

    def test_openai_response_keeps_unused_metadata(self) -> None:
        path = Path(tempfile.mkdtemp()) / "llm_trace.jsonl"
        client = _openai_client(
            LLMTracer(mode="file", file_path=path),
            lambda **kwargs: FakeOpenAIResponse(tool=True),
        )
        client.generate_turn([Message(role="user", content="inspect")], TOOLS, turn=1)
        payload = _read_jsonl(path)[1]["payload"]
        self.assertEqual(payload["id"], "resp_123")
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["incomplete_details"], {"reason": "max_output_tokens"})
        self.assertTrue(payload["parallel_tool_calls"])

    def test_raw_output_unchanged_with_tracing(self) -> None:
        off_client = _anthropic_client(
            LLMTracer(mode="off"),
            lambda **kwargs: FakeAnthropicResponse(),
        )
        path = Path(tempfile.mkdtemp()) / "llm_trace.jsonl"
        on_client = _anthropic_client(
            LLMTracer(mode="file", file_path=path),
            lambda **kwargs: FakeAnthropicResponse(),
        )
        messages = [Message(role="user", content="inspect")]
        off_turn = off_client.generate_turn(messages, TOOLS, turn=1)
        on_turn = on_client.generate_turn(messages, TOOLS, turn=1)
        self.assertEqual(off_turn.raw_output, on_turn.raw_output)
        self.assertEqual(off_turn.tool_calls, on_turn.tool_calls)
        self.assertEqual(off_turn.text, on_turn.text)

        continued = [
            Message(role="user", content="inspect"),
            Message(
                role="assistant",
                content=on_turn.text,
                tool_calls=on_turn.tool_calls,
                raw_output=on_turn.raw_output,
            ),
            Message(
                role="tool",
                tool_result=ToolResult(
                    tool_call_id="toolu_abc",
                    ok=False,
                    output="File not found: x",
                ),
            ),
        ]
        from miniharness.model import _messages_to_anthropic

        mapped = _messages_to_anthropic(continued)
        self.assertEqual(mapped[1]["content"], list(on_turn.raw_output))
        self.assertTrue(mapped[2]["content"][0]["is_error"])

    def test_turn_correlation_with_agent_loop(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        (tmp / "notes.txt").write_text("x\n", encoding="utf-8")
        run_dir = tmp / "run"
        run_dir.mkdir()
        trace_path = run_dir / "llm_trace.jsonl"
        calls = {"n": 0}

        def create(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return FakeOpenAIResponse(tool=True)
            return FakeOpenAIResponse(text="done")

        model = _openai_client(LLMTracer(mode="file", file_path=trace_path), create)
        result = run_agent_loop(
            task="inspect the repo",
            model=model,
            registry=ToolRegistry(tmp),
            events=EventLogger(run_dir),
            config=_debug_config("file"),
        )
        self.assertEqual(result.outcome, "completed")
        events = _read_jsonl(run_dir / "events.jsonl")
        traces = _read_jsonl(trace_path)
        event_turns = [item["turn"] for item in events if item.get("event") == "model_request"]
        request_turns = [item["turn"] for item in traces if item["type"] == "request"]
        response_turns = [item["turn"] for item in traces if item["type"] == "response"]
        self.assertEqual(event_turns, [1, 2])
        self.assertEqual(request_turns, [1, 2])
        self.assertEqual(response_turns, [1, 2])
        self.assertEqual(
            [item["type"] for item in traces],
            ["request", "response", "request", "response"],
        )

    def test_stage_00_generate_is_traced_as_turn_1(self) -> None:
        path = Path(tempfile.mkdtemp()) / "llm_trace.jsonl"
        captured: dict = {}

        def create(**kwargs):
            captured["kwargs"] = kwargs
            return FakeOpenAIResponse(text="hello")

        client = _openai_client(LLMTracer(mode="file", file_path=path), create)
        client.generate("naked prompt")
        records = _read_jsonl(path)
        self.assertEqual(records[0]["turn"], 1)
        self.assertEqual(records[0]["payload"], to_jsonable(captured["kwargs"]))
        self.assertEqual(captured["kwargs"]["input"], "naked prompt")
        self.assertNotIn("tools", captured["kwargs"])

    def test_events_do_not_contain_raw_payloads(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        (tmp / "notes.txt").write_text("x\n", encoding="utf-8")
        run_dir = tmp / "run"
        run_dir.mkdir()
        model = _openai_client(
            LLMTracer(mode="file", file_path=run_dir / "llm_trace.jsonl"),
            lambda **kwargs: FakeOpenAIResponse(text="done"),
        )
        run_agent_loop(
            task="inspect",
            model=model,
            registry=ToolRegistry(tmp),
            events=EventLogger(run_dir),
            config=_debug_config("file"),
        )
        for record in _read_jsonl(run_dir / "events.jsonl"):
            self.assertNotIn("payload", record)
            self.assertNotIn("endpoint", record)


if __name__ == "__main__":
    unittest.main()
