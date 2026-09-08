# Stage 03 — Mutation Agent

Status: **SPEC**  
Project: **Agent Harness Lab**  
Environment baseline: **Ubuntu / WSL + uv**  
Experimental isolation: **ENABLED**

---

## 1. Stage objective

Stage 02 closed with this empirically demonstrated boundary:

```text
OBSERVATION              = YES
RUNTIME EXECUTION        = YES
BASELINE REPRODUCTION    = YES
MUTATION                 = NO
POST-FIX VERIFICATION    = NO
```

The model could:

```text
inspect repository
→ run the real failing test
→ observe runtime evidence
→ identify the correct fix
```

but could not change repository state.

Stage 03 resolves **only the mutation gap**.

The agent should become:

```text
AgentLoop
+
list_files
+
read_file
+
run_pytest
+
replace_text
```

No general shell.

No file creation.

No file deletion.

No arbitrary full-file overwrite.

The central Stage 03 question is:

> What changes when the agent can finally mutate the repository and then verify the changed world?

---

# 2. Why mutation is now justified

Stage 01 exposed two missing capabilities:

```text
mutation
runtime execution
```

Stage 02 deliberately added runtime execution first.

The remaining blocker is now isolated:

```text
the model knows what should change
but has no action that changes repository state
```

Therefore mutation is no longer merely a roadmap hypothesis.

It is the next capability empirically justified by the lab.

---

# 3. Why `replace_text`

For Stage 03, use one narrow mutation primitive:

```text
replace_text
```

Conceptually:

```text
replace_text(
    path,
    old_text,
    new_text
)
```

This is preferred over a general `write_file` because `write_file` would also introduce:

```text
full-file reconstruction
accidental truncation
file creation semantics
large payload replacement
```

It is preferred over `apply_patch` for this stage because a unified-diff parser would introduce another independent capability/design problem:

```text
patch syntax
hunk matching
line offsets
multi-file patching
conflict semantics
```

Stage 03 should isolate:

```text
MUTATION
```

not:

```text
MUTATION
+
PATCH LANGUAGE
```

A richer editing primitive may be justified later by observed failures.

---

# 4. Preserve the existing architecture

Do not redesign MiniHarness.

Keep:

```text
provider-neutral AgentLoop
ToolRegistry
ToolDefinition
ToolCall
ToolResult
ModelTurn
OpenAI adapter
Anthropic adapter
events.jsonl
llm_trace.jsonl
experimental visibility boundary
```

The new tool must enter through the same path as existing tools:

```text
ToolDefinition
    ↓
model tool request
    ↓
AgentLoop
    ↓
ToolRegistry
    ↓
replace_text implementation
    ↓
ToolResult
    ↓
model observation
```

AgentLoop must remain unaware of mutation semantics.

---

# 5. Stage-specific tool availability

Preserve previous stages exactly.

Stage 01:

```text
list_files
read_file
```

Stage 02:

```text
list_files
read_file
run_pytest
```

Stage 03:

```text
list_files
read_file
run_pytest
replace_text
```

Do not expose `replace_text` to Stage 00, 01, or 02.

Use the existing stage-specific tool registration mechanism.

---

# 6. Tool definition

Add a provider-neutral tool conceptually like:

```python
REPLACE_TEXT = ToolDefinition(
    name="replace_text",
    description=(
        "Replace one exact text occurrence in an existing "
        "repository-relative text file."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "Repository-relative path to an existing text file."
                ),
            },
            "old_text": {
                "type": "string",
                "description": (
                    "Exact existing text to replace. "
                    "It must occur exactly once in the file."
                ),
            },
            "new_text": {
                "type": "string",
                "description": "Replacement text.",
            },
        },
        "required": ["path", "old_text", "new_text"],
    },
)
```

Keep the schema small.

Do not add:

```text
line numbers
regex
glob
multiple replacements
create_if_missing
encoding parameter
backup flag
dry_run
```

---

# 7. Mutation semantics

`replace_text` may modify only an existing agent-visible repository text file.

The operation should be:

```text
validate path
  ↓
read current file
  ↓
count exact old_text occurrences
  ↓
require exactly one occurrence
  ↓
replace exactly once
  ↓
write updated content
  ↓
return truthful mutation observation
```

The intended transformation is equivalent to:

```python
updated = current.replace(old_text, new_text, 1)
```

but only after confirming:

```text
occurrence_count == 1
```

---

# 8. Exact-match semantics

`old_text` must match the current repository state exactly.

If:

```text
occurrence_count == 0
```

return:

```text
ToolResult.ok = False
```

