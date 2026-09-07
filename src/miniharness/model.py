from dataclasses import dataclass
from typing import Protocol

from anthropic import Anthropic
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
    def __init__(self, model: str, max_output_tokens: int):
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.client = OpenAI()

    def generate(self, prompt: str) -> ModelResult:
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            max_output_tokens=self.max_output_tokens,
        )

        usage = getattr(response, "usage", None)
        return ModelResult(
            text=response.output_text,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )


class AnthropicModelClient:
    def __init__(self, model: str, max_output_tokens: int):
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.client = Anthropic()

    def generate(self, prompt: str) -> ModelResult:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_output_tokens,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        text_parts = [
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        ]

        usage = getattr(response, "usage", None)
        return ModelResult(
            text="".join(text_parts),
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )


def create_model_client(config: ModelConfig) -> ModelClient:
    if config.provider == "openai":
        return OpenAIModelClient(
            model=config.model,
            max_output_tokens=config.max_output_tokens,
        )

    if config.provider == "anthropic":
        return AnthropicModelClient(
            model=config.model,
            max_output_tokens=config.max_output_tokens,
        )

    raise ValueError(f"Unsupported provider: {config.provider}")
