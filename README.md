# MiniHarness

Minimal provider-neutral agent harness used in this repository.

The harness loads a task, runs an agent loop against a model provider, and exposes a small set of repository tools. Implementation lives in `src/miniharness/`.

## Setup

`uv` manages the project-local `.venv` and locked dependencies.

```bash
uv sync
```

Copy `.env.example` to `.env` and fill in provider API keys. Select a model profile with `MODEL_PROFILE`. Model IDs live in `config.toml`, not in `.env`.

Activation of `.venv` is optional. Prefer `uv run` for all project commands.

## Tests

```bash
uv run pytest
```

## Run a scenario

```bash
MODEL_PROFILE=openai_luna \
uv run python -m miniharness.run scenarios/<scenario>/task.md
```

Examples:

```bash
MODEL_PROFILE=openai_luna \
uv run python -m miniharness.run scenarios/01_read_only_agent/task.md

MODEL_PROFILE=anthropic_haiku \
uv run python -m miniharness.run scenarios/02_verify_only_agent/task.md
```

Shell environment variables override `.env`.

## Repository structure

```text
src/miniharness/   harness implementation
tests/             harness unit tests
fixtures/          small project fixtures used by scenarios
scenarios/         task files for agent runs
AGENTS.md          project instructions for the agent
config.toml        model profiles and harness settings
pyproject.toml     project metadata and dependencies
```
