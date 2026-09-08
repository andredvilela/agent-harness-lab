# Reorganize Agent Harness Lab for Experimental Isolation

We have completed:

```text
Stage 00 — Naked Model
Stage 01 — Read-Only Agent
Stage 02 — Verify-Only Agent
```

Before beginning Stage 03, reorganize the repository to establish an explicit boundary between:

```text
1. information intended to be visible to the experimental agent

2. experimenter-only metadata about the lab itself
```

This task is **experimental hygiene**, not a new Agent Harness capability stage.

Do not implement Stage 03.

Do not add mutation capabilities.

Do not redesign the harness architecture unnecessarily.

---

# 1. Why this change is required

During Stages 01 and 02, the agent could inspect repository files using:

```text
list_files
read_file
```

That was useful because it allowed us to observe behaviors such as the model voluntarily discovering and reading:

```text
AGENTS.md
pyproject.toml
source files
tests
```

However, the repository is now accumulating documents such as:

```text
stage specifications
failure reports
roadmap documents
run artifacts
experimental analyses
```

These documents describe:

```text
what capability is being tested
what failure we expect
what the likely next primitive is
what previous models did
what future stages may contain
```

If the experimental agent can discover or read these files, the experiment becomes contaminated.

For example:

```text
docs/lab/agent_harness_lab_proposed_roadmap.md
```

may explicitly say:

```text
Stage 03 = mutation
```

If the model reads this during Stage 03, we can no longer distinguish:

```text
model inferred the next useful action
```

from:

```text
model was told what the experiment expects
```

Therefore introduce an explicit experimental-isolation boundary.

---

# 2. Conceptual model

The repository should distinguish:

```text
AGENT HARNESS LAB REPOSITORY
│
├── AGENT-VISIBLE WORKSPACE
│   │
│   ├── source code
│   ├── fixtures
│   ├── tests
│   ├── project configuration
│   ├── AGENTS.md
│   └── project knowledge intentionally exposed to the agent
│
└── EXPERIMENTER-ONLY STATE
    │
    ├── stage specifications
    ├── failure reports
    ├── roadmap
    ├── experimental analyses
    └── run artifacts / traces
```

The key distinction is:

```text
AGENTS.md
=
knowledge intended for the subject agent
```

versus:

```text
specs
failure logs
roadmap
run analyses
=
knowledge about the experiment being conducted on the subject agent
```

The second category must not be visible through normal agent tools.

---

# 3. Desired repository organization

Inspect the current repository before moving anything.

Prefer converging toward a structure conceptually like:

```text
repo/
│
├── AGENTS.md
├── README.md
├── pyproject.toml
├── uv.lock
├── config.toml
│
├── src/
├── tests/
├── fixtures/
├── scenarios/
│
├── lab/
│   ├── specs/
│   ├── failure_log/
│   ├── docs/
│   │   └── agent_harness_lab_proposed_roadmap.md
│   └── analyses/          # only if such files currently exist
│
└── runs/
```

The exact final structure should reflect what actually exists in the repository.

Do not create empty organizational directories merely for symmetry.

### Important

Prefer moving:

```text
specs/
→ lab/specs/

failure_log/
→ lab/failure_log/

lab-specific roadmap/docs
→ lab/docs/
```

If there are other documents that are clearly:

```text
experimenter-facing analysis of MiniHarness behavior
```

move them under `lab/` as appropriate.

Do not move ordinary project documentation merely because it is Markdown.

---

# 4. Treatment of `runs/`

`runs/` contains experiment output such as:

```text
response.md
events.jsonl
summary.json
llm_trace.jsonl
```

These are also experimenter-facing data and must not be visible to the experimental agent.

However, moving `runs/` may require changes to existing runtime/configuration behavior.

Therefore:

1. inspect how `runs_dir` is currently configured and used;
2. determine whether moving it under:

```text
lab/runs/
```

would be a trivial and low-risk configuration change;
3. if yes, moving it is acceptable;
4. if doing so introduces unnecessary runtime churn, leave `runs/` in its current physical location and classify it as experimenter-only through the visibility boundary.

