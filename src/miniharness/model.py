from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI

from .config import ModelConfig


@dataclass(frozen=True)
class ModelResult:
    text: str
    input_tokens: int | None
    output_tokens: int | None


class ModelClient(Protocol):
    def generate(self, prompt: str) -> ModelResult:
        ...


class OpenAIModelClient:
    def __init__(self, model: str):
        self.model = model
        self.client = OpenAI()

    def generate(self, prompt: str) -> ModelResult:
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
        )

        usage = getattr(response, "usage", None)
        return ModelResult(
            text=response.output_text,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )


def create_model_client(config: ModelConfig) -> ModelClient:
    if config.provider == "openai":
        return OpenAIModelClient(model=config.model)

    raise ValueError(f"Unsupported provider: {config.provider}")
