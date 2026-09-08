from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .agent import run_agent_loop
from .config import LabConfig, load_config
from .events import EventLogger
from .model import create_model_client
from .tools import STAGE_TOOLS, ToolRegistry
from .trace import LLMTracer
from .types import AgentRunResult


def new_run_dir(runs_dir: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{stamp}-{uuid.uuid4().hex[:8]}"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def infer_stage(task_file: Path) -> str:
    name = task_file.resolve().parent.name
    if name in STAGE_TOOLS:
        return name
    return "00_model_only"


def emit_console(text: str) -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        buffer = getattr(sys.stdout, "buffer", None)
        payload = (text + "\n").encode(encoding, errors="replace")
        if buffer is not None:
            buffer.write(payload)
            buffer.flush()
            return
        sys.stdout.write(payload.decode(encoding, errors="replace"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_file", type=Path)
    parser.add_argument(
        "--llm-trace",
        action="store_true",
        help="Write complete provider request/response payloads to llm_trace.jsonl",
    )
    parser.add_argument(
        "--llm-trace-stdout",
        action="store_true",
        help="Print complete provider request/response payloads to stdout",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.llm_trace and args.llm_trace_stdout:
        parser.error("--llm-trace and --llm-trace-stdout cannot be used together")
    return args


def resolve_llm_trace_mode(args: argparse.Namespace, config: LabConfig) -> str:
    if args.llm_trace:
        return "file"
    if args.llm_trace_stdout:
        return "stdout"
    return config.debug.llm_trace


def make_tracer(mode: str, run_dir: Path) -> LLMTracer:
    file_path = run_dir / "llm_trace.jsonl" if mode == "file" else None
    return LLMTracer(mode=mode, file_path=file_path)


def _write_summary(run_dir: Path, summary: dict) -> None:
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )


def run_stage_00(
    task: str,
    config,
    events: EventLogger,
    run_dir: Path,
    tracer: LLMTracer,
) -> None:
    events.emit(
        "run_started",
        stage="00_model_only",
        model_profile=config.model.profile,
        provider=config.model.provider,
        model=config.model.model,
    )
    events.emit("model_request", prompt_chars=len(task))

    model = create_model_client(config.model, tracer=tracer)
    result = model.generate(task)

    events.emit(
        "model_response",
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )

    (run_dir / "response.md").write_text(result.text, encoding="utf-8")
    _write_summary(
        run_dir,
        {
            "stage": "00_model_only",
            "model_profile": config.model.profile,
            "provider": config.model.provider,
            "model": config.model.model,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "outcome": "ungraded",
            "llm_trace_mode": tracer.mode,
        },
    )
    events.emit("run_finished", outcome="ungraded")
    emit_console(result.text)
    emit_console(f"\nRun artifacts: {run_dir}")


def run_agent_stage(
    stage: str,
    task: str,
    config,
    events: EventLogger,
    run_dir: Path,
    tracer: LLMTracer,
) -> None:
    events.emit(
        "run_started",
        stage=stage,
        model_profile=config.model.profile,
        provider=config.model.provider,
        model=config.model.model,
    )

    model = create_model_client(config.model, tracer=tracer)
    registry = ToolRegistry(
        config.repo_root,
        enabled_tools=STAGE_TOOLS[stage],
    )
    result: AgentRunResult = run_agent_loop(
        task=task,
        model=model,
        registry=registry,
        events=events,
        config=config,
    )

    (run_dir / "response.md").write_text(result.text, encoding="utf-8")
    _write_summary(
        run_dir,
        {
            "stage": stage,
            "model_profile": config.model.profile,
            "provider": config.model.provider,
            "model": config.model.model,
            "model_calls": result.model_calls,
            "tool_calls": result.tool_calls,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "outcome": result.outcome,
            "llm_trace_mode": tracer.mode,
            **({"error": result.error} if result.error else {}),
        },
    )
    events.emit("run_finished", outcome=result.outcome)
    emit_console(result.text)
    if result.error:
        emit_console(f"\nRun error: {result.error}")
    emit_console(f"\nRun artifacts: {run_dir}")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    task = args.task_file.read_text(encoding="utf-8")
    config = load_config()
    stage = infer_stage(args.task_file)
    trace_mode = resolve_llm_trace_mode(args, config)

    run_dir = new_run_dir(config.runs_dir)
    events = EventLogger(run_dir)
    tracer = make_tracer(trace_mode, run_dir)
    (run_dir / "task.md").write_text(task, encoding="utf-8")

    if stage in STAGE_TOOLS:
        run_agent_stage(stage, task, config, events, run_dir, tracer)
        return

    run_stage_00(task, config, events, run_dir, tracer)


if __name__ == "__main__":
    main()