Do not make a broad code refactor merely to move `runs/`.

The important property is:

```text
agent cannot discover/read run artifacts
```

not the exact physical directory name.

---

# 5. Preserve agent-visible project knowledge

The following should remain visible unless an existing reason says otherwise:

```text
AGENTS.md
pyproject.toml
config files relevant to project work
fixtures/
src/
tests/
scenario task content relevant to the active run
```

In particular:

```text
AGENTS.md
```

must **not** be hidden as part of this change.

It represents intentional project-facing guidance and is an important future experimental variable.

---

# 6. Scenario visibility

Inspect how scenario task files are currently used.

The active task is already loaded by the harness and provided directly to the model.

The model should not need unrestricted access to historical scenario specifications to complete a run.

Determine whether:

```text
scenarios/
```

contains only subject-facing task inputs or also contains experimenter-facing stage metadata.

If scenario directories contain only task files that are intentionally part of the experiment, they may remain visible.

If they contain stage explanations, expected outcomes, solution hints, or other experimenter metadata, separate those files from the task input.

Do not change task wording merely as part of this reorganization.

---

# 7. Introduce a minimal experimental visibility boundary

Implement the smallest explicit mechanism that prevents agent filesystem/execution tools from accessing experimenter-only metadata.

Do **not** build a generic permission framework.

Do **not** implement sandbox architecture.

A minimal concept is sufficient, for example:

```python
EXPERIMENTER_ONLY_ROOTS = (
    "lab",
    "runs",
)
```

or equivalent naming appropriate to the existing code.

If `runs/` is moved under `lab/`, then denying:

```text
lab/
```

may be sufficient.

The rule should apply consistently to agent-accessible tools.

At minimum inspect:

```text
list_files
read_file
run_pytest
```

---

# 8. `list_files` behavior

Experimenter-only metadata should ideally be invisible rather than merely unreadable.

For example:

```text
list_files(".")
```

should not return:

```text
lab/
lab/specs/
lab/failure_log/
runs/
```

The agent should not receive hints from directory names alone.

This is important.

The visibility boundary protects against:

```text
content leakage
```

and:

```text
metadata/name leakage
```

A file named:

```text
03_mutation_agent_spec.md
```

already reveals experimental information even if the agent cannot open it.

Therefore denied experimenter roots should be omitted from listings.

---

# 9. `read_file` behavior

Direct attempts to read experimenter metadata must fail.

For example:

```text
read_file("lab/docs/agent_harness_lab_proposed_roadmap.md")
```

should return a truthful tool-level denial.

Use simple wording such as:

```text
Access denied: experimenter-only lab metadata.
```

Do not pretend the file does not exist if the current tool semantics normally distinguish denial from missing files.

The important property is that file contents never reach the model.

---

# 10. `run_pytest` behavior

The Stage 02 execution primitive should respect the same experiment boundary.

A model should not be able to use:

```text
run_pytest
```

to target files under experimenter-only roots.

For example:

```text
run_pytest("lab/...")
```

should be rejected before subprocess execution.

Do not otherwise change `run_pytest` semantics.

Preserve:

```text
sys.executable -m pytest
repository-relative validation
timeout
output truncation
ToolResult.ok semantics
```

---

# 11. Centralize only what is necessary

Avoid implementing three unrelated hardcoded deny lists if the existing architecture makes a tiny shared helper natural.

A small helper such as:

```python
is_agent_visible_path(...)
```

or equivalent is acceptable.

Conceptually:

```text
repository boundary validation
        +
experimental visibility validation
```

should determine whether an agent-facing tool can access a path.

Do not generalize this into:

```text
ACL framework
role system
policy engine
permissions subsystem
sandbox
```

This is experimental isolation only.

---

# 12. Preserve `.env` protection

Existing `.env` protection must continue to work.

Do not replace it accidentally with only the new lab-metadata rule.

Conceptually we now have at least two different reasons for denial:

```text
.env
→ secret protection

lab metadata
→ experimental isolation
```

They are related at the tool boundary but conceptually distinct.

