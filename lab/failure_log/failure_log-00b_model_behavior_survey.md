# Stage 00B — Model Behavior Survey

## Task attempted

Stage 00B reused exactly the same coding task and naked harness from Stage 00A.

The task asked the model to fix the failing `test_percentage_discount` test in the `tiny_checkout` fixture, without modifying the tests, and then explain:

1. the cause of the bug;
2. which file was changed;
3. how the fix was verified.

The experimental conditions were intentionally frozen:

```text
same task
same prompt
same harness
same absence of tools
same inaccessible repository

variable:
provider / model
```

Four model profiles were observed:

```text
openai_luna
openai_sol
anthropic_haiku
anthropic_opus
```

The purpose was not to determine which model was "best".

The purpose was to observe how different models behave when confronted with an agentic task that requires a capability the harness does not provide.

---

## What I expected

I expected all models eventually to encounter the same hard operational ceiling:

```text
task requires repository interaction
        ↓
harness provides no repository interaction
        ↓
task cannot be completed
```

However, I expected their behavior before reaching that conclusion to differ.

Possible behaviors included:

- immediately recognizing the missing capability;
- narrating an intended workflow before detecting the limitation;
- attempting nonexistent tool calls;
- asking the user to supply repository contents;
- reasoning about possible bugs despite insufficient evidence;
- hallucinating repository details;
- proposing speculative fixes;
- falsely claiming modification or verification.

The experiment was therefore intended to expose:

```text
MODEL BEHAVIOR
        ≠
HARNESS CAPABILITY
```

---

## What actually happened

All four models ultimately recognized that they did not have enough operational access to complete the task.

None claimed that the repository had actually been modified.

None claimed that tests had actually been executed successfully.

However, their trajectories differed substantially.

---

### OpenAI Luna

Luna initially behaved as though it were beginning a normal coding-agent workflow.

Its trajectory was approximately:

```text
inspect implementation
→ locate test
→ reason about percentage representation
→ attempt to proceed
→ detect absence of repository/terminal access
→ declare itself blocked
```

It described actions such as inspecting the checkout implementation and locating the relevant code before acknowledging that no repository or terminal capability was available.

It also formed an early hypothesis that the bug might involve treating a percentage as a whole number versus a decimal.

The behavior can be summarized as:

```text
correct procedural instinct
+
premature progress narration
+
eventual capability awareness
```

It did not claim that the hypothesis was confirmed.

It did not claim a successful fix.

An earlier Stage 00A run using the same Luna model had gone one step further and emitted output resembling nonexistent `container.exec` and `terminal.exec` calls.

The Stage 00B Luna run did not reproduce that exact trajectory.

This is important evidence of run-to-run behavioral variance.

---

### OpenAI Sol

Sol reacted much more directly.

Its trajectory was approximately:

```text
detect no filesystem/shell
→ state operational limitation
→ request repository access
→ stop
```

It did not spend significant visible effort exploring possible causes of the bug.

It did not narrate a fictitious investigation.

It did not attempt to compensate for the missing capability with speculative reasoning.

Its behavior was the cleanest example of immediate capability-boundary recognition.

---

### Anthropic Haiku

Haiku interpreted the problem primarily as missing information that the user could provide.

Its trajectory was approximately:

```text
missing repository information
→ ask user for test
→ ask user for implementation
→ ask user for failure message
→ explain what it could do after receiving them
```

Rather than treating the missing repository as an absent harness capability, it behaved more like a traditional conversational assistant.

Conceptually:

```text
missing information
        ↓
ask human to supply it
```

rather than:

```text
missing environment capability
        ↓
expect harness/tool access
```

It did not invent repository facts or claim completion.

---

### Anthropic Opus

Opus explicitly recognized that it lacked repository contents, files, tests and tooling and stated that producing a fix would otherwise require guessing.

It then continued reasoning about the problem class.

It listed several generic possibilities for percentage-discount failures, including:

```text
percentage vs fraction representation
unit price vs line total
tax/shipping ordering
rounding behavior
discount amount vs discounted total
```