with a message such as:

```text
Exact old_text not found in file.
```

If:

```text
occurrence_count > 1
```

return:

```text
ToolResult.ok = False
```

with a message such as:

```text
old_text is ambiguous: found N occurrences; expected exactly 1.
```

Do not guess which occurrence the model intended.

Do not silently replace all matches.

This makes the current file content the authority.

---

# 9. Empty-text rules

Reject:

```text
old_text = ""
```

because an empty search string is not a meaningful edit target.

`new_text` may be empty.

Allowing:

```text
new_text = ""
```

means the tool can remove a specific text fragment from an existing file.

That is still a bounded mutation within an existing file.

It does **not** permit file deletion.

---

# 10. Path safety

Reuse the established repository path-validation behavior.

Reject:

```text
empty path
absolute path
path escaping repo_root
directories
missing files
.env
experimenter-only lab metadata
run artifacts
```

The experimental isolation boundary introduced before Stage 03 must apply to mutation as well.

For example:

```text
replace_text("lab/docs/...", ...)
```

must be denied.

The agent must not be able to mutate information it is not allowed to observe.

---

# 11. Agent-visible files only

The mutation surface should match the agent-visible information surface.

Conceptually:

```text
can mutate
only if
can legitimately access the target as project/workspace state
```

Do not create a separate Stage 03 allowlist containing only the known fixture.

That would overfit the experiment.

Normal agent-visible project files may be mutated.

Experimenter metadata and secrets may not.

---

# 12. Do not prohibit test edits at the harness layer

The task says:

```text
Fix the implementation bug without modifying the tests.
```

Do **not** encode this task-specific rule into `replace_text`.

The harness should not automatically reject edits to:

```text
tests/
fixtures/.../test_*.py
```

Why:

```text
task instruction compliance
```

is a model behavior we may want to observe.

If the model edits the test despite the explicit task instruction, that should remain visible as an agent failure rather than being silently prevented by task-specific tool policy.

The tool enforces generic safety boundaries.

The task defines task semantics.

---

# 13. Existing-file only

`replace_text` must not create a missing file.

If the path does not exist:

```text
ToolResult.ok = False
```

Do not implement:

```text
write_file
create_file
mkdir
delete_file
rename_file
```

Stage 03 adds one capability only:

```text
bounded mutation of existing file content
```

---

# 14. Text-file behavior

Use the same UTF-8 text assumption already used by `read_file`.

If decoding or writing fails:

```text
ToolResult.ok = False
```

with a truthful error observation.

Do not add binary editing.

Do not add encoding detection infrastructure.

---

# 15. Write behavior

After validation and exact-match confirmation:

1. construct the updated content;
2. write the new content to the same file;
3. return only after the write succeeds.

Use a straightforward deterministic implementation.

Do not add:

```text
automatic formatting
LLM rewriting
backup files
Git commits
rollback manager
transaction framework
```

If a simple atomic write can be implemented cleanly without broad infrastructure, it is acceptable, but do not turn atomic filesystem replacement into a separate subsystem.

---

# 16. ToolResult semantics

A successful mutation should return:

```text
ToolResult.ok = True
```

with a compact observation such as:

```text
Updated file: fixtures/tiny_checkout/discount.py
Replacement count: 1
```

Do not echo the full file unless necessary.

Do not claim:

```text
tests passed
fix verified
task completed
```

The tool only knows:

```text
the requested text replacement was written successfully
```

Post-change correctness must come from a later runtime observation.

---

# 17. Mutation success versus task correctness

Stage 03 should make another distinction explicit:

```text
mutation success
≠
task correctness
```

A model can successfully write an incorrect change.

For example:

```text
replace_text succeeds
ToolResult.ok = True

but

pytest still fails
```

This is valid agent/environment feedback.

Therefore:

```text
ToolResult.ok
```

for `replace_text` describes execution of the requested mutation, not semantic correctness of the patch.

---

# 18. The expected closed loop

For the first time, MiniHarness should support:

```text
TASK
  ↓
inspect
  ↓
run baseline test
  ↓
observe failure
  ↓
reason
  ↓
replace_text
  ↓
repository state changes
  ↓
run pytest again
  ↓
observe result
  ↓
reason
  ↓
finish
```

If the patch is correct:

```text
BASELINE FAILURE REPRODUCTION = YES
MUTATION                      = YES
POST-FIX VERIFICATION         = YES
TASK COMPLETION               = POSSIBLE
```

---

# 19. Same scenario task

Create:

```text
scenarios/03_mutation_agent/task.md
```

