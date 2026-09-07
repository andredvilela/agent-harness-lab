from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class ModelConfig:
    profile: str
    provider: str
    model: str
    max_output_tokens: int


@dataclass(frozen=True)
class LabConfig:
    runs_dir: Path
    model: ModelConfig


def load_config() -> LabConfig:
    load_dotenv()

    config_path = Path(os.getenv("CONFIG_PATH", "config.toml"))

    with config_path.open("rb") as f:
        raw = tomllib.load(f)

    profile = os.getenv("MODEL_PROFILE", "openai_luna")
    model_raw = raw["models"][profile]

    return LabConfig(
        runs_dir=Path(raw.get("lab", {}).get("runs_dir", "runs")),
        model=ModelConfig(
            profile=profile,
            provider=model_raw["provider"],
            model=model_raw["model"],
            max_output_tokens=model_raw["max_output_tokens"],
        ),
    )
