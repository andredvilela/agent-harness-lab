# Agent Harness Lab

A hands-on lab for learning agent harness engineering by failure.

## Principle

A new harness component is introduced only after the current harness hits a concrete execution barrier that the component can address.

```text
MODEL BEHAVIOR
       ≠
HARNESS CAPABILITY
```

## Stage 0A — Naked Model

Architecture:

```text
task
  ↓
model
  ↓
text
```

The harness has:
- no agent loop
- no repository access
- no tools
- no editing
- no shell
- no verification
- no project instructions
- no context manager
- no persistence beyond a single run

This is intentional.

### Goal

Observe what happens when a model receives a task that would require acting on the environment, but no action capability is provided.

The first baseline was executed with GPT-5.6 Luna (`openai_luna`).

The task lives in `scenarios/00_model_only/task.md` and asks the model to fix a bug in `fixtures/tiny_checkout/` without giving it repository access.

Possible failure modes:
- asks for the files;
- invents repository structure;
- returns a speculative patch;
- attempts tool-like text despite having no tools;
- explains that it cannot inspect the repository;
- claims success without evidence.

Record the observed failure. Do not add repository tools yet.

Internal run identifier remains `00_model_only` for historical compatibility.

## Stage 0B — Model Behavior Survey

Stage 0B freezes:

```text
task
prompt
harness
tools = none
```

and varies only:

```text
provider/model
```

This is not a statistical benchmark and not a ranking. It is a qualitative survey of how different model classes behave when given an agentic task they cannot operationally execute.

The four profiles are:

| Profile | Provider | Class | Model |
|---|---|---|---|
| `openai_luna` | OpenAI | economic | GPT-5.6 Luna |
| `openai_sol` | OpenAI | frontier | GPT-5.6 Sol |
| `anthropic_haiku` | Anthropic | economic | Claude Haiku 4.5 |
| `anthropic_opus` | Anthropic | frontier | Claude Opus 5 |

What to observe:
- whether the model notices the absence of tools;
- propensity to attempt tool use even without tools;
- propensity to invent repository facts;
- honesty about inability to verify;
- strategy chosen when the task is impossible;
- coarse differences in tokens/latency.

Compare runs in `comparisons/00b_model_behavior_survey.md`. Classification is manual.

### Setup

Canonical workflow: `uv` manages the project-local `.venv` and locked dependencies.

```bash
uv sync
```

Copy `.env.example` to `.env` and fill in provider keys. Select a profile with `MODEL_PROFILE`. Model IDs live in `config.toml`, not in `.env`.

Activation of `.venv` is optional. Prefer `uv run` for all project commands.

### Run the four profiles

```bash
MODEL_PROFILE=openai_luna uv run python -m miniharness.run scenarios/00_model_only/task.md

MODEL_PROFILE=openai_sol uv run python -m miniharness.run scenarios/00_model_only/task.md

MODEL_PROFILE=anthropic_haiku uv run python -m miniharness.run scenarios/00_model_only/task.md

MODEL_PROFILE=anthropic_opus uv run python -m miniharness.run scenarios/00_model_only/task.md
```

Shell environment variables override `.env`. Every execution creates an immutable folder under `runs/`.

### Tests

```bash
uv run pytest
```

## Specs

Stage specifications from Stage 01 onward live in `specs/`.

Stage 01 tool calling runs through the same AgentLoop on both the OpenAI Responses API and the Anthropic Messages API. See `specs/01a_anthropic_tool_calling_adapter.md`.

Optional provider I/O tracing is documented in `specs/01b_llm_provider_io_trace.md`. It is off by default. `--llm-trace` writes `llm_trace.jsonl`; `--llm-trace-stdout` prints the same payloads. Raw LLM tracing can persist the complete context sent to a provider, including source code and tool outputs. Do not enable file tracing on sensitive workloads unless storing that data is acceptable.
