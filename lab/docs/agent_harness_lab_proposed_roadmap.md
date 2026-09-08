# Agent Harness Lab — Proposed Roadmap

Status: **PROPOSED / NON-BINDING**  
Purpose: **Curriculum map for the Agent Harness Lab**

---

## 1. Purpose of this document

This document describes a **probable learning path** for the Agent Harness Lab.

It is not a fixed implementation plan.

The lab follows an experimental rule:

> Do not add a harness primitive before a scenario demonstrates a concrete failure or pressure that motivates it.

Therefore, the roadmap below should be interpreted as:

```text
probable capability progression
+
expected future pressures
+
candidate experiments
```

not as:

```text
mandatory sequence of features
```

The observed behavior of the lab has authority over this roadmap.

If a future stage exposes a different bottleneck than expected, the roadmap should change.

---

## 2. Core learning method

The lab is intentionally built from execution barriers.

```text
experience execution barrier
        ↓
implement the smallest plausible primitive
        ↓
observe model + harness behavior
        ↓
inspect failure and trajectory
        ↓
decide what capability is actually missing
        ↓
only then add another primitive
```

The objective is not to reproduce a frontier coding agent as quickly as possible.

The objective is to understand why frontier harnesses contain the mechanisms they contain.

> Build from observed necessity, not from feature imitation.

---

## 3. Roadmap philosophy

The roadmap has three broad phases.

### I. Basic agency

```text
reason
→ perceive
→ execute
→ mutate
```

### II. Real repository work

```text
navigate
→ search
→ execute broadly
→ follow project instructions
```

### III. Harness control and scale

```text
manage context
→ control permissions
→ discover tools
→ plan
→ reuse procedures
→ integrate external systems
→ delegate
→ persist knowledge
→ optimize economics
```

Stages 00–03 are expected to be relatively linear because they establish the minimum closed agent loop.

After that, the roadmap becomes increasingly provisional.

---

## 4. Current progress

Completed:

```text
Stage 00 — Naked Model
Stage 01 — Read-Only Agent
Stage 02 — Verify-Only Agent
```

Current capability state:

```text
REASONING              = YES
REPOSITORY OBSERVATION = YES
RUNTIME EXECUTION      = YES
BASELINE REPRODUCTION  = YES
MUTATION               = NO
POST-FIX VERIFICATION  = NO
```

Current empirically demonstrated boundary:

```text
the agent can understand the repository,
run the failing test,
observe the real failure,
and formulate the correct fix,

but cannot change repository state.
```

This makes mutation the likely starting point for Stage 03.

---

## 5. Proposed stage map

| Stage | Probable primitive / concept | Capability added | Expected pressure being addressed |
|---|---|---|---|
| 00 | Model call | Reasoning | A model call alone is not an operational agent |
| 01 | AgentLoop + read tools | Perception | The model needs real evidence from the environment |
| 02 | `run_pytest` | Runtime evidence | Static reasoning is not runtime verification |
| 03 | Edit / patch primitive | Mutation | The agent knows the fix but cannot change the world |
| 04 | Search / grep / navigation | Repository discovery | `list_files` + `read_file` stop scaling |
| 05 | General execution / shell | Broader execution | `run_pytest` becomes too narrow |
| 06 | Project instructions | Persistent repository guidance | The agent needs reliable repo-specific operating rules |
| 07 | Context management | Bounded working context | History, files and tool output begin to accumulate |
| 08 | Permissions / sandbox | Action control | Mutation + shell create real risk |
| 09 | Tool discovery / filtering | Dynamic action space | Large tool registries become expensive/noisy |
| 10 | Planning / task state | Long-horizon control | Implicit model planning becomes insufficient |
| 11 | Skills | Reusable procedural knowledge | Repeated workflows deserve explicit reusable procedures |
| 12 | MCP / external integrations | External action space | The agent needs systems outside the local repository |
| 13 | Subagents | Delegation | A single trajectory becomes a bottleneck |
| 14 | Persistent knowledge / memory | Cross-run continuity | Useful knowledge should survive the current run |
| 15 | Economics / policy tuning | Harness optimization | Cost, latency and trajectory trade-offs become important |

