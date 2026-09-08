# Experimental Isolation

This document records a methodological constraint of the Agent Harness Lab.

It is experimenter-facing. It must not be visible through agent tools unless a scenario explicitly studies access to this information.

---

## Invariant

Experimenter-only lab metadata must not be visible through agent tools unless a scenario explicitly studies access to that information.

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

## Why the boundary exists

As the lab generated its own specs, failure reports and roadmap,
the repository began containing knowledge about the experiment itself.

Because the agent can inspect the repository, experimenter metadata
became a possible source of task hints.

This revealed that agent experiments require control not only over
tools and prompts, but also over the environment's information surface.

---

## Two kinds of knowledge

```text
PROJECT / SUBJECT KNOWLEDGE
=
information intentionally available to the agent
```

Examples: `AGENTS.md`, source, fixtures, tests, ordinary project configuration, the root `README.md`.

```text
EXPERIMENTER KNOWLEDGE
=
information about expected behavior, failures and experiment design
```

Examples: stage specs, failure logs, the proposed roadmap, run traces, `lab/README.md`.

`AGENTS.md` remains agent-visible. It is project-facing guidance and a future experimental variable. It is not hidden by this boundary.

---

## Two READMEs

The repository uses two README files with different roles:

| File | Audience | Role |
|---|---|---|
| `README.md` (root) | agent-visible | MiniHarness setup, tests, scenarios, project structure |
| `lab/README.md` | experimenter-only | lab purpose, methodology, stages, isolation, roadmap pointers |

The root README must not describe experiment design, expected trajectories, model comparisons, or future stages. That content belongs in `lab/README.md`.

---

## Document classification rule

For any new document, ask:

```text
Would a real coding agent working on this project,
without knowing it is being studied,
reasonably need access to this?
```

If yes → root / normal project docs.

If no → `lab/`.

---

## Information-state principle

For model/harness trajectory comparisons to be meaningful, we should aim to preserve:

```text
same task
same tools
same agent-visible repository state
```

A model that reads hidden experimental hints is operating from a different information state.

Therefore experimental isolation is part of controlling the experiment.

---

## Current boundary

Agent tools cannot discover or read:

```text
lab/
runs/
```

`runs/` stays at the repository root. Moving it under `lab/` would have required runtime/config churn. The visibility rule classifies it as experimenter-only regardless of that physical location.

Denied roots are omitted from `list_files` listings. Direct reads and `run_pytest` targets that resolve inside those roots fail with:

```text
Access denied: experimenter-only lab metadata.
```

Secret protection for `.env` remains a separate denial.

The model is not told which directories are hidden. Isolation is enforced by the tool surface.
