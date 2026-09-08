from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from miniharness.tools import (
    EXPERIMENTER_ONLY_DENIED,
    MAX_TEST_OUTPUT_CHARS,
    STAGE_TOOLS,
    TRUNCATION_MARKER,
    ToolRegistry,
    truncate_output,
)
from miniharness.types import ToolCall


def _repo(enabled_tools: tuple[str, ...] | None = None) -> tuple[Path, ToolRegistry]:
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
    return root, ToolRegistry(root, enabled_tools=enabled_tools)


def _verify_repo() -> tuple[Path, ToolRegistry]:
    return _repo(enabled_tools=STAGE_TOOLS["02_verify_only_agent"])


def _isolated_repo(
    enabled_tools: tuple[str, ...] | None = None,
) -> tuple[Path, ToolRegistry]:
    root, registry = _repo(enabled_tools)
    (root / "lab" / "docs").mkdir(parents=True)
    (root / "lab" / "docs" / "agent_harness_lab_proposed_roadmap.md").write_text(
        "EXPERIMENTER_ROADMAP_SECRET_BODY\n",
        encoding="utf-8",
    )
    (root / "lab" / "specs").mkdir(parents=True)
    (root / "lab" / "specs" / "hidden_stage_spec.md").write_text(
        "EXPERIMENTER_SPEC_SECRET_BODY\n",
        encoding="utf-8",
    )
    (root / "runs").mkdir()
    (root / "runs" / "llm_trace.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("project guidance\n", encoding="utf-8")
    return root, registry


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
        self.assertNotIn("run_pytest", names)

    def test_stage_02_exposes_run_pytest(self) -> None:
        _root, registry = _verify_repo()
        names = [item.name for item in registry.definitions()]
        self.assertEqual(names, ["list_files", "read_file", "run_pytest"])
        self.assertNotIn("write_file", names)
        self.assertNotIn("shell", names)

    def test_stage_01_run_pytest_is_unknown(self) -> None:
        _root, registry = _repo()
        result = registry.execute(
            _call("run_pytest", target="fixtures/tiny_checkout/test_discount.py")
        )
        self.assertFalse(result.ok)
        self.assertIn("Unknown tool", result.output)


class RunPytestTests(unittest.TestCase):
    def test_valid_target_accepted(self) -> None:
        _root, registry = _verify_repo()
        result = registry.execute(
            _call("run_pytest", target="fixtures/tiny_checkout/test_discount.py")
        )
        self.assertTrue(result.ok)
        self.assertIn(
            "pytest target: fixtures/tiny_checkout/test_discount.py", result.output
        )
        self.assertIn("exit_code:", result.output)

    def test_node_selector_works(self) -> None:
        root, registry = _verify_repo()
        test_file = root / "fixtures" / "tiny_checkout" / "test_discount.py"
        test_file.write_text(
            "def test_percentage_discount():\n"
            "    assert True\n"
            "\n"
            "def test_other():\n"
            "    assert False\n",
            encoding="utf-8",
        )
        result = registry.execute(
            _call(
                "run_pytest",
                target=(
                    "fixtures/tiny_checkout/test_discount.py"
                    "::test_percentage_discount"
                ),
            )
        )
        self.assertTrue(result.ok)
        self.assertIn("exit_code: 0", result.output)
        self.assertIn("1 passed", result.output)
        self.assertNotIn("test_other", result.output)

    def test_empty_target_rejected(self) -> None:
        _root, registry = _verify_repo()
        result = registry.execute(_call("run_pytest", target=""))
        self.assertFalse(result.ok)
        self.assertIn("non-empty string", result.output)

    def test_missing_target_rejected(self) -> None:
        _root, registry = _verify_repo()
        result = registry.execute(ToolCall(id="call-1", name="run_pytest", arguments={}))
        self.assertFalse(result.ok)
        self.assertIn("non-empty string", result.output)

    def test_absolute_path_rejected(self) -> None:
        root, registry = _verify_repo()
        absolute = str(
            (root / "fixtures" / "tiny_checkout" / "test_discount.py").resolve()
        )
        result = registry.execute(_call("run_pytest", target=absolute))
        self.assertFalse(result.ok)
        self.assertIn("Absolute paths are not allowed", result.output)

    def test_repository_escape_rejected(self) -> None:
        _root, registry = _verify_repo()
        result = registry.execute(_call("run_pytest", target="../secret.py"))
        self.assertFalse(result.ok)
        self.assertIn("outside repository", result.output.lower())

    def test_pytest_flag_injection_rejected(self) -> None:
        _root, registry = _verify_repo()
        for target in (
            "-k",
            "--maxfail=1",
            "-c",
            "--rootdir=.",
            "fixtures/tiny_checkout/test_discount.py --maxfail=1",
            "fixtures/tiny_checkout/test_discount.py -k test_percentage_discount",
        ):
            with self.subTest(target=target):
                result = registry.execute(_call("run_pytest", target=target))
                self.assertFalse(result.ok)
                self.assertIn("Pytest flags are not allowed", result.output)

    def test_env_target_rejected(self) -> None:
        _root, registry = _verify_repo()
        result = registry.execute(_call("run_pytest", target=".env"))
        self.assertFalse(result.ok)
        self.assertIn(".env access denied", result.output)

    def test_passing_test_ok_true_exit_zero(self) -> None:
        root, registry = _verify_repo()
        (root / "tests_ok").mkdir()
        (root / "tests_ok" / "test_ok.py").write_text(
            "def test_ok():\n    assert True\n",
            encoding="utf-8",
        )
        result = registry.execute(_call("run_pytest", target="tests_ok/test_ok.py"))
        self.assertTrue(result.ok)
        self.assertIn("exit_code: 0", result.output)
        self.assertFalse((root / ".pytest_cache").exists())

    def test_failing_test_ok_true_exit_one(self) -> None:
        root, registry = _verify_repo()
        (root / "tests_fail").mkdir()
        (root / "tests_fail" / "test_fail.py").write_text(
            "def test_fail():\n    assert 190.0 == 180.0\n",
            encoding="utf-8",
        )
        result = registry.execute(_call("run_pytest", target="tests_fail/test_fail.py"))
        self.assertTrue(result.ok)
        self.assertIn("exit_code: 1", result.output)
        self.assertIn("190.0", result.output)
        self.assertIn("180.0", result.output)

    def test_timeout_returns_tool_failure(self) -> None:
        _root, registry = _verify_repo()
        with patch(
            "miniharness.tools.subprocess.run",
            side_effect=subprocess.TimeoutExpired(
                cmd=["python", "-m", "pytest"],
                timeout=30,
            ),
        ):
            result = registry.execute(
                _call("run_pytest", target="fixtures/tiny_checkout/test_discount.py")
            )
        self.assertFalse(result.ok)
        self.assertIn("pytest timed out after 30 seconds", result.output)

    def test_output_truncation(self) -> None:
        huge = "A" * (MAX_TEST_OUTPUT_CHARS + 5_000)
        truncated = truncate_output(huge)
        self.assertLessEqual(len(truncated), MAX_TEST_OUTPUT_CHARS)
        self.assertIn(TRUNCATION_MARKER, truncated)
        self.assertTrue(truncated.startswith("A"))
        self.assertTrue(truncated.endswith("A"))

        _root, registry = _verify_repo()
        fake = subprocess.CompletedProcess(
            args=["python", "-m", "pytest"],
            returncode=0,
            stdout=huge,
            stderr="",
        )
        with patch("miniharness.tools.subprocess.run", return_value=fake):
            result = registry.execute(
                _call("run_pytest", target="fixtures/tiny_checkout/test_discount.py")
            )
        self.assertTrue(result.ok)
        self.assertIn(TRUNCATION_MARKER, result.output)
        self.assertIn("exit_code: 0", result.output)


class ExperimentalIsolationTests(unittest.TestCase):
    def test_root_listing_hides_experimenter_roots(self) -> None:
        _root, registry = _isolated_repo()
        result = registry.execute(_call("list_files", path=".", max_depth=4))
        self.assertTrue(result.ok)
        self.assertNotIn("lab", result.output)
        self.assertNotIn("runs", result.output)
        self.assertNotIn("hidden_stage_spec.md", result.output)
        self.assertNotIn("agent_harness_lab_proposed_roadmap.md", result.output)
        self.assertIn("AGENTS.md", result.output)
        self.assertIn("fixtures/tiny_checkout/discount.py", result.output)

    def test_direct_lab_listing_denied(self) -> None:
        _root, registry = _isolated_repo()
        result = registry.execute(_call("list_files", path="lab"))
        self.assertFalse(result.ok)
        self.assertEqual(result.output, EXPERIMENTER_ONLY_DENIED)

    def test_direct_runs_listing_denied(self) -> None:
        _root, registry = _isolated_repo()
        result = registry.execute(_call("list_files", path="runs"))
        self.assertFalse(result.ok)
        self.assertEqual(result.output, EXPERIMENTER_ONLY_DENIED)

    def test_read_lab_file_denied(self) -> None:
        _root, registry = _isolated_repo()
        result = registry.execute(
            _call(
                "read_file",
                path="lab/docs/agent_harness_lab_proposed_roadmap.md",
            )
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.output, EXPERIMENTER_ONLY_DENIED)
        self.assertNotIn("EXPERIMENTER_ROADMAP_SECRET_BODY", result.output)

    def test_read_runs_file_denied(self) -> None:
        _root, registry = _isolated_repo()
        result = registry.execute(_call("read_file", path="runs/llm_trace.jsonl"))
        self.assertFalse(result.ok)
        self.assertEqual(result.output, EXPERIMENTER_ONLY_DENIED)

    def test_traversal_cannot_bypass_isolation(self) -> None:
        _root, registry = _isolated_repo()
        result = registry.execute(
            _call(
                "read_file",
                path="fixtures/../lab/docs/agent_harness_lab_proposed_roadmap.md",
            )
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.output, EXPERIMENTER_ONLY_DENIED)
        self.assertNotIn("EXPERIMENTER_ROADMAP_SECRET_BODY", result.output)

    def test_run_pytest_cannot_target_lab(self) -> None:
        _root, registry = _isolated_repo(
            enabled_tools=STAGE_TOOLS["02_verify_only_agent"]
        )
        with patch("miniharness.tools.subprocess.run") as mock_run:
            result = registry.execute(
                _call("run_pytest", target="lab/specs/hidden_stage_spec.md")
            )
        self.assertFalse(result.ok)
        self.assertEqual(result.output, EXPERIMENTER_ONLY_DENIED)
        mock_run.assert_not_called()

    def test_run_pytest_cannot_target_runs_via_traversal(self) -> None:
        _root, registry = _isolated_repo(
            enabled_tools=STAGE_TOOLS["02_verify_only_agent"]
        )
        with patch("miniharness.tools.subprocess.run") as mock_run:
            result = registry.execute(
                _call("run_pytest", target="fixtures/../runs/llm_trace.jsonl")
            )
        self.assertFalse(result.ok)
        self.assertEqual(result.output, EXPERIMENTER_ONLY_DENIED)
        mock_run.assert_not_called()

    def test_agent_facing_files_remain_available(self) -> None:
        _root, registry = _isolated_repo()
        agents = registry.execute(_call("read_file", path="AGENTS.md"))
        self.assertTrue(agents.ok)
        self.assertEqual(agents.output, "project guidance\n")

        discount = registry.execute(
            _call("read_file", path="fixtures/tiny_checkout/discount.py")
        )
        self.assertTrue(discount.ok)
        self.assertEqual(discount.output, "PRICE = 1\n")

        test_file = registry.execute(
            _call("read_file", path="fixtures/tiny_checkout/test_discount.py")
        )
        self.assertTrue(test_file.ok)
        self.assertIn("test_percentage_discount", test_file.output)

    def test_env_protection_still_distinct(self) -> None:
        _root, registry = _isolated_repo()
        result = registry.execute(_call("read_file", path=".env"))
        self.assertFalse(result.ok)
        self.assertEqual(result.output, ".env access denied")

    def test_stage_01_tool_set_unchanged(self) -> None:
        self.assertEqual(STAGE_TOOLS["01_read_only_agent"], ("list_files", "read_file"))
        _root, registry = _isolated_repo(
            enabled_tools=STAGE_TOOLS["01_read_only_agent"]
        )
        names = [item.name for item in registry.definitions()]
        self.assertEqual(names, ["list_files", "read_file"])

    def test_stage_02_tool_set_unchanged(self) -> None:
        self.assertEqual(
            STAGE_TOOLS["02_verify_only_agent"],
            ("list_files", "read_file", "run_pytest"),
        )
        _root, registry = _isolated_repo(
            enabled_tools=STAGE_TOOLS["02_verify_only_agent"]
        )
        names = [item.name for item in registry.definitions()]
        self.assertEqual(names, ["list_files", "read_file", "run_pytest"])


if __name__ == "__main__":
    unittest.main()
