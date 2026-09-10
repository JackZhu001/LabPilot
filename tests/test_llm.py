from __future__ import annotations

from collections.abc import Iterable
from uuid import uuid4

import pytest
from pydantic import BaseModel

from labpilot.llm.deepseek import (
    CompletionRequest,
    CompletionResponse,
    DeepSeekLLMClient,
)
from labpilot.llm.errors import LLMBudgetError, LLMConfigurationError, LLMTransientError
from labpilot.llm.models import LLMSettings


class Answer(BaseModel):
    value: int


class RecordingTransport:
    def __init__(self, responses: Iterable[CompletionResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[CompletionRequest] = []

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.requests.append(request)
        return self.responses.pop(0)


class TransientTransport:
    def __init__(self) -> None:
        self.requests: list[CompletionRequest] = []

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.requests.append(request)
        if len(self.requests) == 1:
            raise LLMTransientError("temporary outage")
        return response('{"value":7}', 2)


class InvalidThenTransientTransport:
    def __init__(self) -> None:
        self.requests = 0

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        del request
        self.requests += 1
        if self.requests == 1:
            return response('{"wrong":1}', 1)
        raise LLMTransientError("temporary outage")


def response(content: str, number: int) -> CompletionResponse:
    return CompletionResponse(
        request_id=f"request-{number}",
        model="deepseek-v4-pro",
        content=content,
        input_tokens=10,
        output_tokens=3,
    )


def test_environment_settings_and_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = LLMSettings.from_environment(
        {"DEEPSEEK_BASE_URL": "https://example.invalid/v1", "DEEPSEEK_MODEL": "fixture"}
    )
    assert str(settings.base_url) == "https://example.invalid/v1"
    assert settings.model == "fixture"
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(LLMConfigurationError, match="DEEPSEEK_API_KEY"):
        DeepSeekLLMClient(LLMSettings())


def test_request_construction_validation_retry_and_usage() -> None:
    transport = RecordingTransport((response('{"wrong":1}', 1), response('{"value":7}', 2)))
    client = DeepSeekLLMClient(LLMSettings(max_retries=1), transport)
    result = client.generate_structured(
        research_id=uuid4(),
        operation="contract_test",
        prompt_template="test:v1",
        system_prompt="Return JSON.",
        user_prompt="Give an answer as JSON.",
        response_model=Answer,
    )
    assert result.output.value == 7
    assert len(result.usage) == len(transport.requests) == 2
    assert sum(item.total_tokens for item in result.usage) == 26
    first, second = transport.requests
    assert first.model == "deepseek-v4-pro"
    assert "JSON Schema" in first.user_prompt
    assert "previous JSON was invalid" in second.user_prompt
    assert not hasattr(first, "api_key")


def test_token_budget_stops_validation_retry_and_preserves_usage() -> None:
    transport = RecordingTransport((response('{"wrong":1}', 1), response('{"value":7}', 2)))
    client = DeepSeekLLMClient(LLMSettings(max_retries=1), transport)
    with pytest.raises(LLMBudgetError) as caught:
        client.generate_structured(
            research_id=uuid4(),
            operation="budget_test",
            prompt_template="test:v1",
            system_prompt="Return JSON.",
            user_prompt="Give an answer as JSON.",
            response_model=Answer,
            max_total_tokens=600,
        )
    assert len(transport.requests) == 1
    assert len(caught.value.usages) == 1


def test_transient_failure_retries_explicitly() -> None:
    transport = TransientTransport()
    client = DeepSeekLLMClient(LLMSettings(max_retries=1), transport)
    result = client.generate_structured(
        research_id=uuid4(),
        operation="retry_test",
        prompt_template="test:v1",
        system_prompt="Return JSON.",
        user_prompt="Give an answer as JSON.",
        response_model=Answer,
    )
    assert result.output.value == 7
    assert len(transport.requests) == 2
    assert len(result.usage) == 1


def test_later_transient_failure_preserves_accepted_usage() -> None:
    transport = InvalidThenTransientTransport()
    client = DeepSeekLLMClient(LLMSettings(max_retries=1), transport)
    with pytest.raises(LLMTransientError) as caught:
        client.generate_structured(
            research_id=uuid4(),
            operation="retry_accounting_test",
            prompt_template="test:v1",
            system_prompt="Return JSON.",
            user_prompt="Give an answer as JSON.",
            response_model=Answer,
        )
    assert transport.requests == 2
    assert len(caught.value.usages) == 1
