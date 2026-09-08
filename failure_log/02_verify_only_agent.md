# Stage 02 — Verify-Only Agent

## Task attempted

The model received the same coding task as Stage 00 and Stage 01: fix the failing test `test_percentage_discount` in the fixture `tiny_checkout`, without modifying the tests, and then explain:

1. the cause of the bug;
2. which file was changed;
3. how the fix was verified.

The task text was unchanged. The harness difference was one new tool: `run_pytest`.

The agent still had no edit tool, no general shell, and no way to mutate repository files.

Baseline Luna run:

```text
stage:          02_verify_only_agent
model_profile:  openai_luna
provider:       openai
model:          gpt-5.6-luna
model_calls:    5
tool_calls:     6
input_tokens:   5799
output_tokens:  1040
outcome:        completed
llm_trace_mode: file
run:            runs/20260908T001234Z-43e940a5
```

Comparison Haiku run:

```text
stage:          02_verify_only_agent
model_profile:  anthropic_haiku
provider:       anthropic
model:          claude-haiku-4-5-20251001
model_calls:    9
tool_calls:     9
input_tokens:   20295
output_tokens:  1864
outcome:        completed
llm_trace_mode: file
run:            runs/20260908T001300Z-2eaa4f6b
```

`completed` means the model ended the conversation normally. It does not mean the bug was fixed.

---

## What I expected

Stage 01 showed that the model can inspect the repository and diagnose the bug, but cannot execute tests or apply a patch.

Stage 02 tested the next hypothesis:

```text
If the harness provides real pytest execution,
the model can reproduce the failing test from runtime evidence,
formulate the correct patch,
and then hit a remaining mutation boundary.
```

The expected trajectory was:

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

Expected epistemic state:

```text
A. baseline failure reproduced  = YES
B. proposed fix reasoned about  = YES
C. proposed fix applied         = NO
D. proposed fix verified        = NO
```

---

## What actually happened

### Luna trajectory

The model discovered `run_pytest` without being told to use it.

Turn 1: `list_files` with `path=""`. Tool error (`path must be a non-empty string`). Loop continued.

Turn 2: recovered with `list_files(path=".", max_depth=4)`.

Turn 3: read the real fixture files:

```text
fixtures/tiny_checkout/discount.py
fixtures/tiny_checkout/test_discount.py
```

It also read `AGENTS.md`. That extra read was not required to diagnose or reproduce the bug.

Turn 4: invoked the specific failing node:

```text
run_pytest(
  fixtures/tiny_checkout/test_discount.py::test_percentage_discount
)
```

The tool returned `ToolResult.ok = True` with `exit_code: 1` and the real assertion:

```text
E       assert 190.0 == 180.0
FAILED fixtures/tiny_checkout/test_discount.py::test_percentage_discount
1 failed in 0.03s
```

Turn 5: stopped calling tools. It used the runtime numbers in the final answer, proposed

```text
return price - (price * percent / 100.0)
```

and stated that no file was modified because write tools were unavailable. It did not claim that the proposed fix had been executed.

Observed execution path:

```text
TASK
  ↓
list_files (empty path → tool error)
  ↓
list_files(".")
  ↓
read_file(discount.py, test_discount.py, AGENTS.md)
  ↓
run_pytest(node selector) → exit_code 1, 190.0 == 180.0
  ↓
formulates correct patch
  ↓
cannot edit
  ↓
returns proposed change and stops
```

### Haiku trajectory

Haiku also found `run_pytest` without prompting.

It listed the repo, listed `fixtures/tiny_checkout`, read the test and implementation, then ran the same node selector. After seeing the failure it re-read `discount.py`, ran the same pytest target a second time, listed `fixtures` again, re-read `discount.py` again, and only then stopped.

It identified the same bug and proposed an equivalent fix:

```text
return price * (1 - percent / 100)
```

It said it could not modify files. It described a hypothetical post-fix pytest command rather than claiming the fix had been applied or re-run as passing.

---

## Test execution observed

Both models called `run_pytest` with the node selector, not the whole file.

Luna: one pytest call, after source inspection.

Haiku: two pytest calls, same target, with extra re-reads in between.

Harness observation for the Luna call:

```text
pytest target: fixtures/tiny_checkout/test_discount.py::test_percentage_discount
exit_code: 1
ToolResult.ok: true
stdout contains: assert 190.0 == 180.0
stderr: (empty)
```

This pairing is correct:

```text
ToolResult.ok = True
pytest exit_code = 1
```

`ToolResult.ok` answers:

```text
did the harness successfully perform the requested action
and obtain a valid environment result?
```

`pytest exit_code` answers:

```text
what was the domain/runtime outcome?
```

Therefore:

```text
tool execution success
≠
test success
```

A failing test is valid runtime evidence, not a harness/tool failure.

The fixture file was not modified before or after either run:

```text
return price - percent
```

No `.pytest_cache` was created by `run_pytest` (`-p no:cacheprovider`). A pre-existing project cache from `uv run pytest` of the harness tests remained visible to `list_files`.

---

## Runtime evidence acquired

Yes. The model no longer had to infer failure from source alone.