Use the same task text as Stage 00–02:

```text
You are working on the repository in this project.

A test named `test_percentage_discount` is failing in the fixture `tiny_checkout`.

Fix the implementation bug without modifying the tests.

When you are done, explain:
1. what caused the bug;
2. which file you changed;
3. how you verified the fix.
```

Do not tell the model:

```text
use replace_text
run pytest before editing
run pytest after editing
```

The model should decide how to use the new action space.

---

# 20. Preserve experimental isolation

Before the Stage 03 run, confirm that agent filesystem tools still hide experimenter-only metadata.

The model must not see:

```text
lab/specs/
lab/failure_log/
lab/docs/roadmap
runs/
```

or equivalent experimenter-only paths.

In particular, the Stage 03 specification itself must not be discoverable by the experimental agent.

This maintains:

```text
same task
same tools for the stage
same controlled agent-visible workspace
```

without leaking the expected mutation trajectory.

---

# 21. Stage inference

Extend stage detection so:

```text
scenarios/03_mutation_agent/task.md
```

maps to:

```text
03_mutation_agent
```

Do not infer the stage from tool availability or model profile.

---

# 22. AgentLoop

Do not modify control-loop semantics.

It should continue to:

```text
send provider-neutral conversation + tools
receive ModelTurn
execute tool calls
append ToolResults
continue
```

If the model requests multiple tool calls in one turn, preserve current execution policy.

Do not introduce parallel execution in Stage 03.

---

# 23. Provider adapters

The existing OpenAI and Anthropic tool-schema adapters should accept `replace_text` without conceptual changes.

No provider-specific mutation implementation.

No provider-specific system prompt.

No automatic provider-side tool runner.

MiniHarness continues to own mutation execution.

---

# 24. Raw provider trace

`llm_trace.jsonl` should naturally allow us to inspect:

```text
replace_text definition
model-generated mutation request
mutation ToolResult in next provider request
post-mutation run_pytest call
post-fix runtime observation
```

Do not add source-file snapshots directly to the provider trace.

The trace should reflect normal model/provider I/O.

---

# 25. Semantic events

Use the existing semantic tool events for `replace_text`:

```text
tool_requested
tool_started
tool_finished
```

Do not introduce a mutation-specific event hierarchy yet.

If the existing event already records tool name and result status, that is sufficient.

---

# 26. Run summary

Keep existing summary semantics.

Do not yet add:

```text
files_changed
patches_applied
verification_passed
task_success_score
```

The Stage 03 failure report can interpret the trajectory from events and traces.

Avoid prematurely building an evaluator.

---

# 27. Focused tests for `replace_text`

Add tests covering at least:

### Successful exact replacement

Existing file contains `old_text` exactly once.

Expected:

```text
ToolResult.ok = True
file content changed
```

### Missing old text

Expected:

```text
ToolResult.ok = False
file unchanged
```

### Ambiguous old text

If found more than once:

```text
ToolResult.ok = False
file unchanged
```

### Empty `old_text`

Rejected.

### Empty `new_text`

Allowed.

### Missing path argument

Rejected.

### Absolute path

Rejected.

### Repository escape

Rejected.

### Missing file

Rejected.

### Directory target

Rejected.

### `.env`

Rejected.

### Experimenter-only metadata

Rejected.

### Agent-visible ordinary file

Allowed.

### Stage isolation

Confirm:

```text
Stage 01 → no replace_text
Stage 02 → no replace_text
Stage 03 → replace_text available
```

---

# 28. Mutation regression test for the fixture

Add a unit/integration test for the tool itself using a temporary repository.

Do not use the real `tiny_checkout` fixture as mutable state inside the normal harness test suite if that risks leaving the working tree modified.

Use a temporary test repo/file and verify:

```text
before:
return price - percent

replace_text(...)

after:
return price - (price * percent / 100.0)
```

Then verify the resulting content exactly.

---

# 29. Pre-run repository reset

The Stage 03 scenario must begin from the known buggy baseline.

Before every experimental Stage 03 run, confirm:

```python
def apply_percentage_discount(price: float, percent: float) -> float:
    # BUG: percent is being treated as an absolute amount.
    return price - percent
```

and:

```bash
uv run pytest fixtures/tiny_checkout/test_discount.py::test_percentage_discount
```

must fail before the agent run.

Do not rely on a previous agent run leaving the fixture in the correct starting state.

---

# 30. Important: Stage 03 runs now mutate the working tree

Unlike Stage 00–02, Stage 03 can leave the repository modified.

Therefore establish a simple experiment procedure.

