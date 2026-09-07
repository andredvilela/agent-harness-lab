# Stage 01 — Read-Only Agent
## Agent Loop + Tool Interface + `list_files` + `read_file`

Status: **SPEC**  
Project: **Agent Harness Lab**

---

## 1. Purpose

Stage 01 introduces the first real harness primitive.

Stages 00A and 00B established that the model can reason about what it wants to do, but cannot interact with the repository because the harness exposes no executable action channel.

The observed failure was:

```text
TASK
  ↓
MODEL
  ↓
understands that repository inspection is required
  ↓
NO EXECUTABLE TOOL CHANNEL
  ↓
BLOCKED
```

Stage 01 must resolve **only that specific limitation**.

The new system should allow the model to inspect the repository through a deliberately tiny, read-only action space.

The target architecture is:

```text
                ┌─────────────┐
                │    TASK     │
                └──────┬──────┘
                       │
                       ▼
                ┌─────────────┐
                │    MODEL    │
                └──────┬──────┘
                       │
             final text│tool call
                ┌──────┴───────┐
                │              │
                ▼              ▼
             FINISH       TOOL DISPATCH
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
               list_files             read_file
                    │                     │
                    └──────────┬──────────┘
                               ▼
                          observation
                               │
                               └──────────→ MODEL
```

The objective is **not** to fix the checkout bug yet.

The objective is:

> Give the model the ability to inspect the repository and observe what new execution barrier appears next.

---

## 2. Didactic hypothesis

Stage 00 demonstrated:

```text
Model capability ≠ Harness capability
```

Stage 01 tests the next hypothesis:

```text
If the harness provides perception,
the model can acquire evidence from the environment,
but remains unable to modify or verify the repository.
```

Expected result:

```text
task
  ↓
model
  ↓
list/read
  ↓
understands actual bug
  ↓
tries to proceed
  ↓
cannot edit and/or verify
  ↓
BLOCKED AT A NEW BOUNDARY
```

The desired outcome is therefore not necessarily task success.

A successful Stage 01 experiment is one in which:

1. the model successfully requests repository observations;
2. the harness executes those requests;
3. the observations are returned to the model;
4. the model uses them to understand the actual implementation;
5. execution eventually reaches a new barrier caused by a capability that still does not exist.

---

## 3. Scope

Implement only these new concepts:

```text
AgentLoop
ToolCall
ToolResult
Tool interface / tool definition
ToolRegistry or minimal dispatcher
list_files
read_file
multi-turn model conversation
tool telemetry
```

The implementation should be deliberately minimal.

Do not attempt production-grade abstraction.

---

## 4. Preserve the Stage 00 experiment

The existing Stage 00 behavior must remain reproducible.

Do not modify:

```text
scenarios/00_model_only/task.md
fixtures/tiny_checkout/
failure_log/00_model_only.md
failure_log/00b_model_behavior_survey.md
```

Do not migrate or rewrite historical run artifacts.

Stage 01 should use a new scenario directory:

```text
scenarios/01_read_only_agent/
```

Create:

```text
scenarios/01_read_only_agent/task.md
```

with the same task text:

```text
You are working on the repository in this project.

A test named `test_percentage_discount` is failing in the fixture `tiny_checkout`.

Fix the implementation bug without modifying the tests.

When you are done, explain:
1. what caused the bug;
2. which file you changed;
3. how you verified the fix.
```

This is intentional.

The difference between Stage 00 and Stage 01 must come from harness capability, not prompt changes.

---

## 5. Model baseline

Use one baseline model for Stage 01 implementation and first execution.

Default profile:

```text
openai_luna
```

Do not run the full Stage 00B model survey automatically.

The purpose of Stage 01 is to understand the harness primitive, not compare models.

The model/provider abstraction created in Stage 00B must continue to work.

Do not remove Anthropic support.

---

## 6. Core architectural change

Stage 00 behaves approximately like:

```python
response = model.generate(prompt)
return response
```

Stage 01 must introduce an explicit agent loop.

Conceptually:

```python
messages = [user_task]

while True:
    response = model.generate(
        messages=messages,
        tools=tools,
    )

    if response has no tool calls:
        return final response

    append model response to conversation

    for tool_call in response.tool_calls:
        result = tool_registry.execute(tool_call)
        append tool result to conversation
```

The exact provider APIs may differ.

