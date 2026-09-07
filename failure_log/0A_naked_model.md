# Stage 00A — Naked Model

## Task attempted

The model received a coding task asking it to fix the failing test `test_percentage_discount` in the `tiny_checkout` fixture, without modifying the tests, and then explain:

1. the cause of the bug;
2. which file was changed;
3. how the fix was verified.

The harness supplied only the task text to the model.

The model had no repository access, filesystem tools, shell, test runner, editing capability, or structured tool-calling interface.

Run configuration:

```text
stage:          00_model_only
model_profile:  openai_default
provider:       openai
model:          gpt-5.6-luna
prompt_chars:   301
input_tokens:   71
output_tokens:  1584
outcome:        ungraded
```

The model call took approximately 19.3 seconds from `model_request` to `model_response`.

---

## What I expected

I expected the model to encounter the fundamental limitation of a naked model call:

```text
task
  ↓
model
  ↓
text
```

The task requires interaction with an external environment, but the model has no mechanism to inspect or modify that environment.

Possible expected behaviors included:

* asking for repository contents;
* stating that repository access was unavailable;
* hallucinating repository structure or implementation details;
* proposing a speculative patch;
* falsely claiming that the task had been completed;
* attempting to express a tool call despite no tools being exposed.

The purpose of the experiment was not to solve the bug. It was to observe how a model behaves when a task requires capabilities that the harness does not provide.

---

## What actually happened

The model immediately formed an appropriate operational plan:

```text
inspect repository
→ inspect discount implementation
→ reproduce failing test
→ make smallest change
→ run relevant tests
```

It then emitted output resembling attempts to invoke environment tools, including commands conceptually equivalent to:

```text
container.exec(...)
terminal.exec(...)
```

For example, it attempted to inspect the directory structure and later attempted to query the current working directory.

However, these were not executable tool calls from the perspective of the MiniHarness.

They were simply text emitted as part of the model response.

No tool schema had been supplied to the model, no tool request had been parsed by the harness, and no operation was executed against the repository.

After these attempts, the model recognized that repository and test-runner access were unavailable.

It explicitly stated that it could not safely:

* inspect `tiny_checkout`;
* identify the implementation bug;
* modify the correct file;
* execute the tests;
* verify a fix.

It therefore did not invent a repository implementation or falsely claim that the bug had been corrected.

---

## Observable failure

The model identified actions required to solve the task, but the harness provided no mechanism to convert those intended actions into interactions with the environment.

Observed execution path:

```text
TASK
  ↓
MODEL
  ↓
forms appropriate operational plan
  ↓
attempts to express environment actions
  ↓
NO EXECUTABLE TOOL CHANNEL
  ↓
actions are only text
  ↓
repository remains inaccessible
  ↓
model recognizes limitation
  ↓
BLOCKED
```

The practical failure was therefore not primarily an inability to reason about what should happen next.

The failure was an inability to act.

---

## Why the current harness cannot overcome it

The Stage 0A harness implements only a single model invocation:

```text
prompt
  ↓
ModelClient.generate()
  ↓
provider API
  ↓
ModelResult.text
```

There is no execution path from model output to the external environment.

The harness currently lacks at least the following concepts:

```text
structured tool request
        ↓
tool dispatch
        ↓
environment operation
        ↓
observation
        ↓
new model invocation
```

Even if the model knows that it should inspect a file, the harness cannot execute that intention.

This establishes an important distinction:

```text
MODEL CAPABILITY

can reason that repository inspection is necessary

≠

HARNESS CAPABILITY

can actually give the model access to the repository
```

The Stage 0A system therefore cannot become an operational coding agent merely through a stronger textual response.

It requires an action mechanism.

---

## Next primitive justified by this failure

The observed failure justifies introducing a minimal mechanism for **environment perception**.

The next system should allow the model to request and receive information from the repository.

The minimal capabilities suggested by this failure are:

```text
Agent Loop
+
Tool interface
+
Tool dispatch
+
list_files
+
read_file
```

The next stage should remain read-only.

It should not yet add:

* editing;
* search;
* shell;
* test execution;
* project instructions;
* context management;
* permissions;
* skills;
* memory.

The purpose should be only to answer:

> What changes when the model can finally inspect the environment it is reasoning about?

---

## Minimal implementation idea

The current execution:

```python
response = model.generate(task)
return response
```

would eventually need to evolve toward a loop conceptually similar to:

```python
messages = [task]

while True:
    response = model.generate(messages, tools)

    if response.is_final:
        return response

    for tool_call in response.tool_calls:
        result = execute(tool_call)
        messages.append(result)
```

For the next stage, the available action space should be deliberately tiny:

```text
list_files
read_file
```

This is enough to introduce the distinction between:

```text
reasoning
```

and:

```text
reasoning + perception + observation
```

without yet giving the model the ability to modify the environment.

---

## What I learned

### 1. A model call is not an agent

A model can formulate an appropriate plan while still being completely incapable of executing it.

The missing capability resides in the harness.

---

### 2. Agentic behavior may already exist inside the model

Even though no tools were exposed, the model attempted to express actions resembling shell or container operations.

This suggests that the model has learned an internal behavioral pattern approximately like:

```text
coding task
→ inspect environment
→ locate implementation
→ modify
→ test
```

The model's internal policy can therefore be more agentic than the capabilities exposed by the harness.

---

### 3. Intended tool use and actual tool use are different things

The model emitted text resembling tool calls.

Nothing was executed.

This distinction is fundamental:

```text
model expresses intention to act
            ≠
harness executes an action
```

A harness must provide the protocol and runtime connecting the two.

---

### 4. The model correctly recognized the boundary of its evidence

Once it determined that repository access was unavailable, it refused to identify a specific bug or claim successful verification without evidence.

In this run, the model did not hallucinate repository facts or falsely claim task completion.

---

### 5. Missing harness capabilities can create token waste

The run used:

```text
71 input tokens
1584 output tokens
```

while producing no repository modification.

A substantial part of the output consisted of:

* planning actions that could not be performed;
* expressing attempted actions;
* discovering the lack of capability;
* explaining why execution was blocked.

No economic conclusion can be drawn from a single run, but the observation suggests a future question:

> How much model expenditure is caused by poor or missing harness capabilities rather than by the intrinsic difficulty of the task?

---

### 6. The first missing harness capability is perception, not intelligence

The immediate barrier is not the absence of a more capable model.

The system needs a way to expose information from the environment to the model.

This provides the causal motivation for the next primitive.

---

## Questions to investigate in frontier harnesses

After implementing the minimal equivalent ourselves, investigate how frontier harnesses solve the same class of problem:

1. How does the harness describe available tools to the model?
2. What does a structured tool request look like?
3. Where does tool dispatch occur?
4. How is a tool result represented and returned to the model?
5. Who controls the agent loop: provider API, harness runtime, or both?
6. How are invalid or malformed tool calls handled?
7. How much provider-specific logic exists in the tool interface?
8. Are filesystem capabilities exposed as many narrow tools or a smaller number of broad tools?
9. How do different models behave when the same tools are available?
10. How much of apparently “agentic” behavior comes from model training versus harness orchestration?

These questions should be revisited only after the minimal implementation has made the underlying problem concrete.