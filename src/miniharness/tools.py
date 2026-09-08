from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from .types import ToolCall, ToolDefinition, ToolResult

SKIP_NAMES = {".env", ".venv", ".git", "__pycache__"}
MAX_FILE_CHARS = 200_000
MAX_TEST_OUTPUT_CHARS = 20_000
PYTEST_TIMEOUT_SECONDS = 30
TRUNCATION_MARKER = "... [output truncated by MiniHarness] ..."

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

RUN_PYTEST = ToolDefinition(
    name="run_pytest",
    description="Run pytest for a repository-relative test target and return the real test result.",
    parameters={
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": (
                    "Repository-relative pytest target, such as "
                    "'fixtures/tiny_checkout/test_discount.py' or "
                    "'fixtures/tiny_checkout/test_discount.py::test_percentage_discount'."
                ),
            }
        },
        "required": ["target"],
    },
)

DEFAULT_TOOLS = ("list_files", "read_file")
STAGE_TOOLS = {
    "01_read_only_agent": ("list_files", "read_file"),
    "02_verify_only_agent": ("list_files", "read_file", "run_pytest"),
}


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


def truncate_output(text: str, max_chars: int = MAX_TEST_OUTPUT_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    available = max_chars - len(TRUNCATION_MARKER)
    if available <= 0:
        return TRUNCATION_MARKER[:max_chars]
    head = available // 2
    tail = available - head
    return text[:head] + TRUNCATION_MARKER + text[-tail:]


def _display_stream(text: str) -> str:
    if not text:
        return "(empty)"
    return truncate_output(text)


def _validate_pytest_target(repo_root: Path, target: object) -> str:
    if not isinstance(target, str) or not target.strip():
        raise ToolError("Invalid arguments: target must be a non-empty string")

    target = target.strip()
    for token in target.split():
        if token.startswith("-"):
            raise ToolError("Pytest flags are not allowed")

    path_part, _sep, _selector = target.partition("::")
    path_part = path_part.strip()
    if not path_part:
        raise ToolError(
            "Invalid arguments: target must start with a repository-relative path"
        )
    if Path(path_part).is_absolute():
        raise ToolError("Absolute paths are not allowed")

    resolve_repo_path(repo_root, path_part)
    return target


def run_pytest(repo_root: Path, arguments: dict[str, Any]) -> str:
    target = _validate_pytest_target(repo_root, arguments.get("target"))

    if importlib.util.find_spec("pytest") is None:
        raise ToolError("pytest unavailable")

    argv = [
        sys.executable,
        "-m",
        "pytest",
        target,
        "-q",
        "-p",
        "no:cacheprovider",
    ]

    try:
        completed = subprocess.run(
            argv,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=PYTEST_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolError(
            f"pytest timed out after {PYTEST_TIMEOUT_SECONDS} seconds"
        ) from exc
    except OSError as exc:
        raise ToolError(f"Failed to start pytest: {exc}") from exc

    return (
        f"pytest target: {target}\n"
        f"exit_code: {completed.returncode}\n"
        f"\n"
        f"stdout:\n"
        f"{_display_stream(completed.stdout)}\n"
        f"\n"
        f"stderr:\n"
        f"{_display_stream(completed.stderr)}"
    )


class ToolRegistry:
    def __init__(
        self,
        repo_root: Path,
        enabled_tools: tuple[str, ...] | None = None,
    ):
        self.repo_root = repo_root.resolve()
        names = enabled_tools if enabled_tools is not None else DEFAULT_TOOLS
        handlers: dict[str, Callable[[dict[str, Any]], str]] = {
            "list_files": lambda args: list_files(self.repo_root, args),
            "read_file": lambda args: read_file(self.repo_root, args),
            "run_pytest": lambda args: run_pytest(self.repo_root, args),
        }
        definitions = {
            "list_files": LIST_FILES,
            "read_file": READ_FILE,
            "run_pytest": RUN_PYTEST,
        }
        unknown = [name for name in names if name not in handlers]
        if unknown:
            raise ValueError(f"Unknown tools: {', '.join(unknown)}")
        self._enabled = names
        self._handlers = {name: handlers[name] for name in names}
        self._definitions = [definitions[name] for name in names]

    def definitions(self) -> list[ToolDefinition]:
        return list(self._definitions)

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
