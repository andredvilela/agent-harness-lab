# Agent Harness Lab

A hands-on lab for learning agent harness engineering by failure.

This document is experimenter-facing. It lives under `lab/` and is not visible through agent tools.

---

## Purpose

The lab introduces harness primitives only after a scenario demonstrates a concrete execution barrier that the new primitive can address.

```text
MODEL BEHAVIOR
       ≠
HARNESS CAPABILITY
```

Build from observed necessity, not from feature imitation.

---

## Document classification rule

For any document, ask:

```text
Would a real coding agent working on this project,
without knowing it is being studied,
reasonably need access to this?
```

If yes → root / normal project docs (`README.md`, `AGENTS.md`, source, fixtures, tests, scenarios).

If no — because it contains experiment design, expected trajectories, model comparisons, failure analysis, next primitives, or roadmap — it belongs under `lab/`.

```text
PROJECT / SUBJECT KNOWLEDGE     → agent-visible
EXPERIMENTER KNOWLEDGE          → lab/ (and runs/)
```

See `docs/experimental_isolation.md` for the tool boundary.

---

## Experimental isolation

Agent tools cannot discover or read:

```text
lab/
runs/
```

The root `README.md` describes the MiniHarness as a normal project. It does not describe what the experiment is trying to discover.

`AGENTS.md` remains agent-visible as intentional project-facing guidance.

---

## Completed stages

### Stage 00 — Naked Model

Architecture:

```text
task → model → text
```

No agent loop, no repository access, no tools, no editing, no shell, no verification.

- Scenario: `scenarios/00_model_only/task.md`
- Failure log: `failure_log/0A_naked_model.md`
- Survey: `docs/00b_model_behavior_survey.md`

### Stage 01 — Read-Only Agent

Added `list_files` and `read_file` through a provider-neutral agent loop.

- Scenario: `scenarios/01_read_only_agent/task.md`
- Spec: `specs/01_read_only_agent.md`
- Failure log: `failure_log/01_read_only_agent.md`
- Closeout: `failure_log/01_stage_closeout_report.md`
- Adapter spec: `specs/01a_anthropic_tool_calling_adapter.md`
- Trace spec: `specs/01b_llm_provider_io_trace.md`

### Stage 02 — Verify-Only Agent

Added `run_pytest` for runtime evidence without mutation.

- Scenario: `scenarios/02_verify_only_agent/task.md`
- Spec: `specs/02_verify_only_agent_spec_uv_linux.md`
- Failure log: `failure_log/02_verify_only_agent.md`

Observed boundary at close:

```text
OBSERVATION              = YES
RUNTIME EXECUTION        = YES
BASELINE REPRODUCTION    = YES
MUTATION                 = NO
POST-FIX VERIFICATION    = NO
```

---

## Stage 03 hypothesis

At the time of writing, the strongest hypothesis is:

```text
Stage 03 = introduce the smallest useful mutation primitive
```

This is a hypothesis, not a commitment. Stage 03 design has not started.

See `docs/agent_harness_lab_proposed_roadmap.md` for the full non-binding curriculum map.

---

## Repository organization

```text
lab/
├── README.md              this overview
├── specs/                 stage specifications
├── failure_log/           observed failures per stage
└── docs/                  roadmap, isolation notes, analyses

runs/                      immutable run artifacts (experimenter-only)
```

Reorganization spec: `specs/repo_visibility.md`.

---

## Running experiments

Setup and tests use the same `uv` workflow as the root README.

### Run a stage scenario

```bash
MODEL_PROFILE=openai_luna \
uv run python -m miniharness.run scenarios/02_verify_only_agent/task.md
```

### Model behavior survey (Stage 0B)

Same naked harness, same task, vary only `MODEL_PROFILE`:

| Profile | Provider | Class | Model |
|---|---|---|---|
| `openai_luna` | OpenAI | economic | GPT-5.6 Luna |
| `openai_sol` | OpenAI | frontier | GPT-5.6 Sol |
| `anthropic_haiku` | Anthropic | economic | Claude Haiku 4.5 |
| `anthropic_opus` | Anthropic | frontier | Claude Opus 5 |

Compare runs manually using `docs/00b_model_behavior_survey.md`.

### Provider I/O tracing

Optional. Off by default.

```bash
MODEL_PROFILE=openai_luna \
uv run python -m miniharness.run scenarios/02_verify_only_agent/task.md --llm-trace
```

`--llm-trace` writes `llm_trace.jsonl` under `runs/<run-id>/`. `--llm-trace-stdout` prints the same payloads. Raw tracing can persist the complete context sent to a provider, including source code and tool outputs.

---

## Key references

- `docs/agent_harness_lab_proposed_roadmap.md` — proposed, non-binding curriculum
- `docs/experimental_isolation.md` — isolation invariant and rationale
- `docs/00b_model_behavior_survey.md` — Stage 0B qualitative survey template
- `failure_log/TEMPLATE.md` — template for new failure reports

---

## Documentation rule

For each stage, record:

1. the attempted task;
2. the observed failure;
3. why the current harness could not overcome it;
4. the next primitive introduced;
5. what changed after introducing it.
