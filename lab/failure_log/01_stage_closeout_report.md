# Stage 01 Closeout Report — Read-Only Agent

Status: **CLOSED**  
Stage: `01_read_only_agent`

This document is an additional closeout report for Stage 01.

It does not replace the original failure log.

The purpose is to consolidate what Stage 01 actually demonstrated after:

- implementing the provider-neutral AgentLoop;
- adding `list_files` and `read_file`;
- running OpenAI and Anthropic models;
- implementing Anthropic tool calling;
- adding provider I/O tracing;
- inspecting OpenAI Responses and Anthropic Messages payloads turn by turn.

---

# 1. Stage objective

Stage 01 tested a deliberately narrow hypothesis:

```text
If the harness gives the model read-only perception of the repository,
can the model move from speculation to evidence while still hitting
a clear execution boundary?
```

The available agent capabilities were intentionally limited to:

```text
AgentLoop
+
list_files
+
read_file
```

The agent had no:

```text
file mutation
shell
test runner
git
search / grep
automatic AGENTS.md injection
context compaction
skills
MCP
LSP
subagents
memory
planning system
permissions framework
sandbox
```

The task remained the same simple checkout bug used in Stage 00.

That isolation was important.

The goal was not to build a capable coding agent.

The goal was to experience the pressure that makes additional harness primitives necessary.

---

# 2. Final observed capability boundary

Stage 00 failed at:

```text
cannot observe repository
```

Stage 01 resolved that boundary.

The new operational flow became:

```text
TASK
  ↓
MODEL
  ↓
structured tool request
  ↓
HARNESS
  ↓
filesystem
  ↓
real observation
  ↓
MODEL
  ↓
correct diagnosis
```

The model could now inspect the actual repository and identify the concrete defect.

The remaining boundary was:

```text
can observe
can diagnose

but cannot:

- mutate repository state
- execute / verify repository behavior
```

Therefore the final Stage 01 boundary is:

```text
PERCEPTION = AVAILABLE

MUTATION = UNAVAILABLE

EXECUTION / VERIFICATION = UNAVAILABLE
```

Stage 01 did not establish that mutation must come before verification.

Both gaps are directly observable.

Their ordering remains a curriculum/design decision.

---

# 3. The first real AgentLoop

Stage 01 converted the MiniHarness from:

```text
task
  ↓
model
  ↓
text
```

into:

```text
reason
  ↓
request action
  ↓
execute action
  ↓
observe environment
  ↓
reason again
```

This was the first point at which MiniHarness behaved as an operational agent runtime rather than a single model call.

A central distinction became concrete:

```text
MODEL CAPABILITY
≠
HARNESS CAPABILITY
```

The model can understand that a repository should be inspected.

Only the harness can make that inspection actually happen.

---

# 4. Tool errors became observations

One of the most important Stage 01 findings came from a trivial error.

The model attempted:

```text
list_files(path="")
```

The tool returned:

```text
Invalid arguments: path must be a non-empty string
```

No special subsystem existed for recovery.

There was no:

```text
RetryAgent
RecoveryManager
ErrorPlanner
CriticAgent
```

The harness simply returned a truthful tool result.

The next model turn adapted its behavior and used:

```text
path="."
```

The real mechanism was:

```text
ACTION
  ↓
ENVIRONMENT ERROR
  ↓
OBSERVATION
  ↓
MODEL REASONING
  ↓
CORRECTED ACTION
```

This produced one of the strongest Stage 01 lessons:

> Do not build recovery infrastructure before observing whether a competent model can recover directly from a good environment observation.

The same principle appears highly transferable beyond coding agents.

For many business agents:

```text
tool error
≠
system failure
```

It can instead be:

```text
new state information
for the model to reason over
```

---

# 5. Tool design is part of the cognitive interface

The difference between:

```text
path=""
```

and:

```text
path="."
```

looked trivial from an API implementation perspective.

It was not trivial from an agent perspective.

The schema mismatch caused:

```text
tool failure
+
new tool result
+
new model round trip
+
additional context
+
additional latency
+
additional token consumption
```

Therefore:

```text
ToolDefinition
```

is not merely plumbing.

It is part of the model's action interface.

Tool ergonomics influence:

```text
trajectory
errors
round trips
latency
cost
```

This was the first concrete reason to treat tool design as a core harness discipline.

---

# 6. Action space and trajectory are different things

MiniHarness defined the available action space:

```text
list_files
read_file
```

But MiniHarness did not decide:

```text
which path to inspect
which file to read
how many files to read
whether to reread a file
whether to inspect project metadata
whether to batch several reads
```

Those choices came from the model.

The distinction became:

```text
HARNESS
→ defines possible actions

MODEL
→ chooses a trajectory inside that action space
```

This became particularly clear when comparing different models.

---

# 7. Same harness, different trajectories

Stage 01 was executed with multiple models under the same conceptual harness.

The runs demonstrated that:

```text
same task
+
same tools
+
same AgentLoop

does not imply

same trajectory
```

## OpenAI Luna

Luna often requested several independent observations in one model turn.

One run followed approximately:

```text
T1
list_files("")
→ error

T2
list_files(".")
read_file(pyproject.toml)

T3
read_file(discount.py)
read_file(test_discount.py)
read_file(AGENTS.md)
read_file(README.md)

T4
final answer
```

This showed a relatively batched exploration strategy.

---

## Anthropic Haiku

Haiku behaved much more serially.

One run followed approximately:

```text
T1
list_files(".")

T2
list_files("fixtures/tiny_checkout")

T3
read_file(test_discount.py)

T4
read_file(discount.py)

T5
read_file(discount.py) again

T6
final answer
```

The model acquired fewer observations per inference step and even repeated one file read after already having enough evidence.

This exposed a new concept:

```text
trajectory efficiency
```

A cheaper model per token can still produce a longer and more expensive overall agent trajectory if it requires:

```text
more model turns
more rereads
more searches
more retries
more context retransmission
```

---

## OpenAI Sol

Sol showed a frontier-model trajectory that was generally more concentrated.

A representative run followed:

```text
T1
list_files("")
→ error

T2
list_files(".")

T3
read AGENTS.md
read implementation
read test
read pyproject.toml

T4
final
```

It acquired several independent observations in one model response and reached the same execution boundary in fewer turns.

The comparison demonstrated:

```text
tool call count
≠
model round-trip count
≠
trajectory efficiency
```

A model can make more tool calls but still require fewer expensive reasoning rounds.

---

# 8. Useful tool calls versus redundant observations

Stage 01 also showed that:

```text
number of tool calls
```

is not a sufficient quality metric.

Some calls were:

```text
directly task-relevant
```

such as:

```text
read implementation
read failing test
```

Others were:

```text
orientation
```

such as:

```text
read AGENTS.md
read pyproject.toml
```

Those are not automatically waste.

In professional repository work they may be responsible actions.

Other calls were more clearly low-marginal-information observations, such as rereading the same tiny implementation after the bug had already been identified.

This suggests a future distinction between:

```text
necessary evidence
responsible repository orientation
recoverable mistakes
redundant exploration
```

A naive metric such as:

```text
fewer tool calls = better agent
```

would be misleading.

---

# 9. `AGENTS.md`: push versus pull

Stage 01 explicitly did not implement automatic project-instruction loading.

Nevertheless, some models discovered:

```text
AGENTS.md
```

in the repository tree and voluntarily read it.

This exposed two distinct architectures.

## PUSH

```text
HARNESS
automatically injects project instructions
```

## PULL

```text
MODEL
discovers project instruction file
and explicitly reads it
```

Stage 01 therefore did not remain completely free of project instructions in every final model turn.

But that did not violate the intended harness boundary.

The correct description is:

```text
automatic harness injection = NO

model-initiated instruction retrieval = POSSIBLE
```

This distinction may later matter for:

```text
reliability
token consumption
latency
cache behavior
instruction priority
consistency
```

---

# 10. Multi-tool generation versus parallel tool execution

Some OpenAI model turns returned several tool calls in one response.

For example:

```text
read_file(A)
read_file(B)
read_file(C)
read_file(D)
```

This exposed an important distinction.

## Model/provider capability

```text
MULTI-TOOL GENERATION
```

The model can express several independent desired actions in one inference.

## Harness capability

```text
PARALLEL TOOL EXECUTION
```

The current MiniHarness still executes:

```python
for call in tool_calls:
    registry.execute(call)
```

Therefore:

```text
model requested several tools together

does not imply

harness executed them concurrently
```

This distinction was invisible before Stage 01.

---

# 11. Context growth became observable

The first Stage 01 runs already showed input-token growth across turns.

Initially this looked approximately like:

```text
task
+
tool schemas
+
messages
+
tool calls
+
tool results
+
repository content
```

As execution continues:

```text
working context grows
```

This gave a concrete reason for the existence of future mechanisms such as:

```text
context compaction
summarization
retrieval
tool filtering
prompt caching
```

However, provider I/O tracing later showed that the real story is more subtle.

---

# 12. Provider I/O tracing exposed the real conversation shape

The added raw provider trace did not change agent capability.

It exposed what had already been happening.

The tracer records:

```text
provider request payload
provider raw response
```

while:

```text
events.jsonl
```

continues to record provider-neutral semantic execution.

The distinction is:

```text
llm_trace.jsonl
=
provider-native I/O observability

events.jsonl
=
harness semantic observability
```

This proved highly valuable.

---

# 13. The conversation is not simply user / assistant / tool text

The OpenAI Responses trace showed that continuation state includes provider-native items such as:

```text
reasoning
function_call
function_call_output
```

The effective next request can look more like:

```text
user task

reasoning state
function_call
function_call_output

reasoning state
function_call
function_call
function_call_output
function_call_output

...
```

rather than a traditional chat transcript.

This changed the mental model of "conversation history".

---

# 14. `raw_output` became understandable

MiniHarness already carried:

```python
Message.raw_output
ModelTurn.raw_output
```

The trace made its purpose clear.

`raw_output` is:

```text
machine-facing provider-private continuation state
```

For OpenAI, it can preserve provider-native output items.

For Anthropic, it preserves content blocks needed to correctly replay assistant tool-use turns, including provider-native structures such as:

```text
tool_use
thinking
redacted_thinking
```

when present.

The distinction is now:

```text
raw_output
=
operational state used by the agent runtime
```

versus:

```text
llm_trace.jsonl
=
human observability
```

The tracer does not participate in execution.

Deleting the trace must not affect the agent.

---

# 15. Reasoning state can exist without visible reasoning text

The OpenAI trace revealed provider-native `reasoning` items containing opaque/encrypted continuation state.

This does not expose the model's private chain of thought.

But it demonstrates that a reasoning model's rollout state can involve more than visible assistant text.

Conceptually:

```text
provider response
    ↓
opaque reasoning continuation state
    ↓
raw_output
    ↓
next provider request
```

Therefore:

```text
conversation state
≠
only user-visible conversation
```

This is an important adapter-level responsibility.

---

# 16. Adapter is more than field renaming

Before tracing, a provider adapter could look conceptually like:

```text
rename fields
normalize output
```

Stage 01 showed that it does more.

The adapter is responsible for translating and preserving the provider protocol.

OpenAI uses structures such as:

```text
function_call
function_call_output
reasoning
```

Anthropic uses:

```text
assistant content blocks
tool_use
user tool_result blocks
tool_use_id
is_error
```

Therefore the adapter influences:

```text
conversation materialization
provider-private continuation
tool protocol
usage representation
caching behavior
```

The AgentLoop can remain provider-neutral only because the adapter handles these differences.

---

# 17. Anthropic tool calling made provider neutrality concrete

The same MiniHarness semantics were successfully mapped onto two provider protocols:

```text
MiniHarness
    │
    ├── OpenAI adapter
    │     ↓
    │   Responses API
    │
    └── Anthropic adapter
          ↓
        Messages API
```

The same internal concepts were preserved:

```text
ToolDefinition
ToolCall
ToolResult
ModelTurn
```

while the wire representation changed.

This validated the project's vendor-neutral direction at a very small scale.

---

# 18. Tool errors as cognitive feedback generalized across providers

Anthropic maps failed tool execution into:

```text
tool_result
is_error = true
```

OpenAI receives tool failures as the corresponding function output content.

The key abstraction remains provider-neutral:

```text
ToolResult(
    ok=False,
    output="truthful environment error"
)
```

The model can then decide how to react.

This reinforces the Stage 01 recovery insight:

```text
good tool observations
can eliminate the need
for premature special-purpose recovery subsystems
```

---

# 19. Prompt caching changed the interpretation of context cost

The OpenAI provider trace showed prompt caching happening during the rollout.

A later turn contained:

```text
input tokens
+
cached input tokens
+
newly processed/cache-written tokens
```

This means:

```text
context size
≠
uncached model work
```

The same full logical context may be present while part of it is reused from cache.

Therefore future economics must distinguish at least:

```text
input tokens
cached input tokens
uncached input tokens
output tokens
reasoning tokens
```

A simple total such as:

```text
summary.input_tokens
```

is not sufficient for cross-provider cost analysis.

---

# 20. Output tokens are not equivalent to visible answer length

Provider traces also showed that output-token accounting may include:

```text
reasoning tokens
tool-call representation
visible assistant text
```

Therefore:

```text
output_tokens
≠
visible response tokens
```

This matters for future model economics.

A model can produce a short final answer while consuming substantial non-visible reasoning output.

---

# 21. Effective provider behavior can exceed explicit harness configuration

The OpenAI request explicitly contained only a small configuration surface such as:

```text
model
input
max_output_tokens
tools
```

The provider response exposed effective behaviors/settings such as:

```text
reasoning mode
parallel tool-call support
automatic tool choice
```

This creates another useful distinction:

```text
HARNESS-REQUESTED CONFIGURATION
≠
PROVIDER EFFECTIVE BEHAVIOR
```

Understanding a harness therefore requires inspecting both:

```text
what the harness asks for
```

and:

```text
what the provider/model actually does
```

---

# 22. Tool registry retransmission became concrete

Provider traces confirmed that the tool registry is included again in successive model calls.

With only:

```text
list_files
read_file
```

this is trivial.

But the mechanism immediately explains why large agent systems encounter pressure toward:

```text
tool filtering
tool search
lazy loading
namespaces
dynamic discovery
```

A future system with hundreds of tool schemas cannot necessarily expose the complete action catalog on every inference without cost.

Stage 01 therefore produced the first concrete motivation for tool discovery mechanisms.

---

# 23. Round-trip economics became more important than raw tool count

The model comparisons exposed a useful economic principle.

For local filesystem tools:

```text
tool execution
≈ extremely cheap and fast
```

while:

```text
additional model round trip
= comparatively expensive and slow
```

This suggests a future notion of:

```text
turn efficiency
```

Conceptually:

```text
useful environmental information acquired
─────────────────────────────────────────
            model inference rounds
```

A model that batches several useful observations into one inference may be operationally cheaper than a cheaper-per-token model that serializes every observation into a separate reasoning step.

---

# 24. Total agent economics is trajectory-dependent

Stage 01 invalidated a simplistic model comparison such as:

```text
Model A costs X per token
Model B costs Y per token
therefore B is cheaper
```

Actual agent cost depends on more dimensions:

```text
MODEL PRICE
+
TRAJECTORY LENGTH
+
TOOL STRATEGY
+
CONTEXT GROWTH
+
CACHE BEHAVIOR
+
REASONING USAGE
+
HARNESS EXECUTION POLICY
```

This is one of the central lessons for the larger Agent Harness Lab.

---

# 25. Completion semantics were insufficient

Current run summaries can report:

```text
outcome = completed
```

But Stage 01 showed three different states:

```text
loop_completion  = YES

task_completion  = NO

task_correctness = N/A
```

The agent loop ended normally.

The requested repository task was not completed because no file changed.

Functional correctness was not verified because tests were never executed.

Therefore:

```text
loop completion
≠
task completion
≠
task correctness
```

This distinction will become increasingly important as the harness gains mutation and execution capabilities.

---

# 26. The fixture was intentionally easy

The tiny fixture contained a very obvious implementation defect.

Therefore Stage 01 demonstrated:

```text
read-only perception can ground model reasoning
```

It did not demonstrate:

```text
list_files + read_file
are sufficient for serious debugging
```

The fixture served its intended purpose:

```text
isolate perception
```

rather than:

```text
benchmark software engineering intelligence
```

No broader debugging conclusion should be drawn from it.

---

# 27. What Stage 01 did NOT justify

The following components remain unjustified by Stage 01 alone:

```text
RecoveryAgent
CriticAgent
RetryPlanner
context compaction implementation
tool search implementation
parallel executor
automatic AGENTS injection
planner
subagents
memory
skills
MCP
LSP
sandbox
permission framework
```

Some of their motivating pressures became visible.

That is different from saying they should now be implemented.

The lab principle remains:

> Do not add a primitive merely because frontier harnesses contain it. Add it when an observed execution barrier makes its role concrete.

---

# 28. What Stage 01 DID justify as observed future pressure

The following pressures are now empirically visible:

```text
MUTATION GAP

EXECUTION / VERIFICATION GAP

CONTEXT GROWTH

TOOL REGISTRY OVERHEAD

TOOL SCHEMA FRICTION

MODEL ROUND-TRIP COST

PROVIDER PROTOCOL DIFFERENCES

CACHE-AWARE ACCOUNTING

REDUNDANT OBSERVATION

PROJECT-INSTRUCTION PUSH VS PULL

MULTI-TOOL GENERATION VS PARALLEL EXECUTION

LOOP COMPLETION VS TASK COMPLETION VS CORRECTNESS
```