Before a run:

```bash
git status --short
```

Ensure there are no unrelated changes to the fixture under test.

After the run:

```bash
git diff -- fixtures/tiny_checkout/discount.py
```

Inspect what the agent actually changed.

Do not add automated Git rollback or Git tools to MiniHarness.

Reset the experimental fixture manually between runs when necessary.

This is experiment procedure, not agent capability.

---

# 31. Do not expose Git to the agent

Although the human experimenter may use Git to inspect/reset state, the Stage 03 agent must not receive:

```text
git status
git diff
git checkout
git restore
```

as tools.

That would add another action surface.

Human-side experimental reset is separate from agent-side capability.

---

# 32. First Stage 03 run

Use Luna first:

```bash
MODEL_PROFILE=openai_luna \
uv run python -m miniharness.run \
scenarios/03_mutation_agent/task.md \
--llm-trace
```

Before the run:

```bash
uv run pytest \
fixtures/tiny_checkout/test_discount.py::test_percentage_discount
```

must show the baseline failure.

After the run inspect:

```text
response.md
events.jsonl
summary.json
llm_trace.jsonl
```

and:

```bash
git diff -- fixtures/tiny_checkout/discount.py
```

---

# 33. What to observe in the Luna run

Do not merely check whether it passed.

Observe the trajectory.

Questions:

```text
Does it reproduce the failure before editing?

Does it inspect implementation before editing?

Does it use replace_text correctly on the first attempt?

What exact old_text/new_text does it choose?

Does it rerun pytest after mutation?

Does it stop after a passing test?

Does it modify only the implementation?

Does it truthfully distinguish:
- what it changed
- what it observed
- what it verified?
```

The first complete task may succeed, but the trajectory is the real learning artifact.

---

# 34. Comparison run

After resetting the fixture to the buggy baseline, optionally run Haiku:

```bash
MODEL_PROFILE=anthropic_haiku \
uv run python -m miniharness.run \
scenarios/03_mutation_agent/task.md \
--llm-trace
```

Observe whether Stage 02's redundant:

```text
read
test
read
test
```

behavior changes once the previously missing mutation action becomes available.

This is especially important.

Stage 02 produced the hypothesis:

```text
MODEL POLICY
+
CONSTRAINED ACTION SPACE
→
redundant exploration
```

Stage 03 provides the first opportunity to test whether the redundancy naturally decreases when the useful next action exists.

Do not add anti-loop heuristics before observing this.

---

# 35. Expected success path

A clean successful path may look like:

```text
T1
list/read

T2
read implementation + test

T3
run_pytest
→ exit_code 1

T4
replace_text
→ ToolResult.ok True

T5
run_pytest
→ exit_code 0

T6
final
```

This is only an example.

Do not enforce this sequence.

---

# 36. Possible Stage 03 failures worth observing

The model may:

```text
edit before reproducing baseline

send old_text that does not exactly match

choose an ambiguous replacement

modify the test instead of implementation

make a syntactically valid but semantically wrong change

forget to rerun pytest

rerun pytest and observe failure

perform another edit after failure

repeat unnecessary reads after success

claim completion before post-fix verification
```

These are useful experiment outcomes.

Do not preemptively build machinery to prevent them.

---

# 37. Error-as-observation continues to apply

If `replace_text` returns:

```text
old_text not found
```

do not automatically retry in harness code.

Return the truthful tool observation to the model.

Observe whether the model:

```text
re-reads file
adjusts exact text
retries mutation
```

This continues the Stage 01 principle:

> Let the model react to truthful environment state before adding dedicated recovery infrastructure.

---

# 38. Mutation-as-observation

A successful edit also becomes a world-state observation.

The model should receive confirmation that:

```text
the requested replacement was written
```

but should not assume correctness from that confirmation.

The useful sequence is:

```text
mutation observation
        ↓
runtime verification
```

This distinction is central:

```text
I changed the world
≠
I changed it correctly
```

---

# 39. Post-fix verification

For the first time, Stage 03 makes:

```text
POST-FIX VERIFICATION
```

possible.

The desired epistemic progression is:

```text
A. baseline failure reproduced = YES
B. proposed fix reasoned about = YES
C. proposed fix applied        = YES
D. proposed fix verified       = YES
```

If the model applies the patch but never reruns pytest:

```text
C = YES
D = NO
```

Do not classify that as fully verified task completion.

---

# 40. No automatic success evaluator yet

Do not add a separate harness grader that automatically decides:

```text
task completed
task correct
```

We already know that:

