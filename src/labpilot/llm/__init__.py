"""Provider-independent structured LLM boundary and DeepSeek implementation."""

from __future__ import annotations

from labpilot.llm.client import LLMClient, StructuredLLMResult
from labpilot.llm.deepseek import DeepSeekLLMClient

__all__ = ["DeepSeekLLMClient", "LLMClient", "StructuredLLMResult"]
