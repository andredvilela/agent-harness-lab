from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .trace import TRACE_MODES


@dataclass(frozen=True)
class ModelConfig:
    profile: str
    provider: str
    model: str
    max_output_tokens: int


@dataclass(frozen=True)
class AgentConfig:
    max_turns: int


@dataclass(frozen=True)
class DebugConfig:
    llm_trace: str


@dataclass(frozen=True)
class LabConfig:
    runs_dir: Path
    repo_root: Path
    model: ModelConfig
    agent: AgentConfig
    debug: DebugConfig


def _parse_llm_trace_mode(value: object) -> str:
    mode = str(value).strip()
    if mode not in TRACE_MODES:
        allowed = ", ".join(TRACE_MODES)
        raise ValueError(
            f"Invalid debug.llm_trace={value!r}. Expected one of: {allowed}"
        )
    return mode


def load_config() -> LabConfig:
    load_dotenv()

    config_path = Path(os.getenv("CONFIG_PATH", "config.toml"))

    with config_path.open("rb") as f:
        raw = tomllib.load(f)

    profile = os.getenv("MODEL_PROFILE", "openai_luna")
    model_raw = raw["models"][profile]
    lab_raw = raw.get("lab", {})
    agent_raw = raw.get("agent", {})
    debug_raw = raw.get("debug", {})

    return LabConfig(
        runs_dir=Path(lab_raw.get("runs_dir", "runs")),
        repo_root=Path(lab_raw.get("repo_root", ".")).resolve(),
        model=ModelConfig(
            profile=profile,
            provider=model_raw["provider"],
            model=model_raw["model"],
            max_output_tokens=model_raw["max_output_tokens"],
        ),
        agent=AgentConfig(
            max_turns=int(agent_raw.get("max_turns", 10)),
        ),
        debug=DebugConfig(
            llm_trace=_parse_llm_trace_mode(debug_raw.get("llm_trace", "off")),
        ),
    )