These are observations.

They are not yet a mandated implementation sequence.

---

# 29. Stage 01 consolidated mental model

The harness can now be understood as several distinct layers.

```text
                    TASK
                     │
                     ▼
                 AgentLoop
                     │
                     │ provider-neutral
                     ▼
               Model Adapter
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
   OpenAI protocol        Anthropic protocol
          │                     │
          ▼                     ▼
        MODEL                 MODEL
          │                     │
          └──────────┬──────────┘
                     ▼
               Model Adapter
                     │
                     ▼
                  ToolCall
                     │
                     ▼
                ToolRegistry
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
     list_files             read_file
          │                     │
          └──────────┬──────────┘
                     ▼
                 ToolResult
                     │
                     ▼
                  AgentLoop
```

Alongside that operational path:

```text
events.jsonl
→ semantic harness observability
```

and:

```text
llm_trace.jsonl
→ provider-native I/O observability
```

Neither observability channel should alter execution.

---

# 30. The most important conceptual decomposition

By the end of Stage 01, behavior can be decomposed into four layers.

## MODEL

The model:

```text
chooses trajectory
decides what evidence to acquire
batches or serializes observations
reacts to tool errors
may perform redundant exploration
decides when to stop
```

## HARNESS

The harness:

```text
defines available actions
executes tool calls
returns observations
maintains the execution loop
enforces capability boundaries
```

## ADAPTER

The adapter:

```text
maps provider-neutral state
to provider-native protocol

preserves provider-private continuation state

normalizes provider output
back into MiniHarness concepts
```

## PROVIDER

The provider contributes:

```text
wire protocol
usage accounting
caching behavior
effective defaults
tool-call semantics
reasoning-state representation
```

This decomposition is the main intellectual output of Stage 01.

---

# 31. Stage 01 key lessons

```text
1. An LLM call is not an agent.

2. AgentLoop turns model intention into environment interaction.

3. Perception converts speculation into evidence.

4. Tool errors can be useful observations rather than system failures.

5. A competent model can perform recovery without a dedicated recovery subsystem.

6. Tool schema design shapes model trajectory, latency and cost.

7. Harness defines action space; model chooses the trajectory.

8. Same harness does not imply same trajectory across models.

9. More tool calls do not necessarily mean lower efficiency.

10. Fewer model round trips can matter more than fewer local tool calls.

11. Repository orientation is not automatically waste.

12. Project instructions can be pushed by the harness or pulled by the model.

13. One model response can contain several tool calls.

14. Multi-tool generation and parallel execution are different capabilities.

15. Multi-turn execution causes context growth quickly.

16. Provider-native continuation state can be richer than visible chat history.

17. `raw_output` and raw observability traces serve different purposes.

18. Provider adapters do much more than rename fields.

19. Prompt caching changes the economics of growing context.

20. Input-token totals alone are insufficient for cost comparison.

21. Output tokens can include invisible reasoning work.

22. Tool registries themselves create context overhead.

23. Model price per token alone cannot predict full agent cost.

24. Loop completion is different from task completion.

25. Task completion is different from verified correctness.

26. Stage 01 revealed both a mutation gap and an execution/verification gap.

27. The experiment does not yet determine which gap should be addressed first.
```

---

# 32. Final Stage 01 failure statement

The final failure statement is:

```text
The MiniHarness can now establish a real model ↔ environment feedback loop
and provide repository evidence through read-only tools.

The model can inspect the actual code, diagnose the bug, recover from
certain tool errors, and formulate the correct mutation.

The harness cannot yet change repository state or execute the software
to establish functional verification.

The next observed capability gaps are therefore:

1. mutation
2. execution / verification

The Stage 01 evidence does not determine their implementation order.
```

---

# 33. Stage verdict

```text
STAGE 01 — CLOSED
```

Success criteria were met.

The Stage 00 perception barrier was resolved.

A new execution boundary was reached cleanly.

No unnecessary capability was added to cross that boundary.

The resulting experiments exposed not only read-only perception, but also:

```text
agent-loop mechanics
tool ergonomics
error-as-observation recovery
trajectory differences across models
context accumulation
provider protocol differences
provider-private continuation state
prompt caching
reasoning-token accounting
tool-registry overhead
multi-tool behavior
completion semantics
```

Stage 01 can therefore be considered complete.

No next-stage primitive is selected by this report.
