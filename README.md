# Agent Harness Lab

A hands-on lab for learning agent harness engineering by failure.

## Principle

A new harness component is introduced only after the current harness hits a concrete execution barrier that the component can address.

## Stage 00 — Model Only

Current system:

```text
task -> model -> text response
```

It has:
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

Give the model a repository task it cannot actually perform and observe the failure mode.

### Run

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate

pip install -e .

set OPENAI_API_KEY=...
set MODEL=<your-api-model-id>
python -m miniharness.run scenarios/00_model_only/task.md
```

PowerShell:

```powershell
$env:OPENAI_API_KEY="..."
$env:MODEL="<your-api-model-id>"
python -m miniharness.run scenarios/00_model_only/task.md
```


Every execution creates an immutable folder under `runs/`.

## Stage rule

Do not add repository tools yet.

First inspect what the model does when asked to modify a repository it cannot inspect.

Possible failure modes:
- asks for the files;
- invents repository structure;
- returns a speculative patch;
- explains that it cannot inspect the repository;
- claims success without evidence.

Record the observed failure before proceeding to Stage 01.