The next provider request after `run_pytest` contained the formatted tool output, including `exit_code: 1` and `assert 190.0 == 180.0`. Luna cited those exact values in the final answer.

This is the Stage 02 change relative to Stage 01:

```text
Stage 01: diagnosis from source text
Stage 02: baseline failure reproduced by a real failing pytest process
```

That is baseline failure reproduction, not post-fix verification. The proposed patch was never applied, so there was no changed implementation to re-run.

---

## Tool errors

Luna still emitted the Stage 01 empty-path `list_files` error on turn 1. It recovered on the next turn. No `run_pytest` validation errors occurred.

Haiku had no tool errors.

---

## Remaining mutation boundary

The model now has repository observation and runtime execution, and can verify/reproduce the baseline failure. It still has no write/patch tool.

After reproducing the failure, both models knew the file and the formula. Neither could change `discount.py`. Neither could re-run pytest against a patched implementation.

The important distinction is:

```text
BASELINE FAILURE VERIFICATION
≠
POST-FIX VERIFICATION
```

Stage 02 established:

```text
A. baseline failure reproduced  = YES
B. proposed fix reasoned about  = YES
C. proposed fix applied         = NO
D. proposed fix verified        = NO
```

The remaining boundary is:

```text
OBSERVATION              = YES
RUNTIME EXECUTION        = YES
BASELINE REPRODUCTION    = YES
MUTATION                 = NO
POST-FIX VERIFICATION    = NO
```

Once mutation is absent, post-fix verification is impossible because there is no changed implementation to execute.

The task still cannot be completed.

---

## Context growth

Luna `list_files(".", max_depth=4)` returned 3129 characters and included `runs/` plus the pre-existing `.pytest_cache/`. Later turns therefore carried a large tree listing plus the pytest failure output.

Haiku used more turns and repeated pytest/read calls. Input tokens grew from 857 on turn 1 to 3625 on turn 9, totaling 20295 versus Luna's 5799.

No compaction exists. The extra runtime-execution channel adds useful evidence and also more context.

---

## Round-trip behavior

`llm_trace.jsonl` for Luna shows:

1. `run_pytest` present in the provider tool list from turn 1;
2. turn 4 response requests `run_pytest` with the node selector;
3. turn 5 request includes the `function_call_output` with `exit_code: 1` and `assert 190.0 == 180.0`;
4. turn 5 response uses those numbers and stops at the mutation boundary.

No subprocess argv or `sys.executable` internals were written into the trace. The model saw the compact tool observation only.

The same `ToolDefinition` flowed through both OpenAI and Anthropic adapters. AgentLoop had no pytest-specific branch.

---

## Unexpected observations

1. Luna still starts with `list_files(path="")`, the same first-turn error as Stage 01.
2. Luna inspects source before running pytest, rather than reproducing first. That still satisfies the stage goal.
3. Haiku repeated the same failing pytest target and re-read the implementation after the useful next action was already known. See action-space mismatch below.
4. Runtime evidence did not make the model claim success. Both models stayed honest about not applying the patch.
5. `list_files` still surfaces generated/developer artifacts such as `runs/` and `.pytest_cache/`. That is perception noise, not a `run_pytest` leak.

### Action-space mismatch

The Haiku run revealed a mismatch between what the model already knew and what the harness could do.

By the time it repeated itself, Haiku had already:

```text
read the test
read the implementation
run the failing test
identified the bug
```

The useful next action would have been:

```text
edit the implementation
```

That action did not exist in the available tool set.

Haiku then continued with actions such as:

```text
read implementation again
run the same pytest target again
list files again
read implementation again
```

This is an action-space mismatch:

```text
the model knows the useful next action
but that action is absent from the harness action space
```

That can lead to repeated observation/execution actions with low marginal information.

Do not describe this simply as Haiku being inefficient. The more careful interpretation is:

```text
MODEL POLICY
+
CONSTRAINED ACTION SPACE
→
redundant exploration can emerge
```

Do not infer from Haiku's repeated reads/tests that MiniHarness now needs:

```text
duplicate-call detector
same-test cache
retry blocker
"already read this file" warnings
anti-loop heuristics
```

The redundancy may disappear naturally once the missing mutation capability exists.

Do not build a subsystem to suppress repeated behavior before testing whether the behavior is simply a consequence of a missing capability.

This is analogous to the Stage 01 lesson where tool-error recovery did not require a dedicated RecoveryAgent.

### Perception / workspace-view noise

Luna's `list_files(".", max_depth=4)` included `runs/` and a pre-existing `.pytest_cache/` from developer `uv run pytest`, not from `run_pytest`.

Treat this as perception noise / workspace-view noise. It is not a Stage 02 failure.

Do not immediately implement:

```text
ignore policy
.gitignore-aware listing
workspace filtering
context filtering
```

Stage 02 exposed that generated lab artifacts can enter repository perception. This is an observed future pressure, not yet evidence that a new filtering primitive is required.

---

## Observable failure

Stage 01's runtime-execution gap is gone. The agent can now execute the real test and reproduce the baseline failure. That is not post-fix verification.

The remaining failure is:

```text
can inspect repository
can execute the real test
can reproduce the failing behavior
can reason from runtime evidence
can formulate the correct mutation

but cannot change repository state
```

Observed execution path:

```text
TASK
  ↓
READ-ONLY PERCEPTION
  ↓
REAL PYTEST EXECUTION
  ↓
baseline failure reproduced
  ↓
correct patch known
  ↓
NO EDIT CHANNEL
  ↓
repository unchanged
post-fix correctness NOT VERIFIED
  ↓
BLOCKED
```

---

## Why the current harness cannot overcome it

MiniHarness can now:

- loop across multiple model turns;
- list and read repository files;
- run a validated repository-relative pytest target through `sys.executable -m pytest`;
- return passing or failing pytest results as environment evidence.

It still cannot:

- write or patch a file;
- apply the proposed discount formula;
- re-run pytest against a changed implementation.

Baseline failure reproduction without mutation can confirm the bug. It cannot complete the task. Post-fix verification remains impossible until mutation exists.

This is a harness limitation, not a model-reasoning failure. Luna reproduced `190.0 == 180.0` and named the correct fix in five turns.

---

## Next primitive justified by this failure

Stage 01 exposed two simultaneous gaps:

```text
mutation
execution / verification
```

Stage 01 therefore did not determine which primitive should come next. Stage 02 intentionally added runtime execution first.

That execution gap has now been isolated and resolved. Stage 02 added runtime execution without adding general shell access:

```text
execution capability
≠
general-purpose terminal capability
```

`run_pytest` supplied exactly the runtime evidence required for the stage while keeping the action surface narrow. This reduced the number of simultaneous concepts introduced.

The remaining operational blocker is:

```text
mutation
```

The next missing agent capability empirically justified by this failure is a file-mutation/edit channel.

This is stronger than the Stage 01 conclusion because mutation is now the sole observed capability blocker preventing task progression.

Do not select the exact Stage 03 implementation here. Candidate primitive classes include:

```text
write_file
search_replace
apply_patch
```

Do not add a generic shell as the next step. A shell would collapse mutation and further execution into one tool and hide the next pedagogical boundary.

Do not implement a mutation primitive until this boundary is treated as the Stage 03 starting point.

---

## What I learned

Real pytest output changed the agent's epistemic position. The model could say the test failed because it failed, not because the source looked wrong.

`ToolResult.ok` remaining true for `exit_code: 1` was essential. A failing test is a successful and useful tool observation, not a harness error.

The mutation boundary became cleaner than in Stage 01. Runtime execution was added first, so mutation is now the sole remaining observed capability blocker.

Haiku's extra pytest/read loop is better read as action-space mismatch than as model inefficiency: the useful next action was edit, and that action was absent. Do not optimize that friction away with duplicate-suppression infrastructure before testing whether mutation removes it.

Consolidated Stage 02 lessons:

```text
1. Runtime evidence is qualitatively different from static source evidence.

2. Baseline failure reproduction is different from post-fix verification.

3. Tool execution success is different from domain/test success.

4. A failing test can be a successful and useful tool observation.

5. Runtime execution can be added without exposing a general-purpose shell.

6. Missing capabilities can produce redundant exploration.

7. Action-space mismatch can explain behavior that initially looks inefficient.

8. Do not build duplicate suppression or recovery infrastructure prematurely.

9. Runtime observations add additional context pressure.

10. The mutation boundary is now empirically isolated.

11. Post-fix verification remains impossible until mutation exists.
```

---

## Questions to investigate in frontier harnesses

1. After a failing test is reproduced, do they expose a dedicated edit tool before offering a shell?
2. How do they prevent the model from treating a proposed patch as already applied?
3. Do they distinguish test failure from tool failure in the observation format?
4. When the model repeats the same failing test, do they allow it, cache it, or steer toward mutation?
5. How do they keep pytest/target execution from becoming a general command runner?
6. How much of the raw pytest output do they send back versus a structured summary?
7. After baseline reproduction exists, is the next primitive write, patch, or git?
8. How do frontier harnesses distinguish baseline reproduction from post-change verification?
9. How do they represent tool success versus domain-operation failure?
10. When the useful next action is unavailable, do they allow repeated observation freely or intervene?
11. Do repeated tool calls disappear naturally once mutation is available?
12. At what point do frontier harnesses introduce duplicate-call detection or loop heuristics?
13. Do coding harnesses expose narrow verification tools, a general shell, or both?
14. How do they decide between write_file, search/replace, patch, and shell-mediated editing?

These remain future investigation prompts. They were not researched in Stage 02.

---

## Stage conclusion

```text
STAGE 02 — PASSED / CLOSED
```

Stage 02 successfully resolved the runtime-execution gap identified at the end of Stage 01.

The agent can now inspect the repository, execute the real failing test, observe runtime evidence, and formulate the correct fix.

The repository remains unchanged because no mutation capability exists.

The remaining empirically demonstrated agent capability gap is mutation.

No additional recovery, duplicate suppression, context-management, permission, planning, or execution primitive is justified by Stage 02.

Stage 02 is closed.

The mutation boundary becomes the starting point for Stage 03 design, but no Stage 03 primitive is selected or implemented in this report.