Keep both behaviors.

---

# 13. Update documentation references after moving files

Search the repository for references to old paths such as:

```text
specs/
failure_log/
docs/...
```

Update references where necessary.

Likely candidates:

```text
README.md
AGENTS.md
other lab documents
```

Be careful with `AGENTS.md`.

Do not add detailed roadmap or expected-stage information to `AGENTS.md`.

If it needs to reference experimenter documents, prefer not to expose their content or purpose to the agent.

Since `AGENTS.md` is agent-visible, avoid adding text such as:

```text
Stage 03 is mutation.
See lab/specs/03...
```

That would defeat the isolation boundary.

---

# 14. Roadmap location

Place the proposed roadmap under experimenter-only metadata, preferably:

```text
lab/docs/agent_harness_lab_proposed_roadmap.md
```

It must not be reachable through agent tools.

The roadmap remains useful to the human running the lab but must not become part of the subject agent's information state.

---

# 15. Specs and failure logs

Move existing stage specifications to:

```text
lab/specs/
```

Move existing failure logs to:

```text
lab/failure_log/
```

Preserve filenames and history as much as possible.

Do not rewrite their content except for path references that genuinely need updating.

Git should ideally recognize these as moves rather than unrelated delete/create operations where possible.

---

# 16. Do not hide normal repository orientation files

The model should still be able to discover ordinary repository state.

For example:

```text
AGENTS.md
README.md
pyproject.toml
src/
tests/
fixtures/
```

should remain available.

The purpose is not:

```text
show the agent only files required for the answer
```

The purpose is:

```text
remove experimenter-side information that changes the experimental condition
```

Normal repository exploration must remain possible.

---

# 17. Add tests for experimental isolation

Add focused regression tests.

At minimum verify:

### Root listing hides experimenter metadata

```text
list_files(".")
```

does not reveal:

```text
lab
runs
```

when those are configured as experimenter-only roots.

### Nested listing cannot expose lab metadata

Direct listing of:

```text
lab/
```

must be denied or otherwise inaccessible.

### Direct file read denied

```text
read_file("lab/docs/...")
```

must fail.

### Traversal cannot bypass isolation

Paths such as:

```text
somewhere/../lab/...
```

must still be denied after resolution.

### `run_pytest` cannot target experimenter metadata

Any target resolving inside the experimenter-only area must fail before subprocess execution.

### Agent-facing files remain available

Confirm that the change does not block:

```text
AGENTS.md
fixtures/tiny_checkout/discount.py
fixtures/tiny_checkout/test_discount.py
```

### Stage 01 tool set unchanged

Stage 01 must remain:

```text
list_files
read_file
```

### Stage 02 tool set unchanged

Stage 02 must remain:

```text
list_files
read_file
run_pytest
```

This reorganization adds no new model capability.

---

# 18. Run complete regression suite

Using the canonical uv workflow:

```bash
uv sync
uv run pytest
```

All tests must pass.

---

# 19. Re-run Stage 02 as an isolation regression

After the reorganization, run at least one Stage 02 baseline again:

```bash
MODEL_PROFILE=openai_luna \
uv run python -m miniharness.run \
scenarios/02_verify_only_agent/task.md \
--llm-trace
```

Do not compare exact trajectory or token counts.

Verify instead:

```text
agent can still inspect ordinary repository files
agent can still run pytest
agent can still reproduce the baseline failure
agent cannot see lab metadata
agent cannot see roadmap/spec/failure-log filenames
agent still stops at mutation boundary
```

Inspect `llm_trace.jsonl` and `events.jsonl` to confirm that no experimenter-only content reached the model.

---

# 20. Optional Anthropic regression

If inexpensive/convenient, repeat with:

```bash
MODEL_PROFILE=anthropic_haiku \
uv run python -m miniharness.run \
scenarios/02_verify_only_agent/task.md \
--llm-trace
```

This is optional if the generic ToolRegistry isolation tests are comprehensive.

Do not turn this into another model benchmark.

---

# 21. Important experimental invariant