The important conceptual ownership is:

> The MiniHarness owns the loop.

Do not hide the loop inside a third-party agent framework.

---

## 7. Conversation representation

Stage 00's:

```python
generate(prompt: str)
```

is no longer sufficient.

Generalize the model interface only as much as necessary for:

```text
multi-turn messages
+
tool definitions
+
structured tool calls
+
tool results
```

Create simple provider-neutral internal types.

Suggested minimal concepts:

```python
Message
ToolDefinition
ToolCall
ToolResult
ModelTurn
```

Do not create a large message framework.

A reasonable shape is conceptually:

```python
@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass(frozen=True)
class ModelTurn:
    text: str
    tool_calls: list[ToolCall]
    input_tokens: int | None
    output_tokens: int | None
```

The internal representation should be provider-neutral enough that both OpenAI and Anthropic adapters can map to it.

However, do not over-generalize edge cases that have not appeared yet.

---

## 8. Provider adapters

Both existing providers should remain structurally supported:

```text
OpenAI
Anthropic
```

Stage 01 must add tool-calling support to the provider adapters in the smallest reasonable way.

The harness should expose the same two tool concepts to either provider:

```text
list_files
read_file
```

Provider-specific wire formats should remain inside the provider adapter.

The rest of the harness should not need to know whether the model is OpenAI or Anthropic.

Conceptually:

```text
MiniHarness ToolDefinition
          │
          ├── OpenAI adapter → OpenAI tool schema
          │
          └── Anthropic adapter → Anthropic tool schema
```

and:

```text
provider response
       │
       ▼
provider adapter
       │
       ▼
ToolCall(name, arguments, id)
```

Do not introduce LiteLLM or another provider-normalization library.

Understanding this adapter boundary is part of the exercise.

---

## 9. Tool 1 — `list_files`

Implement a deliberately simple read-only repository listing tool.

Suggested contract:

```text
name:
list_files

purpose:
List files and directories under a repository-relative path.

arguments:
path: string
max_depth: integer
```

Example:

```json
{
  "path": "fixtures/tiny_checkout",
  "max_depth": 2
}
```

Result should be deterministic plain text or a simple structured object.

Choose the simpler implementation.

Do not add:

```text
glob syntax
semantic search
regex
gitignore awareness beyond trivial needs
file metadata
sizes
hashes
timestamps
```

unless required for safe operation.

---

## 10. Tool 2 — `read_file`

Implement a simple read-only text file tool.

Suggested contract:

```text
name:
read_file

purpose:
Read the contents of a repository-relative text file.

arguments:
path: string
```

Example:

```json
{
  "path": "fixtures/tiny_checkout/discount.py"
}
```

Return the textual contents.

No line-range support is required yet.

No chunking is required yet.

No binary support is required.

No automatic truncation strategy is required beyond a simple hard safety cap if necessary.

If a file cannot be read as text, return a clear tool error.

---

## 11. Repository boundary

The tools must be restricted to the lab repository root.

The model must not be able to read:

```text
../
absolute paths outside the project
.env
API keys
credentials
```

At minimum, normalize the requested path and verify that the resolved path remains inside the configured repository root.

Explicitly deny `.env`.

This is not intended to become the full permissions system.

It is basic implementation safety required to expose filesystem reading at all.

Do not create:

```text
PermissionEngine
allow/ask/deny policy framework
sandbox
OS isolation
```

Those belong to a later stage.

---

## 12. Tool registry / dispatcher

Introduce the smallest useful dispatcher.

Conceptually:

```python
TOOLS = {
    "list_files": list_files,
    "read_file": read_file,
}
```

and:

```python
def execute_tool(call: ToolCall) -> ToolResult:
    ...
```

A class is acceptable if it improves clarity:

```python
class ToolRegistry:
    ...
```

but do not introduce plugin discovery, decorators, dependency injection, or dynamic loading.

The purpose of the registry is simply:

```text
tool name
   ↓
known implementation
   ↓
execute arguments
   ↓
return result/error
```

---

## 13. Tool errors

Tool execution can fail.

Represent failure explicitly.

Examples:

```text
file not found
path outside repository
.env access denied
directory passed to read_file
invalid arguments
unknown tool
```

Do not crash the entire process for a normal tool-use error.

Return the error to the model as an observation so it can react.

Conceptually:

```python
ToolResult(
    tool_call_id=...,
    ok=False,
    output="File not found: ..."
)
```

Do not build retry policies.

Let the model decide what to do after seeing the error.

---

## 14. Agent loop termination

The loop needs minimal termination protection.

Add a simple maximum number of model turns.

Configure it in `config.toml`.

Example:

```toml
[agent]
max_turns = 10
```

If the limit is reached:

```text
terminate run
mark outcome = max_turns_exceeded
```

This is not yet a sophisticated budget controller.

It is a guard against accidental infinite loops introduced by Stage 01 itself.

Do not add token budgets or dollar budgets yet.

---

## 15. Configuration

Extend `config.toml` minimally:

```toml
[lab]
runs_dir = "runs"
repo_root = "."

[agent]
max_turns = 10
```

Preserve existing model profiles.

Do not place secrets in `config.toml`.

`.env` remains for:

```text
OPENAI_API_KEY
ANTHROPIC_API_KEY
MODEL_PROFILE
```

---

## 16. Telemetry

Preserve the existing immutable run artifacts.

For Stage 01, add enough events to make the agent loop visible.

At minimum:

```text
run_started
model_request
model_response
tool_requested
tool_started
tool_finished
run_finished
```

Suggested fields:

### `model_request`

```text
turn
provider
model
message_count
available_tools
```

### `model_response`

```text
turn
input_tokens
output_tokens
text_present
tool_call_count
```

### `tool_requested`

```text
turn
tool_call_id
tool
arguments
```

### `tool_finished`

```text
turn
tool_call_id
tool
ok
output_chars
```

Do not log API keys.

Do not log `.env`.

For this stage, logging tool arguments and outputs is acceptable because the fixture is non-sensitive.

---

## 17. Run artifacts

Each Stage 01 run should continue creating:

```text
runs/<run-id>/
├── task.md
├── response.md
├── events.jsonl
└── summary.json
```

The final `response.md` should contain only the model's final textual answer.

`events.jsonl` should contain the complete execution trajectory.

Add to `summary.json`:

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
```

For `input_tokens` and `output_tokens`, aggregate provider-reported usage over all model turns.

No cost calculation yet.

---

## 18. Outcomes

Stage 01 makes `ungraded` less useful.

Introduce only a minimal execution outcome taxonomy:

```text
completed
max_turns_exceeded
error
```

Do not attempt to determine whether the repository task was correctly solved.

Since the agent cannot edit the repo, `completed` means:

> the model ended the conversation normally.

It does not mean:

> the bug was fixed.

Functional grading comes later.

---

## 19. Expected Stage 01 behavior

The likely trajectory is:

```text
task
  ↓
model asks to inspect repo
  ↓
list_files
  ↓
model reads test
  ↓
read_file(test_discount.py)
  ↓
model reads implementation
  ↓
read_file(discount.py)
  ↓
model understands actual bug
  ↓
model wants to edit and/or test
  ↓
no such capability exists
  ↓
blocked / asks for capability / returns proposed change
```

This is a hypothesis, not a behavior to hard-code.

Do not prompt the model to use tools in a particular sequence.

Do not tell it which files to inspect.

Do not mention the actual bug.

Let the tool descriptions and task drive the behavior.

---

## 20. New failure log

Create:

```text
failure_log/01_read_only_agent.md
```

using the existing failure-log template.

Do not pre-fill conclusions.

It should initially contain:

```text
# Stage 01 — Read-Only Agent

## Task attempted

## What I expected

## What actually happened

## Observable failure

## Why the current harness cannot overcome it

## Next primitive justified by this failure

## Minimal implementation idea

## What I learned

