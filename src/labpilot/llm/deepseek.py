"""DeepSeek OpenAI-compatible JSON adapter; credentials never enter domain state."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Protocol, TypeVar
from uuid import UUID

import httpx
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
)
from pydantic import BaseModel, ValidationError

from labpilot.llm.client import StructuredLLMResult
from labpilot.llm.errors import (
    LLMAuthenticationError,
    LLMBudgetError,
    LLMConfigurationError,
    LLMTransientError,
    StructuredOutputError,
)
from labpilot.llm.models import LLMSettings, LLMUsage

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class CompletionRequest:
    model: str
    system_prompt: str
    user_prompt: str
    temperature: float
    max_output_tokens: int
    timeout_seconds: float
    thinking_enabled: bool
    reasoning_effort: str


@dataclass(frozen=True)
class CompletionResponse:
    request_id: str
    model: str
    content: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None


class CompletionTransport(Protocol):
    def complete(self, request: CompletionRequest) -> CompletionResponse: ...


class OpenAICompletionTransport:
    def __init__(self, settings: LLMSettings, api_key: str) -> None:
        self.client = OpenAI(
            api_key=api_key,
            base_url=str(settings.base_url).rstrip("/"),
            timeout=settings.timeout_seconds,
            http_client=httpx.Client(trust_env=False),
            # Retries must remain explicit so every accepted response is accounted for.
            max_retries=0,
        )

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        response = self.client.chat.completions.create(
            model=request.model,
            messages=[
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=request.temperature,
            max_tokens=request.max_output_tokens,
            timeout=request.timeout_seconds,
            extra_body={
                "thinking": {
                    "type": "enabled" if request.thinking_enabled else "disabled",
                    "reasoning_effort": request.reasoning_effort,
                }
            },
        )
        message = response.choices[0].message.content if response.choices else None
        usage = response.usage
        if usage is None:
            raise LLMTransientError("DeepSeek response omitted token usage")
        prompt_details = usage.prompt_tokens_details
        completion_details = usage.completion_tokens_details
        return CompletionResponse(
            request_id=response.id,
            model=response.model,
            content=message or "",
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            cached_input_tokens=(
                prompt_details.cached_tokens if prompt_details is not None else None
            ),
            reasoning_tokens=(
                completion_details.reasoning_tokens if completion_details is not None else None
            ),
        )


class DeepSeekLLMClient:
    def __init__(self, settings: LLMSettings, transport: CompletionTransport | None = None) -> None:
        self.settings = settings
        if transport is None:
            api_key = os.environ.get("DEEPSEEK_API_KEY", "")
            if not api_key:
                raise LLMConfigurationError("DEEPSEEK_API_KEY is required")
            transport = OpenAICompletionTransport(settings, api_key)
        self.transport = transport

    @classmethod
    def from_environment(cls) -> DeepSeekLLMClient:
        return cls(LLMSettings.from_environment())

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
        schema = json.dumps(response_model.model_json_schema(), separators=(",", ":"))
        instruction = (
            f"Return one JSON object matching this JSON Schema exactly: {schema}. "
            "Do not use markdown fences or add prose outside the JSON object."
        )
        usages: list[LLMUsage] = []
        validation_feedback = ""
        attempts = min(
            self.settings.max_retries + 1,
            max_attempts if max_attempts is not None else self.settings.max_retries + 1,
        )
        for attempt in range(attempts):
            prompt = f"{user_prompt}\n\n{instruction}{validation_feedback}"
            output_limit = max_output_tokens or self.settings.max_output_tokens
            if max_total_tokens is not None:
                used_tokens = sum(item.total_tokens for item in usages)
                # Every tokenizer token contains at least one UTF-8 byte. Reserving the
                # complete request byte length therefore safely bounds its input tokens.
                input_reserve = len(f"{system_prompt}\n{prompt}".encode())
                output_limit = min(output_limit, max_total_tokens - used_tokens - input_reserve)
                if output_limit < 128:
                    raise LLMBudgetError(
                        "LLM token budget cannot safely fund another request", tuple(usages)
                    )
            request = CompletionRequest(
                model=self.settings.model,
                system_prompt=system_prompt,
                user_prompt=prompt,
                temperature=self.settings.temperature,
                max_output_tokens=output_limit,
                timeout_seconds=self.settings.timeout_seconds,
                thinking_enabled=self.settings.thinking_enabled,
                reasoning_effort=self.settings.reasoning_effort,
            )
            started = time.monotonic()
            try:
                response = self.transport.complete(request)
            except AuthenticationError as exc:
                raise LLMAuthenticationError(
                    "DeepSeek authentication failed", tuple(usages)
                ) from exc
            except (APIConnectionError, APITimeoutError, LLMTransientError) as exc:
                if attempt < attempts - 1:
                    continue
                raise LLMTransientError("DeepSeek connection failed", tuple(usages)) from exc
            except APIStatusError as exc:
                if exc.status_code in {401, 403}:
                    raise LLMAuthenticationError(
                        "DeepSeek authentication failed", tuple(usages)
                    ) from exc
                if exc.status_code in {408, 409, 429} or exc.status_code >= 500:
                    if attempt < attempts - 1:
                        continue
                    raise LLMTransientError(
                        f"DeepSeek returned HTTP {exc.status_code}", tuple(usages)
                    ) from exc
                raise LLMConfigurationError(
                    f"DeepSeek rejected the request with HTTP {exc.status_code}", tuple(usages)
                ) from exc
            elapsed = time.monotonic() - started
            usage = LLMUsage(
                request_id=response.request_id,
                research_id=research_id,
                operation=operation,
                prompt_template=prompt_template,
                model=response.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                total_tokens=response.input_tokens + response.output_tokens,
                cached_input_tokens=response.cached_input_tokens,
                reasoning_tokens=response.reasoning_tokens,
                latency_seconds=elapsed,
            )
            usages.append(usage)
            if (
                max_total_tokens is not None
                and sum(item.total_tokens for item in usages) > max_total_tokens
            ):
                raise LLMBudgetError("Provider usage exceeded the LLM token budget", tuple(usages))
            if not response.content.strip():
                error = "Response content was empty"
            else:
                try:
                    output = response_model.model_validate_json(response.content)
                except ValidationError as exc:
                    error = str(exc)
                else:
                    return StructuredLLMResult(output=output, usage=tuple(usages))
            validation_feedback = (
                "\nThe previous JSON was invalid. Correct these validation errors: " + error[:2000]
            )
            if attempt == attempts - 1:
                raise StructuredOutputError(
                    "DeepSeek did not return valid structured output", tuple(usages)
                )
        raise AssertionError("unreachable")
