from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TRACE_MODES = ("off", "file", "stdout")


def to_jsonable(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            return dump(mode="json", exclude_none=True)
        except TypeError:
            return dump()
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return str(value)


class LLMTracer:
    def __init__(self, mode: str, file_path: Path | None = None):
        if mode not in TRACE_MODES:
            raise ValueError(
                f"Invalid llm_trace mode {mode!r}. Expected one of: off, file, stdout"
            )
        if mode == "file" and file_path is None:
            raise ValueError("file trace mode requires file_path")
        self.mode = mode
        self.file_path = file_path

    def request(
        self,
        *,
        turn: int,
        provider: str,
        model: str,
        endpoint: str,
        payload: object,
    ) -> None:
        self._emit(
            record_type="request",
            turn=turn,
            provider=provider,
            model=model,
            endpoint=endpoint,
            payload=payload,
        )

    def response(
        self,
        *,
        turn: int,
        provider: str,
        model: str,
        endpoint: str,
        payload: object,
    ) -> None:
        self._emit(
            record_type="response",
            turn=turn,
            provider=provider,
            model=model,
            endpoint=endpoint,
            payload=payload,
        )

    def _emit(
        self,
        *,
        record_type: str,
        turn: int,
        provider: str,
        model: str,
        endpoint: str,
        payload: object,
    ) -> None:
        if self.mode == "off":
            return

        record: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": record_type,
            "turn": turn,
            "provider": provider,
            "model": model,
            "endpoint": endpoint,
            "payload": to_jsonable(payload),
        }

        if self.mode == "file":
            assert self.file_path is not None
            with self.file_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()
            return

        banner = (
            f"=== LLM {record_type.upper()} — TURN {turn} — "
            f"{provider.upper()} / {endpoint.upper()} ==="
        )
        print(banner)
        print()
        print(json.dumps(record, indent=2, ensure_ascii=False))
        print()
