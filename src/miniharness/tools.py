from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .types import ToolCall, ToolDefinition, ToolResult

SKIP_NAMES = {".env", ".venv", ".git", "__pycache__"}
MAX_FILE_CHARS = 200_000

LIST_FILES = ToolDefinition(
    name="list_files",
    description="List files and directories under a repository-relative path.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Repository-relative path to list.",
            },
            "max_depth": {
                "type": "integer",
                "description": "How many directory levels to descend from path.",
            },
        },
        "required": ["path"],
    },
)

READ_FILE = ToolDefinition(
    name="read_file",
    description="Read the contents of a repository-relative text file.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Repository-relative path of the text file to read.",
            },
        },
        "required": ["path"],
    },
)


class ToolError(Exception):
    pass


def resolve_repo_path(repo_root: Path, path: str) -> Path:
    if not isinstance(path, str) or not path.strip():
        raise ToolError("Invalid arguments: path must be a non-empty string")

    root = repo_root.resolve()
    candidate = (root / path).resolve()

    if not candidate.is_relative_to(root):
        raise ToolError("Path outside repository")

    if candidate.name.lower() == ".env":
        raise ToolError(".env access denied")

    return candidate


def _require_string(arguments: dict[str, Any], name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"Invalid arguments: {name} must be a non-empty string")
    return value


def _optional_int(arguments: dict[str, Any], name: str, default: int) -> int:
    if name not in arguments:
        return default
    value = arguments[name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolError(f"Invalid arguments: {name} must be an integer")
    if value < 0:
        raise ToolError(f"Invalid arguments: {name} must be >= 0")
    return value


def list_files(repo_root: Path, arguments: dict[str, Any]) -> str:
    path = _require_string(arguments, "path")
    max_depth = _optional_int(arguments, "max_depth", 2)
    target = resolve_repo_path(repo_root, path)

    if not target.exists():
        raise ToolError(f"File not found: {path}")

    root = repo_root.resolve()
    lines: list[str] = []

    def walk(current: Path, depth: int) -> None:
        rel = current.relative_to(root).as_posix()
        if current.is_dir():
            lines.append(rel + "/")
            if depth >= max_depth:
                return
            try:
                children = sorted(current.iterdir(), key=lambda p: p.name.lower())
            except OSError as exc:
                raise ToolError(f"Cannot list directory: {rel}: {exc}") from exc
            for child in children:
                if child.name.lower() in {name.lower() for name in SKIP_NAMES}:
                    continue
                walk(child, depth + 1)
            return
        lines.append(rel)

    walk(target, 0)
    return "\n".join(lines) if lines else "(empty)"


def read_file(repo_root: Path, arguments: dict[str, Any]) -> str:
    path = _require_string(arguments, "path")
    target = resolve_repo_path(repo_root, path)

    if not target.exists():
        raise ToolError(f"File not found: {path}")
    if target.is_dir():
        raise ToolError(f"Directory passed to read_file: {path}")

    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ToolError(f"File cannot be read as text: {path}") from exc
    except OSError as exc:
        raise ToolError(f"Cannot read file: {path}: {exc}") from exc

    if len(text) > MAX_FILE_CHARS:
        raise ToolError(
            f"File exceeds safety cap of {MAX_FILE_CHARS} characters: {path}"
        )
    return text


class ToolRegistry:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()
        self._handlers: dict[str, Callable[[dict[str, Any]], str]] = {
            "list_files": lambda args: list_files(self.repo_root, args),
            "read_file": lambda args: read_file(self.repo_root, args),
        }

    def definitions(self) -> list[ToolDefinition]:
        return [LIST_FILES, READ_FILE]

    def execute(self, call: ToolCall) -> ToolResult:
        handler = self._handlers.get(call.name)
        if handler is None:
            return ToolResult(
                tool_call_id=call.id,
                ok=False,
                output=f"Unknown tool: {call.name}",
            )

        if not isinstance(call.arguments, dict):
            return ToolResult(
                tool_call_id=call.id,
                ok=False,
                output="Invalid arguments: expected an object",
            )

        try:
            output = handler(call.arguments)
        except ToolError as exc:
            return ToolResult(tool_call_id=call.id, ok=False, output=str(exc))
        except Exception as exc:
            return ToolResult(
                tool_call_id=call.id,
                ok=False,
                output=f"Tool error: {exc}",
            )

        return ToolResult(tool_call_id=call.id, ok=True, output=output)