The important distinction is that these were presented as generic hypotheses, not as observations about the actual repository.

Its trajectory was approximately:

```text
recognize evidence boundary
→ refuse to invent repository facts
→ generate generic diagnostic hypotheses
→ request concrete evidence
```

This demonstrated more visible reasoning despite the fact that no additional action was possible.

---

## Qualitative comparison

| Profile | Provider | Class | Detects limitation | Nonexistent tool attempt in 0B | Invented repo facts | False success | Requests access / evidence |
|---|---|---|---|---|---|---|---|
| openai_luna | OpenAI | economic | yes | no* | no | no | yes |
| openai_sol | OpenAI | frontier | yes | no | no | no | yes |
| anthropic_haiku | Anthropic | economic | yes | no | no | no | yes |
| anthropic_opus | Anthropic | frontier | yes | no | no | no | yes |

\* Luna did emit tool-like calls in the earlier Stage 00A run, demonstrating trajectory variance under essentially the same naked-agent condition.

---

## Observable failure

Despite substantial differences in behavior, every model reached the same operational limit:

```text
MODEL
  │
  ├── can reason
  ├── can plan
  ├── can identify missing information
  └── may know what action should happen next

              X

HARNESS
  │
  └── cannot expose or modify repository
```

No increase in model capability could cross that boundary.

The experiment therefore produced a common terminal state:

```text
economic model ─┐
frontier model ─┤
other provider ─┼──→ BLOCKED
stronger model ─┘

because:

tools = none
```

---

## Why the current harness cannot overcome it

Stage 00B still uses the naked execution architecture:

```text
task
  ↓
ModelClient
  ↓
provider API
  ↓
text response
```

Changing the model changes the behavior inside the box.

It does not change the system's external capabilities.

The harness still lacks:

```text
structured tool requests
tool execution
environment observations
iterative model/tool interaction
```

Therefore even a substantially more capable model cannot inspect a file that the harness never exposes.

This demonstrates a fundamental distinction:

```text
intelligence
        ≠
capability
```

A more capable model may:

- identify the limitation faster;
- form better hypotheses;
- communicate uncertainty better;
- waste fewer or more tokens;
- choose a different recovery strategy.

But it cannot create an execution channel that does not exist.

---

## Next primitive justified by this failure

Stage 00A established that the model needed repository perception.

Stage 00B strengthens that conclusion across multiple model families.

The next primitive should therefore not be a stronger model.

It should be a minimal action/perception mechanism.

The next stage is justified in introducing:

```text
Agent Loop
+
structured Tool interface
+
Tool dispatch
+
list_files
+
read_file
```

The next stage should remain intentionally read-only.

Do not yet introduce:

```text
search
editing
shell
tests
project instructions
context management
skills
permissions
sandbox
memory
subagents
MCP
```

The experiment should isolate what changes when a model finally gains the ability to observe the environment.

---

## Minimal implementation idea

The current architecture:

```python
response = model.generate(task)
return response
```

must become capable of repeated interaction:

```text
MODEL
  │
  │ requests observation
  ▼
HARNESS
  │
  │ executes read-only operation
  ▼
REPOSITORY
  │
  │ returns observation
  ▼
HARNESS
  │
  ▼
MODEL
```

Conceptually:

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

Initially, the action space should contain only:

```text
list_files
read_file
```

The objective is not yet to fix the bug.

The objective is to observe what new barrier appears once perception exists.

---

## What I learned

### 1. Model capability and harness capability are independent dimensions

A frontier model cannot compensate for a capability that the runtime does not expose.

All four models remained operationally blocked.

This was true despite obvious differences in reasoning style and sophistication.

---

### 2. The harness establishes the ceiling of possible action

The models differed in what they wanted to do.

The harness determined what they were actually capable of doing.

In Stage 00B:

```text
possible action space = ∅
```

Therefore all trajectories eventually converged to the same operational result.

---

### 3. Different models react differently to the same capability boundary

The observed strategies differed:

```text
Luna
→ begins procedural investigation
→ later detects boundary

Sol
→ detects boundary quickly
→ stops

Haiku
→ asks human to provide missing information

Opus
→ detects boundary
→ continues generic diagnostic reasoning
```

