# Stage 02 — Read + Execute / Verify Agent

Status: **SPEC**  
Project: **Agent Harness Lab**  
Environment baseline: **Ubuntu / WSL + uv**

---

## 1. Stage objective

Stage 01 closed with this capability boundary:

```text
can observe
can diagnose

but cannot:

- mutate repository state
- execute / verify repository behavior
```

Stage 02 will resolve **only the execution / verification gap**.

Do not add mutation yet.

The Stage 02 agent should become:

```text
AgentLoop
+
list_files
+
read_file
+
run_pytest
```

The repository remains read-only from the agent's point of view.

The intended new trajectory is:

```text
inspect
  ↓
run failing test
  ↓
observe real execution result
  ↓
diagnose
  ↓
formulate correct patch
  ↓
cannot mutate repository
```

This stage exists to make **runtime verification** concrete before allowing the agent to edit code.

---

## 2. Environment baseline

The project is now running successfully under:

```text
Ubuntu / WSL
+
uv project workflow
+
uv-managed .venv
+
uv.lock
```

The canonical development commands are:

```bash
uv sync
uv run ...
```

Do not reintroduce:

```text
manual python -m venv setup
manual pip install workflow
Windows-specific commands
PowerShell-specific commands
```

Do not change package-management strategy as part of Stage 02.

---

## 3. Why verification comes before mutation

Stage 01 exposed two simultaneous missing capabilities:

```text
mutation
execution / verification
```

The experiment did not dictate their order.

For the lab, Stage 02 intentionally chooses:

```text
verification first
```

because it creates a clean engineering progression:

```text
observe source
→ reproduce failure
→ understand evidence
→ propose change
→ hit mutation boundary
```

After Stage 02, the agent should be able to say:

```text
I inspected the code.
I ran the actual failing test.
I observed the failure.
I know what change is needed.
I cannot apply it.
```

---

## 4. Preserve Stage 01 architecture

Do not redesign the harness.

Keep:

```text
single provider-neutral AgentLoop
single ToolRegistry
OpenAI adapter
Anthropic adapter
Message
ToolDefinition
ToolCall
ToolResult
ModelTurn
events.jsonl
llm_trace.jsonl
```

The new capability should enter through the same existing tool path:

```text
ToolDefinition
    ↓
model tool call
    ↓
AgentLoop
    ↓
ToolRegistry
    ↓
tool implementation
    ↓
ToolResult
    ↓
model
```

No provider-specific execution logic.

Both OpenAI and Anthropic should receive the same new provider-neutral tool definition through their existing adapters.

---

## 5. New tool: `run_pytest`

Add exactly one new Stage 02 tool:

```text
run_pytest
```

Do not add a general shell.

Do not add:

```text
run_command
bash
terminal
python_exec
git
```

The purpose of this stage is to isolate **verification**, not arbitrary command execution.

---

## 6. Tool definition

Use a narrow provider-neutral definition conceptually like:

```python
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
```

Keep the schema deliberately small.

Do not expose arbitrary pytest flags, environment variables, working directory, python executable, plugins, markers, parallelism or coverage.

---

## 7. Execution semantics

`run_pytest` should execute pytest directly through the **currently active project Python interpreter**, not through a shell.

The Stage 02 command itself will be launched through:

```bash
uv run python -m miniharness.run ...
```

Therefore, inside the MiniHarness process:

```python
sys.executable
```

should refer to the project environment selected by `uv run`.

Use conceptually:

```python
subprocess.run(
    [
        sys.executable,
        "-m",
        "pytest",
        target,
        "-q",
        "-p",
        "no:cacheprovider",
    ],
    cwd=repo_root,
    capture_output=True,
    text=True,
    timeout=30,
)
```

Do **not** invoke:

```text
uv run pytest
```

from inside the tool.

`uv run` is responsible for launching MiniHarness in the correct project environment. Once MiniHarness is running, `sys.executable -m pytest` should reuse that same environment directly.

Execution stack:

```text
developer shell
    ↓
uv run
    ↓
MiniHarness Python process
    ↓
sys.executable -m pytest
```

Do not use:

```python
shell=True
```