This table is a curriculum hypothesis, not a contract.

---

## 6. Stage 03 — Mutation

### Probable purpose

Add the smallest file-mutation capability required to complete the current task.

Candidate primitive classes may include:

```text
write_file
search_replace
apply_patch
```

The exact choice should be decided from the Stage 03 design discussion.

The likely first complete agent cycle becomes:

```text
inspect
  ↓
reproduce failure
  ↓
diagnose
  ↓
edit
  ↓
run pytest
  ↓
observe pass
```

This would be the first stage where MiniHarness can potentially complete the coding task end-to-end.

### Expected lesson

```text
reason      ✓
observe     ✓
execute     ✓
mutate      ✓
```

The basic operational agent loop is finally closed.

### Possible new pressures

Mutation may reveal questions around:

```text
edit precision
partial writes
patch conflicts
verification after mutation
rollback
diff visibility
unintended changes
```

Any of these could alter the roadmap.

---

## 7. Stage 04 — Search and repository navigation

The current repository is intentionally tiny.

Tools such as:

```text
list_files
read_file
```

work well when the relevant code is obvious.

They will not scale naturally to a repository containing hundreds or thousands of files.

A larger fixture may create tasks such as:

```text
find where a function is defined
find all callers
find related tests
find configuration references
locate a symbol across the repository
```

This may justify capabilities such as:

```text
search_text
grep
find_files
find_symbol
```

Expected pressure:

```text
repository size
        ↓
serial file inspection becomes expensive
        ↓
targeted retrieval becomes necessary
```

---

## 8. Stage 05 — General execution

Stage 02 deliberately introduced a narrow execution primitive:

```text
run_pytest
```

Eventually that may become insufficient.

A realistic coding task may require:

```text
ruff
mypy
python scripts
uv commands
git diff
build commands
project-specific test runners
```

That can create pressure for something like:

```text
run_command
```

or a shell/terminal capability.

A general shell should not be introduced early because it also introduces:

```text
arbitrary commands
filesystem mutation
network access
package installation
environment variables
process lifecycle
destructive actions
```

---

## 9. Stage 06 — Project instructions

The lab has already observed an early form of this issue.

Models discovered and read:

```text
AGENTS.md
```

without automatic harness injection.

This exposes two architectures.

### Pull

```text
model discovers project instructions
and explicitly reads them
```

### Push

```text
harness automatically injects
project instructions into context
```

Future experiments may compare:

```text
reliability
token cost
instruction priority
cache behavior
discoverability
consistency
```

This stage connects directly with the broader principle:

```text
repository owns project knowledge
not the coding assistant vendor
```

---

## 10. Stage 07 — Context management

Context pressure is already visible.

Each turn can accumulate:

```text
task
tool schemas
repository listings
source files
tool calls
tool results
runtime output
provider-native continuation state
```

As tasks become larger:

```text
working context grows
```

This may justify experiments with:

```text
compaction
summarization
dropping stale observations
retrieval
re-reading on demand
recent-turn windows
important-context preservation
```

Context engineering should emerge from observed pressure, not from premature optimization.

---

## 11. Stage 08 — Permissions and sandboxing

Once the agent can both:

```text
mutate files
execute broad commands
```

the harness gains meaningful destructive power.

Potential actions include:

```text
delete files
modify unrelated files
read secrets
run network commands
install packages
change Git state
execute dangerous commands
```

This creates a new layer:

```text
MODEL
  ↓
requests action
  ↓
PERMISSION / POLICY LAYER
  ↓
allow / deny / ask
  ↓
SANDBOX / EXECUTION ENVIRONMENT
```

Expected lesson:

```text
tool availability
≠
authorization
≠
execution isolation
```

---

## 12. Stage 09 — Tool discovery and filtering

Today the tool registry is small.

A future harness might contain:

```text
filesystem tools
git tools
browser tools
database tools
GitHub tools
email tools
ERP tools
internal APIs
```

Sending hundreds of schemas on every model turn may create:

```text
context overhead
token cost
tool-selection noise
latency
```

This can justify:

```text
tool filtering
tool search
lazy loading
namespaces
dynamic discovery
```

