"""Minimal plan and study metadata; Optuna runtime objects never enter ResearchState."""

from enum import StrEnum
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from labpilot.hpo.search_space import SearchSpace, mnist_search_space
from labpilot.models.common import (
    ChangeType,
    DomainModel,
    MetricDirection,
    NonNegative,
    Text,
    utc_now,
)
from labpilot.models.training import TrainingOverrides


class TrialStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    PRUNED = "PRUNED"


class StudyStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class HPOConfig(DomainModel):
    max_trials: int = Field(default=6, ge=1)
    sampler_seed: int = Field(default=42, ge=0, le=2**32 - 1)
    search_space: SearchSpace = Field(default_factory=mnist_search_space)


class ExperimentPlan(DomainModel):
    id: UUID
    hypothesis_id: UUID
    patch_id: UUID | None = None
    rationale: Text = "Predefined Phase 3 inner-loop plan"
    change_type: ChangeType = ChangeType.CODE_CHANGE_WITH_HPO
    files_to_inspect: tuple[Text, ...] = ()
    files_to_modify: tuple[Text, ...] = ()
    configuration_overrides: TrainingOverrides | None = None
    search_space: SearchSpace | None = None
    primary_metric: Text
    direction: MetricDirection
    max_trials: int = Field(ge=1)
    estimated_runtime_seconds: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    falsification_criteria: Text | None = None
    expected_effect: Text | None = None
    validation_checks: tuple[Text, ...] = ()


class OptimizationStudy(DomainModel):
    id: UUID
    research_id: UUID
    hypothesis_id: UUID
    study_name: Text
    storage_path: Path
    plan_id: UUID
    search_space: SearchSpace
    primary_metric: Text
    direction: MetricDirection
    sampler_name: Literal["TPESampler"] = "TPESampler"
    sampler_seed: NonNegative
    seed_policy: Literal["seed_plus_trial_number_v1"] = "seed_plus_trial_number_v1"
    startup_trials: int = Field(default=3, ge=1)
    max_trials: int = Field(ge=1)
    completed_trials: NonNegative = 0
    failed_trials: NonNegative = 0
    pruned_trials: NonNegative = 0
    best_trial_id: UUID | None = None
    status: StudyStatus = StudyStatus.RUNNING
    failure_reason: Text | None = None
    created_at: AwareDatetime = Field(default_factory=utc_now)
    updated_at: AwareDatetime = Field(default_factory=utc_now)