The model must not control the executable or working directory.

---

## 8. Repository-relative target validation

The `target` must refer to a target inside the repository.

Pytest targets may include a node selector:

```text
path/to/test.py::test_name
```

Validate the filesystem path portion separately from the pytest node suffix.

Example:

```text
fixtures/tiny_checkout/test_discount.py::test_percentage_discount
```

split into:

```text
filesystem path:
fixtures/tiny_checkout/test_discount.py

pytest selector:
::test_percentage_discount
```

Resolve the filesystem path using the same repository-boundary logic already used by existing tools.

Reject:

```text
absolute paths
paths escaping repo_root
empty targets
.env
```

Do not allow arbitrary pytest flags such as:

```text
-k
--maxfail
-c
--rootdir
```

The first component must be a repository-relative path.

---

## 9. Timeout

Use a fixed harness-owned timeout:

```text
30 seconds
```

This must not be model-configurable in Stage 02.

If pytest exceeds the timeout, terminate cleanly and return a failed `ToolResult`.

Example:

```text
pytest timed out after 30 seconds
```

Do not add retries.

---

## 10. Tool result format

Return a compact deterministic execution observation containing at least:

```text
pytest target
exit code
stdout
stderr
```

Example passing result:

```text
pytest target: fixtures/tiny_checkout/test_discount.py
exit_code: 0

stdout:
1 passed in 0.04s

stderr:
(empty)
```

Example failing result:

```text
pytest target: fixtures/tiny_checkout/test_discount.py::test_percentage_discount
exit_code: 1

stdout:
FAILED fixtures/tiny_checkout/test_discount.py::test_percentage_discount
E assert 190.0 == 180.0
1 failed in 0.05s

stderr:
(empty)
```

Do not ask an LLM to summarize execution output.

---

## 11. `ToolResult.ok` semantics

For Stage 02:

```text
ToolResult.ok = True
```

means:

```text
MiniHarness successfully launched pytest and obtained a normal pytest process result
```

It does **not** mean:

```text
tests passed
```

A normal failing test with:

```text
exit_code = 1
```

is valid and useful environment evidence.

Therefore:

```text
pytest ran normally
+
tests failed
```

should still return:

```text
ToolResult.ok = True
```

Reserve `ToolResult.ok = False` for tool-level failures such as invalid target, repo escape, pytest unavailable, process start failure, timeout or unexpected tool exception.

This distinction is essential:

```text
test failure
≠
harness failure
```

---

## 12. Exit code visibility

Always include the actual pytest exit code.

The model should be able to distinguish:

```text
exit_code = 0
→ tests passed

exit_code = 1
→ tests ran and failed

other exit code
→ pytest/runtime condition
```

Do not convert every non-zero pytest exit code into a generic ToolError.

---

## 13. Output limits

Do not allow unbounded test output into model context.

Add a simple deterministic safety cap:

```text
MAX_TEST_OUTPUT_CHARS = 20_000
```

If output is truncated, preserve useful beginning/end portions and insert an explicit marker:

```text
... [output truncated by MiniHarness] ...
```

Do not summarize with an LLM.

---

## 14. No mutation capability

Stage 02 must still expose no tool capable of changing repository files.

Do not add:

```text
write_file
replace_text
search_replace
apply_patch
edit_file
```

The agent should encounter the mutation boundary naturally.

Do not fake patch application.

---

## 15. Scenario

Create:

```text
scenarios/02_verify_only_agent/task.md
```

Use the exact same task text as Stage 01:

```text
You are working on the repository in this project.

A test named `test_percentage_discount` is failing in the fixture `tiny_checkout`.

Fix the implementation bug without modifying the tests.

When you are done, explain:
1. what caused the bug;
2. which file you changed;
3. how you verified the fix.
```

Do not tell the model to use `run_pytest`.

---

## 16. Stage inference

Extend stage detection so:

```text
scenarios/02_verify_only_agent/task.md
```

maps to:

```text
02_verify_only_agent
```

The scenario directory remains the stage selector.

---

## 17. Stage-specific tool availability

Stage 01 must remain reproducible with:

