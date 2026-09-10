"""Deterministic structured client for offline workflow and retry tests."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel

from labpilot.llm.client import StructuredLLMResult
from labpilot.llm.models import LLMUsage

T = TypeVar("T", bound=BaseModel)


class FakeLLMClient:
    def __init__(self, responses: Iterable[BaseModel | dict[str, object] | str]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def generate_structured(
        self,
        *,
        research_id: UUID,
        operation: str,
        prompt_template: str,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        max_output_tokens: int | None = None,
        max_attempts: int | None = None,
        max_total_tokens: int | None = None,
    ) -> StructuredLLMResult[T]:
        del system_prompt, max_output_tokens, max_attempts, max_total_tokens
        if self.calls >= len(self.responses):
            raise AssertionError("Fake LLM response queue exhausted")
        raw = self.responses[self.calls]
        self.calls += 1
        if isinstance(raw, BaseModel):
            output = response_model.model_validate(raw.model_dump())
        elif isinstance(raw, str):
            output = response_model.model_validate_json(raw)
        else:
            output = response_model.model_validate(raw)
        input_tokens = max(1, len(user_prompt) // 4)
        output_tokens = max(1, len(json.dumps(output.model_dump(mode="json"))) // 4)
        usage = LLMUsage(
            request_id=f"fake-{self.calls}",
            research_id=research_id,
            operation=operation,
            prompt_template=prompt_template,
            model="fake-structured",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            latency_seconds=0,
        )
        return StructuredLLMResult(output=output, usage=(usage,))
