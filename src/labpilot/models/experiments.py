"""Experiment contracts; Phase 1 never executes code or trains a model."""

from uuid import UUID, uuid4

from pydantic import Field, model_validator

from labpilot.models.common import (
    DomainModel,
    ExperimentStatus,
    MetricDirection,
    NonNegative,
    Text,
)


class CodePatch(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    hypothesis_id: UUID
    description: Text
    diff: Text


class Baseline(DomainModel):
    metric_name: Text = "validation_accuracy"
    value: float = Field(default=0.8, allow_inf_nan=False)
    direction: MetricDirection = MetricDirection.MAXIMIZE
    min_delta: float = Field(default=0.01, gt=0, allow_inf_nan=False)
    regression_delta: float = Field(default=0.01, gt=0, allow_inf_nan=False)


class ExperimentConfig(DomainModel):
    seed: NonNegative = 42
    metric_name: Text = "validation_accuracy"


class Experiment(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    hypothesis_id: UUID
    patch_id: UUID | None = None
    sequence: int = Field(ge=1)
    config: ExperimentConfig = Field(default_factory=ExperimentConfig)
    status: ExperimentStatus = ExperimentStatus.PENDING
    error: Text | None = None

    @model_validator(mode="after")
    def validate_error(self) -> "Experiment":
        if (self.status == ExperimentStatus.FAILED) != (self.error is not None):
            raise ValueError("Only failed experiments must carry an error")
        return self


class Trial(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    experiment_id: UUID
    seed: NonNegative
    status: ExperimentStatus


class Metric(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    experiment_id: UUID
    trial_id: UUID
    name: Text
    value: float = Field(allow_inf_nan=False)


class ExperimentResult(DomainModel):
    """Boundary result; expected execution failures are data, not exceptions."""

    status: ExperimentStatus
    value: float | None = Field(default=None, allow_inf_nan=False)
    error: Text | None = None

    @model_validator(mode="after")
    def terminal_result(self) -> "ExperimentResult":
        if self.status == ExperimentStatus.SUCCEEDED:
            if self.value is None or self.error is not None:
                raise ValueError("Successful result requires a metric and no error")
        elif self.status == ExperimentStatus.FAILED:
            if self.error is None or self.value is not None:
                raise ValueError("Failed result requires an error and no metric")
        else:
            raise ValueError("Runner must return a terminal result")
        return self
