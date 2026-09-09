"""Typed execution configuration, metric contracts, and durable provenance."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, StringConstraints, model_validator

from labpilot.models.common import DomainModel, NonNegative, Text
from labpilot.models.training import TrainingOverrides

RawText = Annotated[str, StringConstraints(strip_whitespace=False)]

FiniteMetric = Annotated[float, Field(allow_inf_nan=False, strict=True)]
CommitSHA = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]


class ExecutionEnvironment(StrEnum):
    FAKE = "fake"
    DOCKER = "docker"


class ExecutionStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


class ExperimentPurpose(StrEnum):
    BASELINE = "BASELINE"
    CANDIDATE = "CANDIDATE"


class MetricMetadata(DomainModel):
    seed: NonNegative
    epochs: Annotated[int, Field(gt=0, strict=True)]


class MetricReport(DomainModel):
    """Versioned numeric name/value mapping; never parsed from human-readable logs."""

    schema_version: Literal[1]
    metrics: dict[Text, FiniteMetric] = Field(min_length=1)
    metadata: MetricMetadata | None = None


class ExecutionConfig(DomainModel):
    environment: ExecutionEnvironment = ExecutionEnvironment.FAKE
    baseline_repo_path: Path | None = None
    base_commit_sha: CommitSHA | None = None
    runtime_root: Path = Path(".labpilot")
    patch_diff: RawText = ""
    training_command: tuple[Text, ...] = ("python", "train.py")
    image: Text = "labpilot-mnist:phase2"
    build_image: bool = True
    timeout_seconds: float = Field(default=180, gt=0, allow_inf_nan=False)
    build_timeout_seconds: float = Field(default=1200, gt=0, allow_inf_nan=False)
    cpus: float = Field(default=2, gt=0, allow_inf_nan=False)
    memory_mb: int = Field(default=2048, ge=128)

    @model_validator(mode="after")
    def real_requirements(self) -> Self:
        if not self.training_command:
            raise ValueError("Training command cannot be empty")
        if self.environment == ExecutionEnvironment.DOCKER:
            if self.baseline_repo_path is None or self.base_commit_sha is None:
                raise ValueError("Docker execution requires a repository and exact base commit")
            if not self.baseline_repo_path.is_absolute() or not self.runtime_root.is_absolute():
                raise ValueError(
                    "Persist absolute repository and runtime paths for reliable resume"
                )
            if self.runtime_root.is_relative_to(self.baseline_repo_path):
                raise ValueError("Runtime directories must live outside the baseline repository")
        return self


class ExperimentArtifact(DomainModel):
    parameters_path: Path | None = None
    stdout_path: Path
    stderr_path: Path
    metrics_path: Path
    provenance_path: Path
    patch_path: Path
    actual_diff_path: Path
    source_path: Path


class GitMetadata(DomainModel):
    baseline_repo_path: Path
    base_commit_sha: CommitSHA
    baseline_sha_after: CommitSHA | None = None
    baseline_clean_after: bool | None = None
    worktree_path: Path
    worktree_identity: Text
    actual_git_diff: RawText = ""


class DockerMetadata(DomainModel):
    image: Text
    image_id: Text | None = None
    container_id: Text | None = None
    network: Literal["none"] = "none"
    cpus: float
    memory_mb: int


class ExecutionProvenance(DomainModel):
    research_id: UUID
    experiment_id: UUID
    hypothesis_id: UUID | None
    git: GitMetadata
    docker: DockerMetadata
    artifacts: ExperimentArtifact
    training_command: tuple[Text, ...]
    configuration_text: RawText | None = None
    training_overrides: TrainingOverrides | None = None
    source_sha256: Text | None = None
    random_seed: NonNegative
    started_at: AwareDatetime
    finished_at: AwareDatetime
    runtime_seconds: float = Field(ge=0, allow_inf_nan=False)
    exit_code: int | None = None
    status: ExecutionStatus
    failure_reason: Text | None = None
    cleanup_errors: tuple[Text, ...] = ()
    report: MetricReport | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.finished_at < self.started_at:
            raise ValueError("Execution finish precedes start")
        if self.status == ExecutionStatus.SUCCEEDED:
            if self.failure_reason is not None or self.report is None or self.exit_code != 0:
                raise ValueError("Successful execution requires exit zero, metrics, and no failure")
        elif self.failure_reason is None:
            raise ValueError("Failed execution requires a reason")
        return self