The lab has already observed the precursor: tool definitions are present again in successive provider requests.

---

## 13. Stage 10 — Planning and explicit task state

Do not introduce a planner merely because frontier harnesses have planning systems.

Modern models can already perform substantial implicit planning.

Increase task complexity until implicit planning becomes insufficient.

Possible observed failures:

```text
forgotten requirements
missed files
repeated work
premature completion
lost subtask state
```

Only then consider explicit structures such as:

```text
plan
todo list
completed steps
remaining steps
task state
```

Planning infrastructure should compensate for an observed long-horizon control problem.

---

## 14. Stage 11 — Skills

Skills become interesting when the lab starts observing repeated procedures.

Example:

```text
when modifying a FastAPI endpoint:

1. inspect router
2. inspect schema
3. inspect service
4. inspect tests
5. modify implementation
6. run validation
7. update documentation
```

Conceptually:

```text
skill
=
reusable procedural knowledge
```

This creates a path from:

```text
observed repeated workflow
        ↓
codified procedural knowledge
        ↓
reusable repository-owned skill
```

This stage is especially relevant to the self-evolving repository architecture.

---

## 15. Stage 12 — MCP and external integrations

Until this stage, the agent's environment is mostly:

```text
repository
+
local runtime
```

Eventually the action space may extend to:

```text
GitHub
browser
database
Slack
email
ERP
cloud systems
internal APIs
```

This creates questions around:

```text
tool discovery
authentication
transport
schema exposure
remote execution
external state
permissions
```

MCP becomes easier to understand after local tools and tool protocols are already familiar.

---

## 16. Stage 13 — Subagents

Subagents should not be introduced simply because multi-agent architectures are popular.

A single model trajectory should first demonstrate a real bottleneck.

Possible pressures:

```text
large repository
independent investigations
long context
parallelizable analysis
specialized tasks
```

Then an architecture such as:

```text
main agent
   ├── subagent A
   ├── subagent B
   └── subagent C
```

can be explored.

This introduces questions about:

```text
delegation
context isolation
authority
cost
parallelism
result merging
failure propagation
```

---

## 17. Stage 14 — Persistent knowledge

Until persistence exists:

```text
run ends
→ working agent state ends
```

A mature agentic repository may want to preserve:

```text
repository conventions
architectural decisions
failed approaches
known commands
debugging discoveries
workflow knowledge
```

The key distinction becomes:

```text
ephemeral working context
```

versus:

```text
persistent project knowledge
```

This stage connects directly to:

```text
PROJECT
=
code state
+
knowledge state
```

The repository should own durable knowledge, minimizing dependence on any specific model or harness vendor.

---

## 18. Stage 15 — Economics and harness tuning

Economic signals are already being collected:

```text
model calls
tool calls
input tokens
output tokens
cache behavior
latency
trajectory length
```

Systematic optimization should come after the harness contains meaningful capabilities.

At that point, the lab may compare models and harness policies together.

Questions include:

```text
What makes this agent expensive?

Is the expensive model actually more expensive per completed task?

How much cost comes from trajectory rather than price per token?

Does a larger model reduce round trips?

Which harness policy changes total task economics?
```

The goal is causal understanding, not publication-grade benchmarking.

---

## 19. Proposed visual progression

```text
                    BASIC AGENCY
                         │
                         ▼
                   00 — Model
                         │
                   01 — Perception
                         │
                02 — Runtime Execution
                         │
                   03 — Mutation
                         │
                         ▼
                COMPLETE BASIC LOOP
                         │
                         ▼
               04 — Search / Navigation
                         │
               05 — General Execution
                         │
              06 — Project Instructions
                         │
                         ▼
                REAL REPOSITORY WORK
                         │
                         ▼
              07 — Context Management
                         │
            08 — Permissions / Sandbox
                         │
             09 — Tool Discovery
                         │
           10 — Planning / Task State
                         │
                         ▼
                 HARNESS CONTROL
                         │
                         ▼
                    11 — Skills
                         │
              12 — MCP / Integrations
                         │
                  13 — Subagents
                         │
            14 — Persistent Knowledge
                         │
                         ▼
              ADVANCED AGENT SYSTEM
                         │
                         ▼
              15 — Economics / Tuning
```