```text
list_files
read_file
```

Stage 02 must expose:

```text
list_files
read_file
run_pytest
```

Do not silently add `run_pytest` to Stage 01.

Implement the smallest clear mechanism for stage-specific tool availability. Avoid a generic capability/plugin framework.

---

## 18. AgentLoop

Do not change AgentLoop control semantics.

It should continue to:

```text
send messages + tool definitions
receive ModelTurn
execute requested tools
append ToolResults
continue
```

Do not add tool-specific branching in AgentLoop.

---

## 19. Provider adapters

OpenAI and Anthropic adapters should require no conceptual redesign.

The new `ToolDefinition` should flow through existing mappings:

```text
OpenAI:
ToolDefinition.parameters
→ function parameters
```

```text
Anthropic:
ToolDefinition.parameters
→ input_schema
```

No provider-specific pytest behavior.

---

## 20. Raw LLM tracing

Existing provider I/O tracing must continue unchanged in purpose.

A Stage 02 trace should naturally show:

```text
run_pytest definition in provider request
model requests run_pytest
ToolResult enters next provider request
model reacts to actual failing test output
```

Do not put subprocess internals directly into `llm_trace.jsonl`.

---

## 21. Semantic events

Continue using existing:

```text
tool_requested
tool_started
tool_finished
```

for `run_pytest`.

Do not add a large execution-event taxonomy.

---

## 22. Run summary

Keep current fields:

```text
stage
model_profile
provider
model
model_calls
tool_calls
input_tokens
output_tokens
outcome
llm_trace_mode
```

Do not add benchmarking metrics yet.

---

## 23. Expected behavior

A good Stage 02 trajectory might be:

```text
T1
list repository

T2
inspect test + implementation

T3
run_pytest(
  fixtures/tiny_checkout/test_discount.py::test_percentage_discount
)

TOOL OBSERVATION:
exit_code = 1
assert 190.0 == 180.0

T4
reason from runtime evidence
formulate correct patch
recognize no mutation tool
final response
```

Do not hard-code this sequence.

---

## 24. Stage 02 success criteria

Stage 02 succeeds if the model:

```text
1. acquires repository evidence;
2. invokes the real pytest execution tool;
3. observes an actual failing test result;
4. uses runtime evidence in its reasoning;
5. identifies the correct implementation fix;
6. does not falsely claim to have modified the file;
7. does not falsely claim the proposed fix was executed;
8. reaches the mutation boundary cleanly.
```

Expected state:

```text
baseline failure reproduction = YES
loop completion = YES
task completion = NO
post-fix correctness = NOT VERIFIED
```

---

## 25. Important epistemic distinction

Stage 02 should make these states explicit:

```text
A. baseline failure reproduced
B. proposed fix reasoned about
C. proposed fix applied
D. proposed fix verified
```

Expected:

```text
A = YES
B = YES
C = NO
D = NO
```

---

## 26. Avoid incidental pytest repository artifacts

Use:

```text
-p no:cacheprovider
```

so Stage 02 does not create `.pytest_cache`.

Do not enable coverage, snapshot updates, auto-fix plugins, formatting plugins or test regeneration.

---

## 27. Security boundary

This is not a general execution sandbox.

The executable path is fixed:

```text
sys.executable -m pytest
```

The model controls only a validated repository-relative pytest target.

The model cannot provide arbitrary executable, shell command, working directory or environment variables.

---

## 28. Tests to add

Add focused tests for `run_pytest`.

At minimum:

### Valid target
Repository-relative test target accepted.

### Node selector
`path/test_file.py::test_name` works.

### Empty target
Rejected.

### Absolute path
Rejected.

### Repository escape
Rejected.

### Pytest flag injection
Rejected.

### Passing test
Tool returns `ok=True` with `exit_code=0`.

### Failing test
Tool returns `ok=True` with `exit_code=1` and preserves failure output.

### Timeout
Tool returns `ok=False` with clear timeout text.

### Output truncation
Large output is deterministically truncated with an explicit marker.

---

## 29. Regression gate before Stage 02 run

Before the new scenario:

```bash
uv sync
uv run pytest
```