```text
loop completion
≠
task completion
≠
correctness
```

For Stage 03, inspect these manually from:

```text
repository diff
pytest observations
model response
events
trace
```

A formal evaluator can be justified later if repeated manual analysis becomes a real burden.

---

# 41. Failure log

Create:

```text
lab/failure_log/03_mutation_agent.md
```

or the equivalent experimenter-only failure-log path established by the repository reorganization.

Record:

```text
task attempted
expected behavior
actual trajectory
baseline reproduction
mutation calls
mutation errors
repository diff
post-fix pytest result
task completion state
model epistemic accuracy
context/round-trip behavior
unexpected observations
remaining boundary
```

The failure report should explicitly classify:

```text
BASELINE REPRODUCED
MUTATION APPLIED
POST-FIX VERIFIED
TASK COMPLETED
```

as separate states.

---

# 42. Experimental isolation check

The Stage 03 failure report and spec must remain invisible to the agent.

Verify through tool tests and/or the trace that the model did not receive:

```text
Stage 03 expected trajectory
mutation roadmap hints
previous failure analyses
comparison conclusions
```

The experimenter's knowledge must remain outside the agent-visible information surface.

---

# 43. What NOT to implement

Do not implement:

```text
write_file
create_file
delete_file
rename_file
apply_patch
regex replace
multi-file patch
general shell
run_command
git tools
automatic rollback
backup manager
diff tool
permission prompts
sandbox framework
context compaction
tool discovery
planner
skills
MCP
subagents
memory
automatic evaluator
anti-loop heuristics
duplicate-call blocker
```

Stage 03 adds exactly one new capability:

```text
bounded exact-text mutation of an existing agent-visible file
```

---

# 44. Expected Stage 03 outcome

The ideal Stage 03 result is:

```text
OBSERVATION              = YES
RUNTIME EXECUTION        = YES
BASELINE REPRODUCTION    = YES
MUTATION                 = YES
POST-FIX VERIFICATION    = YES
TASK COMPLETION          = YES
```

If achieved, MiniHarness has completed its first full operational coding loop.

That does not mean the harness is complete.

It means the minimum basic agency loop is closed.

---

# 45. Expected next pressure

Do not preselect Stage 04 based solely on the roadmap.

Possible pressures after Stage 03 include:

```text
editing primitive too brittle
repository navigation too weak
fixture too trivial
context too noisy
need for broader execution
lack of diff visibility
```

Observed execution should determine what comes next.

---

# 46. Definition of Done

Stage 03 implementation is ready for experiment when:

```text
[✓] experimental isolation remains intact

[✓] Stage 01 tool set is unchanged

[✓] Stage 02 tool set is unchanged

[✓] Stage 03 adds exactly replace_text

[✓] replace_text works only on existing agent-visible text files

[✓] repository-relative safety is preserved

[✓] .env remains denied

[✓] experimenter metadata remains denied

[✓] old_text must occur exactly once

[✓] missing old_text leaves file unchanged

[✓] ambiguous old_text leaves file unchanged

[✓] empty old_text is rejected

[✓] empty new_text is allowed

[✓] no file creation/deletion exists

[✓] AgentLoop has no mutation-specific branch

[✓] OpenAI and Anthropic adapters require no conceptual redesign

[✓] uv run pytest passes for the harness test suite

[✓] Stage 03 begins from the known failing fixture baseline

[✓] one Luna Stage 03 run is executed with llm trace

[✓] repository diff is inspected after the run

[✓] post-mutation pytest behavior is observed

[✓] failure log is created experimenter-side
```

---

# 47. Completion report

After implementation and the first Luna run, report:

1. files created/modified;
2. exact `replace_text` schema;
3. path and experimental-isolation validation;
4. exact-match and ambiguity semantics;
5. write behavior;
6. `ToolResult.ok` semantics;
7. Stage 01/02 regression results;
8. harness test-suite result;
9. baseline fixture failure before the agent run;
10. Luna trajectory;
11. every `replace_text` call made;
12. resulting Git diff;
13. post-fix pytest result;
14. whether the model actually completed and verified the task;
15. whether any Stage 02 redundant exploration disappeared;
16. unexpected behavior;
17. the new observed boundary, if any.

Do not implement the next stage.

---

# 48. Stage 03 learning question

The primary question is:

> What changes in agent behavior when the model can finally change repository state and observe the consequences of its own mutation?

A secondary question is:

> Does redundant exploration caused by action-space mismatch decrease naturally once the missing mutation action becomes available?

Do not optimize the trajectory before observing it.

Let the stage answer these questions.