---

## 20. Where the roadmap is likely to branch

Stages 00–03 form a relatively natural sequence:

```text
reason
→ perceive
→ execute
→ mutate
```

After Stage 03, the curriculum should become substantially more empirical.

Examples:

### Branch A — Editing pressure

```text
Stage 03 mutation
      ↓
patches are brittle
      ↓
next stage = better edit primitive
```

### Branch B — Navigation pressure

```text
Stage 03 mutation
      ↓
larger repository task
      ↓
too many reads
      ↓
next stage = search
```

### Branch C — Context pressure

```text
larger task
      ↓
context becomes excessive
      ↓
context management moves earlier
```

### Branch D — Safety pressure

```text
general execution added
      ↓
dangerous action becomes possible
      ↓
permissions/sandbox moves immediately next
```

The governing rule is:

```text
ROADMAP
suggests likely future experiments

FAILURE
selects the actual next experiment
```

---

## 21. What should not drive the roadmap

Do not add a feature merely because it exists in:

```text
Claude Code
Codex
Cursor
Copilot
OpenCode
Qwen Code
other frontier harnesses
```

Do not add a primitive because:

```text
it looks architecturally elegant
it is popular
it appears in an agent framework
it may become useful someday
```

Instead:

```text
observed failure
        ↓
understand missing capability
        ↓
implement minimum intervention
        ↓
observe again
```

---

## 22. Frontier harness research

Frontier coding harnesses remain useful references.

Preferred order:

```text
experience the problem
        ↓
form our own mental model
        ↓
inspect how frontier harnesses solve it
        ↓
compare trade-offs
```

rather than:

```text
inspect frontier harness
        ↓
copy architecture
```

This preserves the educational value of the lab.

---

## 23. Relationship to the larger project

The lab is not only about building a coding agent.

It is intended to develop transferable understanding of agent harnesses.

Principles already visible include:

```text
truthful environment observations
→ model recovery
```

```text
tool execution success
≠
business outcome success
```

```text
model capability
≠
harness capability
```

```text
missing action capability
→ redundant exploration
```

```text
tool schema
→ cognitive/action interface
```

```text
persistent project knowledge
→ vendor-neutral intelligence layer
```

The larger objective is to understand behavior emerging from:

```text
MODEL
+
HARNESS
+
TOOLS
+
CONTEXT
+
POLICY
+
ENVIRONMENT
+
PERSISTENT KNOWLEDGE
```

---

## 24. Roadmap governance rule

Before opening a new stage, answer:

```text
1. What concrete failure or pressure did the previous stage reveal?

2. What is the smallest new capability that addresses it?

3. What capabilities are explicitly NOT being added?

4. What new boundary do we expect to encounter?

5. What evidence would prove that the stage succeeded?

6. What would cause us to abandon or reorder the proposed roadmap?
```

If these questions cannot be answered clearly, the next stage is probably underspecified.

---

## 25. Current next-step hypothesis

At the time this roadmap was written:

```text
Stage 02 = CLOSED
```

Observed boundary:

```text
OBSERVATION              = YES
RUNTIME EXECUTION        = YES
BASELINE REPRODUCTION    = YES
MUTATION                 = NO
POST-FIX VERIFICATION    = NO
```

Therefore the current strongest hypothesis is:

```text
Stage 03
=
introduce the smallest useful mutation primitive
```

This remains a hypothesis until Stage 03 design begins.

---

## 26. Final principle

> The lab should eventually write its own curriculum through its failures.

This document provides orientation.

Observed execution remains the authority.

---

## 27. Experimental isolation

Experimenter-only lab metadata must not be visible through agent tools unless a scenario explicitly studies access to that information.

This includes, by default:

```text
stage specs
failure reports
lab roadmap
experimental analyses
run traces/results
```

For model/harness trajectory comparisons to be meaningful, preserve:

```text
same task
same tools
same agent-visible repository state
```

A model that reads hidden experimental hints is operating from a different information state.

See `lab/docs/experimental_isolation.md`.

The root `README.md` is agent-visible project documentation. The lab overview lives in `lab/README.md` and is experimenter-only.
