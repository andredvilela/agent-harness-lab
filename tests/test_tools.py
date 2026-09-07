from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miniharness.tools import ToolRegistry
from miniharness.types import ToolCall


def _repo() -> tuple[Path, ToolRegistry]:
    root = Path(tempfile.mkdtemp())
    (root / "fixtures" / "tiny_checkout").mkdir(parents=True)
    (root / "fixtures" / "tiny_checkout" / "discount.py").write_text(
        "PRICE = 1\n", encoding="utf-8"
    )
    (root / "fixtures" / "tiny_checkout" / "test_discount.py").write_text(
        "def test_percentage_discount():\n    pass\n",
        encoding="utf-8",
    )
    (root / ".env").write_text("OPENAI_API_KEY=secret\n", encoding="utf-8")
    (root / "notes.txt").write_text("hello\n", encoding="utf-8")
    return root, ToolRegistry(root)


def _call(name: str, **arguments) -> ToolCall:
    return ToolCall(id="call-1", name=name, arguments=arguments)


class ToolSafetyTests(unittest.TestCase):
    def test_list_files_lists_fixture(self) -> None:
        _root, registry = _repo()
        result = registry.execute(
            _call("list_files", path="fixtures/tiny_checkout", max_depth=2)
        )
        self.assertTrue(result.ok)
        self.assertIn("fixtures/tiny_checkout/discount.py", result.output)
        self.assertIn("fixtures/tiny_checkout/test_discount.py", result.output)

    def test_list_files_skips_env(self) -> None:
        _root, registry = _repo()
        result = registry.execute(_call("list_files", path=".", max_depth=1))
        self.assertTrue(result.ok)
        self.assertNotIn(".env", result.output)

    def test_list_files_cannot_escape_repo_root(self) -> None:
        _root, registry = _repo()
        result = registry.execute(_call("list_files", path="..", max_depth=1))
        self.assertFalse(result.ok)
        self.assertIn("outside repository", result.output.lower())

    def test_read_file_returns_text(self) -> None:
        _root, registry = _repo()
        result = registry.execute(
            _call("read_file", path="fixtures/tiny_checkout/discount.py")
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.output, "PRICE = 1\n")

    def test_read_file_cannot_escape_repo_root(self) -> None:
        root, registry = _repo()
        secret = root.parent / "secret.txt"
        secret.write_text("nope\n", encoding="utf-8")
        result = registry.execute(_call("read_file", path="../secret.txt"))
        self.assertFalse(result.ok)
        self.assertIn("outside repository", result.output.lower())

    def test_read_file_cannot_read_env(self) -> None:
        _root, registry = _repo()
        result = registry.execute(_call("read_file", path=".env"))
        self.assertFalse(result.ok)
        self.assertIn(".env access denied", result.output)

    def test_read_file_rejects_directory(self) -> None:
        _root, registry = _repo()
        result = registry.execute(_call("read_file", path="fixtures/tiny_checkout"))
        self.assertFalse(result.ok)
        self.assertIn("Directory passed to read_file", result.output)

    def test_read_file_missing_path(self) -> None:
        _root, registry = _repo()
        result = registry.execute(_call("read_file", path="nope.py"))
        self.assertFalse(result.ok)
        self.assertIn("File not found", result.output)

    def test_unknown_tool_returns_error(self) -> None:
        _root, registry = _repo()
        result = registry.execute(_call("shell", command="ls"))
        self.assertFalse(result.ok)
        self.assertIn("Unknown tool", result.output)

    def test_invalid_arguments_return_error(self) -> None:
        _root, registry = _repo()
        result = registry.execute(ToolCall(id="call-1", name="read_file", arguments={}))
        self.assertFalse(result.ok)
        self.assertIn("Invalid arguments", result.output)

    def test_registry_has_only_read_tools(self) -> None:
        _root, registry = _repo()
        names = {item.name for item in registry.definitions()}
        self.assertEqual(names, {"list_files", "read_file"})
        self.assertNotIn("write_file", names)
        self.assertNotIn("shell", names)


if __name__ == "__main__":
    unittest.main()
