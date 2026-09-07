from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import load_config
from .events import EventLogger
from .model import create_model_client


def new_run_dir(runs_dir: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{stamp}-{uuid.uuid4().hex[:8]}"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_file", type=Path)
    args = parser.parse_args()

    task = args.task_file.read_text(encoding="utf-8")
    config = load_config()

    run_dir = new_run_dir(config.runs_dir)
    events = EventLogger(run_dir)

    (run_dir / "task.md").write_text(task, encoding="utf-8")

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

    summary = {
        "stage": "00_model_only",
        "model_profile": config.model.profile,
        "provider": config.model.provider,
        "model": config.model.model,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "outcome": "ungraded",
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    events.emit("run_finished", outcome="ungraded")
    print(result.text)
    print(f"\nRun artifacts: {run_dir}")


if __name__ == "__main__":
    main()
