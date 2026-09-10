"""Shared contracts for simulated and isolated real experiments."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field, model_validator

from labpilot.hpo.models import TrialStatus
from labpilot.hpo.search_space import SampledParameters
from labpilot.models.common import (
    DomainModel,
    ExperimentStatus,
    MetricDirection,
    NonNegative,
    Text,
    utc_now,
)
from labpilot.models.execution import CommitSHA, ExecutionProvenance, ExperimentPurpose, RawText
from labpilot.models.training import TrainingOverrides


class CodePatch(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    hypothesis_id: UUID
    description: Text
    diff: RawText
    experiment_id: UUID | None = None
    base_commit_sha: CommitSHA | None = None
    created_at: AwareDatetime = Field(default_factory=utc_now)


class Baseline(DomainModel):
    metric_name: Text = "validation_accuracy"
    value: float = Field(default=0.8, allow_inf_nan=False)
    direction: MetricDirection = MetricDirection.MAXIMIZE
    min_delta: float = Field(default=0.01, gt=0, allow_inf_nan=False)
    regression_delta: float = Field(default=0.01, gt=0, allow_inf_nan=False)


class ExperimentConfig(DomainModel):
    overrides: TrainingOverrides | None = None
    apply_patch: bool = True
    patch_diff: RawText = ""
    direction: MetricDirection = MetricDirection.MAXIMIZE
    seed: NonNegative = 42
    metric_name: Text = "validation_accuracy"

    @property
    def primary_metric(self) -> str:
        """The selected objective; preserve Phase 1's serialized metric_name field."""
        return self.metric_name


class Experiment(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    research_id: UUID | None = None
    purpose: ExperimentPurpose = ExperimentPurpose.CANDIDATE
    result: ExperimentResult | None = None
    hypothesis_id: UUID | None
    patch_id: UUID | None = None
    sequence: int = Field(ge=1)
    config: ExperimentConfig = Field(default_factory=ExperimentConfig)
    status: ExperimentStatus = ExperimentStatus.PENDING
    error: Text | None = None

    @model_validator(mode="after")
    def validate_error(self) -> Experiment:
        if (self.status == ExperimentStatus.FAILED) != (self.error is not None):
            raise ValueError("Only failed experiments must carry an error")
        return self


class Trial(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    experiment_id: UUID
    seed: NonNegative
    status: TrialStatus
    study_id: UUID | None = None
    research_id: UUID | None = None
    hypothesis_id: UUID | None = None
    optuna_trial_number: NonNegative | None = None
    parameters: SampledParameters = Field(default_factory=SampledParameters)
    primary_metric_name: Text | None = None
    primary_metric_value: float | None = Field(default=None, allow_inf_nan=False)
    failure_reason: Text | None = None
    started_at: AwareDatetime | None = None
    finished_at: AwareDatetime | None = None
    runtime_seconds: float = Field(default=0, ge=0, allow_inf_nan=False)
    created_at: AwareDatetime | None = None

    @property
    def pruned(self) -> bool:
        return self.status == TrialStatus.PRUNED

    @model_validator(mode="after")
    def validate_hpo_trial(self) -> Trial:
        if self.study_id is not None:
            if (
                self.research_id is None
                or self.hypothesis_id is None
                or self.optuna_trial_number is None
            ):
                raise ValueError("HPO trials require research, hypothesis and Optuna identities")
            if self.primary_metric_name is None:
                raise ValueError("HPO trials require a primary metric")
            if self.status == TrialStatus.SUCCEEDED and self.primary_metric_value is None:
                raise ValueError("Successful HPO trials require a metric")
            if self.status == TrialStatus.FAILED and not self.failure_reason:
                raise ValueError("Failed HPO trials require a reason")
            if self.status in {TrialStatus.SUCCEEDED, TrialStatus.FAILED, TrialStatus.PRUNED}:
                if (
                    self.started_at is None
                    or self.finished_at is None
                    or self.finished_at < self.started_at
                ):
                    raise ValueError("Terminal HPO trials require ordered execution timestamps")
        return self


class Metric(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    experiment_id: UUID
    trial_id: UUID
    name: Text
    value: float = Field(allow_inf_nan=False)


class ExperimentResult(DomainModel):
    """Boundary result; expected execution failures are data, not exceptions."""

    execution: ExecutionProvenance | None = None
    status: ExperimentStatus
    value: float | None = Field(default=None, allow_inf_nan=False)
    error: Text | None = None

    @model_validator(mode="after")
    def terminal_result(self) -> ExperimentResult:
        if self.status == ExperimentStatus.SUCCEEDED:
            if self.value is None or self.error is not None:
                raise ValueError("Successful result requires a metric and no error")
        elif self.status == ExperimentStatus.FAILED:
            if self.error is None or self.value is not None:
                raise ValueError("Failed result requires an error and no metric")
        else:
            raise ValueError("Runner must return a terminal result")
        return self


Experiment.model_rebuild()