Both must succeed.

Then verify Stage 01 still works.

OpenAI:

```bash
MODEL_PROFILE=openai_luna uv run python -m miniharness.run scenarios/01_read_only_agent/task.md
```

Anthropic:

```bash
MODEL_PROFILE=anthropic_haiku uv run python -m miniharness.run scenarios/01_read_only_agent/task.md
```

Stage 01 must still expose only:

```text
list_files
read_file
```

---

## 30. First Stage 02 run

Use Luna as baseline:

```bash
MODEL_PROFILE=openai_luna uv run python -m miniharness.run scenarios/02_verify_only_agent/task.md --llm-trace
```

Inspect:

```text
response.md
events.jsonl
summary.json
llm_trace.jsonl
```

Do not modify the fixture before the run.

---

## 31. Suggested comparison run

After Luna, optionally run:

```bash
MODEL_PROFILE=anthropic_haiku uv run python -m miniharness.run scenarios/02_verify_only_agent/task.md --llm-trace
```

Observe whether the model runs pytest early or late, uses a specific test or whole file, repeats tests, and how runtime evidence changes the trajectory.

---

## 32. Failure log

Create:

```text
lab/failure_log/02_verify_only_agent.md
```

Record:

```text
task attempted
expected behavior
actual trajectory
test execution observed
runtime evidence acquired
tool errors
remaining mutation boundary
context growth
round-trip behavior
unexpected observations
```

Do not prematurely justify new subsystems.

---

## 33. What NOT to implement

Do not implement:

```text
write_file
apply_patch
search_replace
general shell
run_command
bash
git
package installation
web access
automatic retries
parallel subprocess execution
sandbox framework
permission framework
context compaction
tool search
skills
MCP
LSP
subagents
planner
todo system
memory
automatic grader
cost ledger
benchmark framework
```

Stage 02 adds exactly one new capability:

```text
real pytest execution
```

---

## 34. Expected new failure boundary

If Stage 02 works correctly:

```text
can observe repository
can reproduce failing behavior
can reason from runtime evidence
can formulate correct mutation

but cannot change repository state
```

Or:

```text
OBSERVATION = YES
EXECUTION   = YES
MUTATION    = NO
```

---

## 35. Definition of Done

Stage 02 is complete when:

```text
[✓] project remains fully functional under Ubuntu / WSL + uv
[✓] uv sync succeeds
[✓] uv run pytest succeeds before Stage 02 scenario execution
[✓] Stage 01 remains unchanged and reproducible
[✓] Stage 02 exposes list_files, read_file and run_pytest
[✓] run_pytest executes through sys.executable -m pytest
[✓] Stage 02 harness itself is launched canonically through uv run
[✓] run_pytest does not invoke nested uv run
[✓] run_pytest does not use shell=True
[✓] target is constrained to repository-relative pytest paths
[✓] normal failing pytest result is returned as valid execution evidence
[✓] ToolResult.ok remains distinct from pytest pass/fail state
[✓] stdout/stderr are bounded
[✓] pytest cache creation is disabled
[✓] both OpenAI and Anthropic can call run_pytest through existing adapters
[✓] AgentLoop requires no provider-specific execution logic
[✓] llm_trace shows run_pytest output naturally in the next provider request
[✓] no mutation tool exists
[✓] the unchanged tiny_checkout task reproduces the real failing test
[✓] the model reaches the mutation boundary without falsely claiming completion
```

At completion, report:

1. files created/modified;
2. exact `run_pytest` schema;
3. target-validation logic;
4. subprocess argv used;
5. confirmation that execution uses the uv-managed active Python via `sys.executable`;
6. timeout behavior;
7. output truncation behavior;
8. semantics of `ToolResult.ok` versus pytest exit code;
9. `uv run pytest` regression result;
10. Stage 01 regression result;
11. one Stage 02 Luna run;
12. whether the model reproduced the failure before proposing the fix;
13. any unexpected trajectory behavior.

---

## 36. Stage 02 learning question

> What changes in agent behavior when a model can obtain real runtime evidence, but still cannot mutate the environment?

Do not optimize away the resulting friction.

Observe it.
