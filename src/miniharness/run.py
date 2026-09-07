from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .agent import run_agent_loop
from .config import load_config
from .events import EventLogger
from .model import create_model_client
from .tools import ToolRegistry
from .types import AgentRunResult


def new_run_dir(runs_dir: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{stamp}-{uuid.uuid4().hex[:8]}"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def infer_stage(task_file: Path) -> str:
    if task_file.resolve().parent.name == "01_read_only_agent":
        return "01_read_only_agent"
    return "00_model_only"


def _write_summary(run_dir: Path, summary: dict) -> None:
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )


def run_stage_00(task: str, config, events: EventLogger, run_dir: Path) -> None:
    events.emit(
        "run_started",
        stage="00_model_only",
        model_profile=config.model.profile,
        provider=config.model.provider,
        model=config.model.model,
    )
    events.emit("model_request", prompt_chars=len(task))

    model = create_model_client(config.model)
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
        },
    )
    events.emit("run_finished", outcome="ungraded")
    print(result.text)
    print(f"\nRun artifacts: {run_dir}")


def run_stage_01(task: str, config, events: EventLogger, run_dir: Path) -> None:
    events.emit(
        "run_started",
        stage="01_read_only_agent",
        model_profile=config.model.profile,
        provider=config.model.provider,
        model=config.model.model,
    )

    model = create_model_client(config.model)
    registry = ToolRegistry(config.repo_root)
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
            "stage": "01_read_only_agent",
            "model_profile": config.model.profile,
            "provider": config.model.provider,
            "model": config.model.model,
            "model_calls": result.model_calls,
            "tool_calls": result.tool_calls,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "outcome": result.outcome,
            **({"error": result.error} if result.error else {}),
        },
    )
    events.emit("run_finished", outcome=result.outcome)
    print(result.text)
    if result.error:
        print(f"\nRun error: {result.error}")
    print(f"\nRun artifacts: {run_dir}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_file", type=Path)
    args = parser.parse_args()

    task = args.task_file.read_text(encoding="utf-8")
    config = load_config()
    stage = infer_stage(args.task_file)

    run_dir = new_run_dir(config.runs_dir)
    events = EventLogger(run_dir)
    (run_dir / "task.md").write_text(task, encoding="utf-8")

    if stage == "01_read_only_agent":
        run_stage_01(task, config, events, run_dir)
        return

    run_stage_00(task, config, events, run_dir)


if __name__ == "__main__":
    main()
