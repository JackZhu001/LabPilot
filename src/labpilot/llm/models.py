"""Persistable Phase 4 settings, structured outputs, provenance, and critique."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Annotated, Literal, Self
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field, HttpUrl, model_validator

from labpilot.hpo.search_space import SearchSpace
from labpilot.models.common import (
    ChangeType,
    Confidence,
    DomainModel,
    MetricDirection,
    NonNegative,
    ResearchDecision,
    Text,
    utc_now,
)
from labpilot.models.execution import RawText
from labpilot.models.training import TrainingOverrides


class LLMSettings(DomainModel):
    provider: Literal["deepseek"] = "deepseek"
    model: Text = "deepseek-v4-pro"
    base_url: HttpUrl = HttpUrl("https://api.deepseek.com")
    temperature: Annotated[float, Field(ge=0, le=2, allow_inf_nan=False)] = 0.2
    max_output_tokens: int = Field(default=4096, ge=128, le=32768)
    thinking_enabled: bool = False
    reasoning_effort: Literal["low", "high", "max"] = "low"
    timeout_seconds: float = Field(default=120, gt=0, le=600, allow_inf_nan=False)
    max_retries: int = Field(default=2, ge=0, le=4)
    max_patch_repairs: int = Field(default=1, ge=0, le=2)

    @classmethod
    def from_environment(cls, env: Mapping[str, str] | None = None) -> LLMSettings:
        values = os.environ if env is None else env
        return cls.model_validate(
            {
                "base_url": values.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                "model": values.get("DEEPSEEK_MODEL", "deepseek-v4-pro"),
            }
        )


class LLMUsage(DomainModel):
    request_id: Text
    research_id: UUID
    operation: Text
    prompt_template: Text
    model: Text
    input_tokens: NonNegative
    output_tokens: NonNegative
    total_tokens: NonNegative
    cached_input_tokens: NonNegative | None = None
    reasoning_tokens: NonNegative | None = None
    latency_seconds: float = Field(ge=0, allow_inf_nan=False)
    created_at: AwareDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def token_total(self) -> Self:
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("Total tokens must equal input plus output tokens")
        return self


class InspectedFile(DomainModel):
    path: Text
    size_bytes: NonNegative


class RepositoryInspection(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    repo_path: Text
    base_commit_sha: Text
    training_entrypoint: Text
    important_files: tuple[InspectedFile, ...] = Field(min_length=1, max_length=32)
    file_tree: tuple[Text, ...] = Field(min_length=1, max_length=256)
    context_characters: NonNegative
    model_summary: Text
    configuration_summary: Text
    available_hyperparameters: tuple[Text, ...]
    primary_metric: Text
    metric_direction: MetricDirection
    possible_change_points: tuple[Text, ...] = Field(max_length=12)
    constraints: tuple[Text, ...] = Field(max_length=12)
    warnings: tuple[Text, ...] = Field(max_length=12)


class RepositoryInspectionSummary(DomainModel):
    training_entrypoint: Text
    model_summary: Text
    configuration_summary: Text
    available_hyperparameters: tuple[Text, ...] = Field(max_length=16)
    primary_metric: Text
    metric_direction: MetricDirection
    possible_change_points: tuple[Text, ...] = Field(min_length=1, max_length=12)
    constraints: tuple[Text, ...] = Field(max_length=12)
    warnings: tuple[Text, ...] = Field(max_length=12)


class HypothesisProposal(DomainModel):
    statement: Text
    motivation: Text
    expected_effect: Text
    expected_impact: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    confidence: Confidence
    estimated_cost: float = Field(ge=0, allow_inf_nan=False)
    falsification_criteria: Text
    change_type: ChangeType


class HypothesisBatch(DomainModel):
    proposals: tuple[HypothesisProposal, ...] = Field(min_length=1, max_length=3)


class ExperimentPlanProposal(DomainModel):
    rationale: Text
    change_type: ChangeType
    files_to_inspect: tuple[Text, ...] = Field(max_length=12)
    files_to_modify: tuple[Text, ...] = Field(max_length=6)
    configuration_overrides: TrainingOverrides | None = None
    search_space: SearchSpace | None = None
    primary_metric: Text
    direction: MetricDirection
    estimated_trials: int = Field(default=1, ge=1, le=32)
    estimated_runtime_seconds: float = Field(gt=0, allow_inf_nan=False)
    falsification_criteria: Text
    expected_effect: Text
    validation_checks: tuple[Text, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def change_contract(self) -> Self:
        if self.change_type == ChangeType.CONFIG_ONLY and self.files_to_modify:
            raise ValueError("CONFIG_ONLY plans cannot modify source files")
        if self.change_type == ChangeType.CONFIG_ONLY and self.configuration_overrides is None:
            raise ValueError("CONFIG_ONLY plans require validated configuration overrides")
        if self.change_type in {ChangeType.CODE_CHANGE, ChangeType.CODE_CHANGE_WITH_HPO}:
            if not self.files_to_modify:
                raise ValueError("Code-change plans require at least one target file")
        if self.change_type == ChangeType.CODE_CHANGE_WITH_HPO and self.search_space is None:
            raise ValueError("CODE_CHANGE_WITH_HPO requires a search space")
        if self.change_type != ChangeType.CODE_CHANGE_WITH_HPO and self.search_space is not None:
            raise ValueError("Only CODE_CHANGE_WITH_HPO plans may contain a search space")
        return self


class PatchProposal(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    hypothesis_id: UUID
    target_files: tuple[Text, ...] = Field(min_length=1, max_length=6)
    base_commit_sha: Text
    unified_diff: RawText
    explanation: Text
    risk_notes: tuple[Text, ...] = Field(max_length=8)
    repair_attempt: NonNegative = 0


class ResearchCritique(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    hypothesis_id: UUID
    decision: ResearchDecision
    summary: Text
    likely_explanation: Text
    next_step_advice: Text
    adequately_tested: bool


class PromptReference(DomainModel):
    template_id: Text
    version: Text = "v1"