## Questions to investigate in frontier harnesses
```

We will fill it after the real execution.

---

## 21. Stage spec location

From now on, stage specifications live outside the README.

Create if needed:

```text
specs/
```

Store this specification as:

```text
specs/01_read_only_agent.md
```

The README should not receive a large new Stage 01 section.

At most, add a short navigation reference to `specs/`.

Do not duplicate this spec into README.

---

## 22. What NOT to implement

Stage 01 must NOT introduce:

```text
write_file
search_replace
apply_patch
edit tools
grep
search
shell
terminal
test execution
git commands
web access
AGENTS.md loading
project rules
system prompt engineering
context compaction
context summarization
retrieval
LSP
MCP
skills
plugins
hooks
subagents
planning mode
todo system
memory
session resume
permissions framework
sandbox
cost ledger
pricing
wire proxy
parallel tool execution
streaming
automatic retries
automatic graders
benchmark runner
TUI
ACP
IDE integration
```

Also do not add a broad generic shell tool as a shortcut for missing capabilities.

The whole point of Stage 01 is to experience the limitations of a **read-only action space**.

---

## 23. Do not help the model through the prompt

Do not change the task to say:

```text
Use list_files first.
Read discount.py.
Read test_discount.py.
You cannot edit files.
```

That would contaminate the experiment.

The model should discover the capabilities from the tool definitions and discover its limitations by attempting the task.

---

## 24. No frontier harness teardown yet

Do not inspect or copy the implementation of:

```text
Codex
Claude Code
Cursor
Grok Build
OpenCode
Qwen Code
```

as part of this implementation.

First implement the primitive naively.

First run it.

First observe how it fails.

Only after Stage 01 produces a concrete trajectory should we compare how frontier harnesses solve the same problems.

This preserves the pedagogical method:

```text
experience problem
→ implement naive primitive
→ observe behavior
→ inspect frontier implementations
```

---

## 25. Validation checklist

Before running the experiment, validate:

```text
[ ] Stage 00 OpenAI naked call still works
[ ] Stage 00 Anthropic naked call still works
[ ] Stage 01 uses the new agent loop
[ ] OpenAI adapter supports the two tools
[ ] Anthropic adapter supports the two tools
[ ] list_files cannot escape repo root
[ ] read_file cannot escape repo root
[ ] read_file cannot read .env
[ ] unknown tool returns a tool error rather than crashing
[ ] normal tool errors are returned to the model
[ ] max_turns terminates a runaway loop
[ ] events.jsonl exposes every model/tool transition
[ ] no edit capability exists
[ ] no shell capability exists
[ ] no search capability exists
[ ] Stage 00 task/fixture files were not altered
```

---

## 26. First experiment protocol

After implementation, run only the baseline first:

```powershell
$env:MODEL_PROFILE="openai_luna"
python -m miniharness.run scenarios/01_read_only_agent/task.md
```

Do not immediately run all four models.

Inspect:

```text
response.md
events.jsonl
summary.json
```

Questions to answer:

1. Did the model discover and use `list_files`?
2. Did it use `read_file`?
3. Did the tool requests contain sensible arguments?
4. Did it inspect the correct files?
5. Did it understand the actual bug?
6. How many model turns were required?
7. Did it repeat reads unnecessarily?
8. What did it attempt after understanding the bug?
9. What capability did it ask for next?
10. Did it falsely claim that it edited or verified anything?
11. Did any provider/tool normalization issue become visible?
12. What is the next concrete execution barrier?

Do not proceed to Stage 02 until the failure log is filled from this actual run.

---

## 27. Definition of Done

Stage 01 implementation is complete when:

```text
[✓] MiniHarness owns an explicit agent loop
[✓] model can issue structured tool requests
[✓] harness can execute list_files
[✓] harness can execute read_file
[✓] results return to the model as observations
[✓] OpenAI adapter maps tool calls correctly
[✓] Anthropic adapter maps tool calls correctly
[✓] agent cannot modify the repository
[✓] agent cannot execute shell commands
[✓] full trajectory is recorded in events.jsonl
[✓] loop has a simple max-turn guard
[✓] Stage 00 remains reproducible
[✓] Stage 01 scenario exists
[✓] Stage 01 failure-log template exists
```

The experiment itself is complete only after a real run demonstrates the next limitation.

---

## 28. Stage success criterion

Do not define Stage 01 success as:

```text
bug fixed
```

Define it as:

```text
The model successfully acquires repository evidence through
harness-executed read-only tools and reaches the next capability
boundary without the harness secretly providing capabilities
outside the Stage 01 scope.
```

This distinction is central to the lab.

---

## 29. Expected conceptual lesson

If Stage 01 behaves as expected, the progression becomes:

```text
STAGE 00
Model can reason
but cannot observe or act.

        ↓ add AgentLoop + read tools

STAGE 01
Model can reason and observe
but cannot change or verify the environment.

        ↓ next failure determines Stage 02
```

The Stage 02 primitive must be chosen only after observing the real Stage 01 run.
