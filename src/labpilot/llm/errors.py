"""Structured failures at the LLM provider and validation boundary."""

from __future__ import annotations

from labpilot.llm.models import LLMUsage


class LLMError(RuntimeError):
    def __init__(self, message: str, usages: tuple[LLMUsage, ...] = ()) -> None:
        super().__init__(message)
        self.usages = usages


class LLMConfigurationError(LLMError):
    pass


class LLMAuthenticationError(LLMError):
    pass


class LLMTransientError(LLMError):
    pass


class StructuredOutputError(LLMError):
    pass


class LLMBudgetError(LLMError):
    pass