Document the following invariant somewhere experimenter-facing, preferably under:

```text
lab/docs/
```

or the roadmap itself:

> Experimenter-only lab metadata must not be visible through agent tools unless a scenario explicitly studies access to that information.

This includes, by default:

```text
stage specs
failure reports
lab roadmap
experimental analyses
run traces/results
```

Future stages may intentionally override this rule, but only as part of an explicit experiment.

---

# 22. Information-state principle

Also record the reason for the boundary:

For model/harness trajectory comparisons to be meaningful, we should aim to preserve:

```text
same task
same tools
same agent-visible repository state
```

A model that reads hidden experimental hints is operating from a different information state.

Therefore experimental isolation is part of controlling the experiment.

---

# 23. New lab insight to record

Add a short experimenter-facing note capturing the insight that motivated this reorganization:

```text
As the lab generated its own specs, failure reports and roadmap,
the repository began containing knowledge about the experiment itself.

Because the agent can inspect the repository, experimenter metadata
became a possible source of task hints.

This revealed that agent experiments require control not only over
tools and prompts, but also over the environment's information surface.
```

And capture the distinction:

```text
PROJECT / SUBJECT KNOWLEDGE
=
information intentionally available to the agent

EXPERIMENTER KNOWLEDGE
=
information about expected behavior, failures and experiment design
```

This is a methodological learning from the lab, not a borrowed feature requirement.

---

# 24. Do not implement

Do not add:

```text
Stage 03 mutation
write_file
apply_patch
search_replace
general shell
permission prompts
sandboxing
context compaction
tool discovery
skills
MCP
subagents
planner
memory
```

Do not modify model prompts to tell them which directories are hidden.

The isolation should be enforced by the environment/tool surface.

---

# 25. Expected conceptual result

Before:

```text
MODEL
  ↓
list_files
  ↓
entire repository
  ↓
project state
+
experimenter metadata
```

After:

```text
MODEL
  ↓
agent tools
  ↓
AGENT-VISIBLE INFORMATION SURFACE
  ↓
project code
tests
fixtures
AGENTS.md
relevant configuration
```

while:

```text
EXPERIMENTER
  ↓
full repository
  ↓
lab/
runs/
roadmap
specs
failure reports
traces
```

---

# 26. Definition of Done

The reorganization is complete when:

```text
[✓] experimenter-only metadata has a clear repository location

[✓] stage specs live under experimenter-only state

[✓] failure logs live under experimenter-only state

[✓] roadmap lives under experimenter-only state

[✓] run artifacts are classified as experimenter-only

[✓] list_files does not reveal experimenter-only root names

[✓] read_file cannot access experimenter-only files

[✓] run_pytest cannot target experimenter-only files

[✓] AGENTS.md remains agent-visible

[✓] normal project files remain agent-visible

[✓] .env remains protected

[✓] Stage 01 tool capabilities are unchanged

[✓] Stage 02 tool capabilities are unchanged

[✓] uv run pytest passes

[✓] Stage 02 can still reproduce the baseline failure

[✓] raw trace confirms no lab metadata leaked into model context

[✓] no Stage 03 capability was introduced
```

---

# 27. Final report

At completion provide:

## Repository changes

Show the relevant before/after tree.

## Files moved

List every moved file or directory.

## Isolation mechanism

Explain exactly how agent-visible paths are determined.

## Tool behavior

Explain how:

```text
list_files
read_file
run_pytest
```

respect the boundary.

## Tests

Report:

```text
uv run pytest
```

result and the isolation-specific tests added.

## Stage 02 regression

Report the run directory and whether:

```text
baseline failure reproduced
lab metadata hidden
mutation boundary preserved
```

## Git diff

Show:

```bash
git status
git diff --stat
```

and summarize the intentional changes.

## Final verdict

End with exactly:

```text
EXPERIMENTAL ISOLATION PASSED — READY TO DESIGN STAGE 03
```

if all gates succeed.

Otherwise:

```text
EXPERIMENTAL ISOLATION INCOMPLETE — <specific blocker>
```

Do not begin Stage 03.
