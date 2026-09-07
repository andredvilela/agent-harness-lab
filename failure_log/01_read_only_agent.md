# Stage 01 — Read-Only Agent

## Task attempted

The model received the same coding task as Stage 00: fix the failing test `test_percentage_discount` in the fixture `tiny_checkout`, without modifying the tests, and then explain:

1. the cause of the bug;
2. which file was changed;
3. how the fix was verified.

The task text was unchanged. The difference was harness capability: MiniHarness now owns an explicit agent loop and exposes two read-only tools, `list_files` and `read_file`.

The agent still had no edit tool, no shell, and no test runner.

Run configuration:

```text
stage:          01_read_only_agent
model_profile:  openai_luna
provider:       openai
model:          gpt-5.6-luna
model_calls:    4
tool_calls:     7
input_tokens:   3315
output_tokens:  835
outcome:        completed
run:            runs/20260907T180513Z-9aa475bb
```

`completed` means the model ended the conversation normally. It does not mean the bug was fixed.

---

## What I expected

Stage 00 showed that the model can reason about the task but cannot inspect the repository.

Stage 01 tested the next hypothesis:

```text
If the harness provides perception,
the model can acquire evidence from the environment,
but remains unable to modify or verify the repository.
```

The expected trajectory was:

```text
task
  ↓
model asks to inspect repo
  ↓
list_files
  ↓
read_file(test)
  ↓
read_file(implementation)
  ↓
understands actual bug
  ↓
wants to edit and/or test
  ↓
no such capability exists
  ↓
blocked at a new boundary
```

The purpose was not to fix the checkout bug. It was to see whether read-only tools are enough for the model to observe the real implementation, and what barrier appears after that.

---

## What actually happened

The model discovered and used both tools without being prompted to do so.

Turn 1: it called `list_files` immediately, with `path=""` and `max_depth=4`. The harness returned a tool error (`path must be a non-empty string`). The process did not crash. The error went back to the model as an observation.

Turn 2: it recovered. It listed `path="."` successfully, and in the same turn also listed `path="tiny_checkout"`, which failed with `File not found` because the fixture actually lives at `fixtures/tiny_checkout`.

Turn 3: after seeing the real tree, it read the correct files:

```text
fixtures/tiny_checkout/discount.py
fixtures/tiny_checkout/test_discount.py
```

It also read `AGENTS.md` and `pyproject.toml`. Those extra reads were not required to diagnose the bug. It did not re-read the implementation or the test.

Turn 4: it stopped calling tools and returned a final textual answer.

It diagnosed the actual bug: `percent` is subtracted as an absolute amount (`price - percent`) instead of being applied as a percentage. It proposed:

```text
return price * (1 - percent / 100)
```

which matches the failing assertion `apply_percentage_discount(200.0, 10.0) == 180.0`.

It did not claim that it had edited the repository. It stated that the available tools are read-only. It did not claim that it had run the tests. It described a hypothetical `pytest` command that it could not execute.

Observed execution path:

```text
TASK
  ↓
MODEL
  ↓
list_files (empty path → tool error)
  ↓
list_files(".") + list_files("tiny_checkout") (second path wrong)
  ↓
read_file(discount.py, test_discount.py, AGENTS.md, pyproject.toml)
  ↓
understands actual bug
  ↓
proposes a patch
  ↓
cannot edit
  ↓
cannot run tests
  ↓
returns proposed change and stops
```

---

## Observable failure

The model acquired enough repository evidence to identify the real bug and the correct file. The harness then had no channel for the next required actions: changing the implementation and verifying the fix.

Observed execution path:

```text
TASK
  ↓
MODEL
  ↓
EXECUTABLE READ-ONLY TOOL CHANNEL
  ↓
inspects actual implementation
  ↓
knows the fix
  ↓
NO EDIT CHANNEL
NO TEST / SHELL CHANNEL
  ↓
repository unchanged
tests unrun
  ↓
BLOCKED
```

The Stage 00 failure was "cannot observe". That failure is gone.

The Stage 01 failure is "can observe, cannot act or verify".

The model did not invent a missing write tool and did not falsely report success. It hit the harness boundary and stopped.

---

## Why the current harness cannot overcome it

The MiniHarness can now:

- loop across multiple model turns;
- accept structured tool calls;
- execute `list_files` and `read_file`;
- return observations and tool errors to the model.

It still cannot:

- write or patch a file;
- run pytest or any other command;
- inspect git state;
- confirm that the repository changed.

The task requires a mutation and a check. Perception is not sufficient for either.

This is a harness limitation, not a model-reasoning failure. GPT-5.6 Luna found the bug after four turns.

---

## Next primitive justified by this failure

The next missing capability is an edit channel.

The model already knows which file to change and what the change should be. Without a way to apply that change, the repository cannot move. A test runner would still be necessary afterward, but verification is not the first remaining gap: there is nothing new to verify until the file can be modified.

The smallest primitive that addresses this failure is a write/edit tool, for example `write_file` or a single-file patch tool.

Do not add a generic shell yet. A shell would hide the distinction between editing and verification, and would skip the next pedagogical boundary.

Do not implement that primitive until this failure is treated as the Stage 02 starting point.

---

## Minimal implementation idea

A later stage could add one file-mutation tool:

```text
write_file(path, contents)
```

or a slightly safer:

```text
apply_patch / search_replace
```

Keep the agent loop. Keep `list_files` and `read_file`. Do not add pytest, git, or a terminal as part of the same step.

The expected next experiment is:

```text
model observes bug
  ↓
model edits discount.py
  ↓
model wants to verify
  ↓
no test/shell capability
  ↓
new boundary
```

---

## What I learned

Read-only tools were enough to convert speculation into evidence. The model inspected the real fixture, recovered from two tool errors, and named the actual bug.

`completed` is the wrong proxy for task success. The run completed because the model stopped talking, not because the repository was fixed.

Tool errors are part of perception. An empty path and a wrong relative path were useful observations. The model adapted without a retry policy.

The model used `read_file` to load `AGENTS.md` on its own. That is not harness-level project-instruction loading. It is the model noticing a file in the listing. Frontier harnesses often inject such files automatically; this run shows the model will also pull them when it can see the tree.

The model asked for two missing capabilities at once: edit and verify. The edit gap is the one that blocked applying the known fix.

---

## Questions to investigate in frontier harnesses

1. After the model understands a fix, do they expose a dedicated edit tool, a patch tool, or a shell that can write files?
2. How do they keep edit and test execution as separate capabilities rather than collapsing both into a terminal?
3. How do they present tool errors so the model recovers, as it did here from `path=""` and a wrong directory name?
4. Do they inject `AGENTS.md` / project rules automatically, or wait for the model to read them?
5. How do they record the trajectory so a later reviewer can see every `list_files` / `read_file` argument, not just the final answer?
6. How do they prevent a model from claiming that it edited or tested when those tools are absent?
7. When several tools are requested in one turn, do they execute them sequentially, in parallel, or under a policy?
8. What is the next primitive they add after perception: write, search, or verify?