These differences may become much more consequential once a real action space exists.

---

### 4. A stronger model does not necessarily produce more useful work when action is impossible

Opus generated additional diagnostic reasoning.

Sol stopped almost immediately.

Both completed exactly zero repository actions.

This introduces an important future economic question:

```text
How much reasoning expenditure produces useful progress
versus reasoning that cannot be converted into action?
```

No conclusion should yet be drawn about which behavior is economically preferable.

---

### 5. Model training appears to influence the expected interaction pattern

Some models behaved as though environment interaction should normally be available.

Others behaved more like conversational assistants expecting the human to paste missing context.

This suggests that "agentic behavior" is partly present in the model itself before the harness is introduced.

The harness does not create all agent behavior from scratch.

It provides an environment in which latent behavioral policies can become executable.

---

### 6. Same model + same task does not imply same trajectory

Luna behaved differently between Stage 00A and Stage 00B.

In 00A it emitted text resembling nonexistent tool calls.

In 00B it narrated an intended investigation but did not reproduce those explicit pseudo-tool calls.

Therefore:

```text
same model
+
same task
+
same capability boundary

does not guarantee

same trajectory
```

This is the first direct evidence in the lab of model stochasticity / behavioral variance.

Individual runs should therefore be treated as observations, not permanent properties of a model.

---

### 7. Qualitative comparison is useful before statistical benchmarking

A single run is insufficient to claim:

```text
"Model X always behaves this way."
```

But it is sufficient to reveal different possible behavior classes and generate hypotheses worth testing later.

For the purpose of this didactic stage, the survey has already done its job.

---

### 8. Provider-reported token usage should not yet be treated as directly comparable economics

The same textual task can be tokenized and accounted for differently across providers.

Additionally, provider APIs may differ in what they include inside reported input/output usage.

The current telemetry remains useful for understanding individual executions and broad orders of magnitude.

It should not yet be treated as a normalized cross-provider cost measurement system.

A future need for normalized measurement may justify a wire-level proxy or another accounting layer, but that component is not required yet.

---

### 9. The next bottleneck is clearly the harness, not model selection

Stage 00B does not provide evidence that changing from an economic model to a frontier model meaningfully changes the operational result when environment access is absent.

The highest-value next intervention is therefore:

```text
add capability
```

rather than:

```text
add intelligence
```

---

## Questions to investigate in frontier harnesses

After implementing the minimal Stage 01 version ourselves, investigate:

1. How much of tool-use behavior is taught to the model versus imposed by the harness?
2. How do different providers represent structured tool calls?
3. Does the harness normalize provider-specific tool protocols into a common internal representation?
4. Who owns the iterative agent loop?
5. How are tool results inserted back into model context?
6. How do harnesses distinguish final responses from requests for action?
7. How do they handle a model requesting a tool that does not exist?
8. How do they handle malformed arguments?
9. Do different models choose substantially different tool trajectories when given the same action space?
10. Does a frontier model use a small action space more efficiently than an economic model?
11. How much does tool description/schema design influence model behavior?
12. When does stronger reasoning reduce tool calls, and when does it merely add reasoning cost?
13. How do Codex, Claude Code, Grok Build, OpenCode and Qwen Code normalize provider/model differences?
14. Which parts of their apparent agentic behavior live in the model, and which live explicitly in the harness?

These questions should be revisited after Stage 01 makes tool execution concrete.

---

## Stage conclusion

```text
STAGE 00B — PASSED
```

The model behavior survey demonstrated:

```text
Stage 00A
Model ≠ Agent

Stage 00B
Model capability ≠ Harness capability

Different models
→ different behavioral trajectories
→ same operational ceiling

Same model
→ potentially different trajectories across runs
```

The next justified experiment is:

```text
Stage 01 — Read-only Agent

AgentLoop
+
Tool interface
+
list_files
+
read_file
```

The objective of Stage 01 is not yet to fix the checkout bug.

It is to give the model the missing capability identified in Stages 00A and 00B and observe what fails next.