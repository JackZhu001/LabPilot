"""Generic typed request contract used by all logical LLM roles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar
from uuid import UUID

from pydantic import BaseModel

from labpilot.llm.models import LLMUsage

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class StructuredLLMResult(Generic[T]):
    output: T
    usage: tuple[LLMUsage, ...]


class LLMClient(Protocol):
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
    ) -> StructuredLLMResult[T]: ...
