"""Coordinate an isolated worktree, Docker execution, and durable artifacts."""

import logging
import os
import shutil
import time

from labpilot.execution.artifacts import ArtifactError, capture_source, create_artifacts
from labpilot.execution.docker import DockerClient, DockerError
from labpilot.execution.git import GitError, WorktreeManager
from labpilot.execution.metrics import MetricsError, MetricsParser
from labpilot.models.common import ExperimentStatus, utc_now
from labpilot.models.execution import (
    DockerMetadata,
    ExecutionConfig,
    ExecutionProvenance,
    ExecutionStatus,
    ExperimentPurpose,
    GitMetadata,
    MetricReport,
)
from labpilot.models.experiments import Baseline, Experiment, ExperimentResult

logger = logging.getLogger(__name__)


class DockerExperimentRunner:
    """Expected execution failures return structured results; orchestration stays unaware."""

    def __init__(self, config: ExecutionConfig, docker: DockerClient | None = None) -> None:
        self.config = config
        self.docker = docker or DockerClient()
        if config.baseline_repo_path is None:
            raise ValueError("Docker runner requires a baseline repository")
        self.worktrees = WorktreeManager(
            config.baseline_repo_path, config.runtime_root / "worktrees"
        )

    def run(self, experiment: Experiment, baseline: Baseline) -> ExperimentResult:
        config = self.config
        if experiment.research_id is None or config.base_commit_sha is None:
            raise ValueError("Real experiments require research identity and base commit")
        started = utc_now()
        timer = time.monotonic()
        try:
            artifacts = create_artifacts(config.runtime_root, experiment.research_id, experiment.id)
        except (ArtifactError, OSError) as exc:
            return ExperimentResult(status=ExperimentStatus.FAILED, error=str(exc))
        path = config.runtime_root / "worktrees" / str(experiment.id)
        git_metadata = GitMetadata(
            baseline_repo_path=self.worktrees.baseline,
            base_commit_sha=config.base_commit_sha,
            worktree_path=path,
            worktree_identity=f"detached:{experiment.id}",
        )
        docker_metadata = DockerMetadata(
            image=config.image, cpus=config.cpus, memory_mb=config.memory_mb
        )
        report: MetricReport | None = None
        failure: str | None = None
        status = ExecutionStatus.FAILED
        exit_code: int | None = None
        cleanup_errors: list[str] = []
        created = False
        configuration_text: str | None = None
        source_hash: str | None = None
        try:
            patch = (
                experiment.config.patch_diff or config.patch_diff
                if experiment.purpose == ExperimentPurpose.CANDIDATE
                and experiment.config.apply_patch
                else ""
            )
            artifacts.patch_path.write_text(patch)
            path = self.worktrees.create_worktree(experiment.id, config.base_commit_sha)
            created = True
            if experiment.purpose == ExperimentPurpose.CANDIDATE and patch:
                self.worktrees.apply_patch(path, patch, config.base_commit_sha)
            actual_diff = self.worktrees.get_diff(path)
            artifacts.actual_diff_path.write_text(actual_diff)
            git_metadata = git_metadata.model_copy(update={"actual_git_diff": actual_diff})
            source_hash = capture_source(
                path, self.worktrees.tracked_files(path), artifacts.source_path
            )
            if config.dataset_cache_path is not None:
                shutil.copytree(
                    config.dataset_cache_path,
                    artifacts.source_path / ".labpilot-dataset",
                    copy_function=os.link,
                )
            if experiment.config.overrides is not None:
                parameter_path = artifacts.source_path / "labpilot-parameters.json"
                if parameter_path.exists():
                    raise ArtifactError(
                        "Reserved generated parameter file already exists in source"
                    )
                parameter_path.write_text(
                    experiment.config.overrides.model_dump_json(exclude_none=True)
                )
                artifacts = artifacts.model_copy(update={"parameters_path": parameter_path})
            config_file = artifacts.source_path / "config.yaml"
            if config_file.is_file():
                configuration_text = config_file.read_text()
            image_id = self.docker.prepare_image(config, artifacts)
            docker_metadata = docker_metadata.model_copy(update={"image_id": image_id})
            execution = self.docker.run(
                config,
                artifacts,
                experiment.id,
                image_id,
                experiment.config.seed,
                experiment.config.metric_name,
                experiment.config.direction.value,
            )
            docker_metadata = docker_metadata.model_copy(
                update={"container_id": execution.container_id}
            )
            exit_code = execution.exit_code
            cleanup_errors.extend(execution.cleanup_errors)
            if execution.timed_out:
                status = ExecutionStatus.TIMED_OUT
                failure = f"Training exceeded {config.timeout_seconds:g} second timeout"
            elif execution.failure_reason is not None:
                failure = execution.failure_reason
            elif exit_code != 0:
                failure = f"Training exited with code {exit_code}"
            else:
                report = MetricsParser().parse(
                    artifacts.metrics_path, experiment.config.metric_name
                )
                if report.metadata is not None and report.metadata.seed != experiment.config.seed:
                    raise MetricsError("Reported random seed differs from the experiment seed")
                if config.dataset is not None:
                    if report.metadata is None:
                        raise MetricsError("Dataset runs require versioned metric metadata")
                    if (
                        report.metadata.dataset_name != config.dataset.name
                        or report.metadata.dataset_version != config.dataset.version
                        or report.metadata.split_policy != config.dataset.split_policy
                    ):
                        raise MetricsError(
                            "Reported dataset metadata differs from execution config"
                        )
                status = ExecutionStatus.SUCCEEDED
        except DockerError as exc:
            failure = str(exc)
            cleanup_errors.extend(exc.cleanup_errors)
        except (GitError, MetricsError, ArtifactError, OSError) as exc:
            failure = str(exc)
        finally:
            if created:
                try:
                    self.worktrees.cleanup_worktree(path)
                except GitError as exc:
                    cleanup_errors.append(str(exc))
            try:
                after = self.worktrees.get_head_sha()
                self.worktrees.validate_clean_baseline(config.base_commit_sha)
                git_metadata = git_metadata.model_copy(
                    update={
                        "baseline_sha_after": after,
                        "baseline_clean_after": True,
                    }
                )
            except GitError as exc:
                failure = f"Baseline integrity verification failed: {exc}; prior failure: {failure}"
                status = ExecutionStatus.FAILED
                git_metadata = git_metadata.model_copy(update={"baseline_clean_after": False})
        for error in cleanup_errors:
            logger.warning("cleanup_failed experiment_id=%s error=%s", experiment.id, error)
        provenance = ExecutionProvenance(
            research_id=experiment.research_id,
            experiment_id=experiment.id,
            hypothesis_id=experiment.hypothesis_id,
            git=git_metadata,
            docker=docker_metadata,
            artifacts=artifacts,
            training_command=config.training_command,
            configuration_text=configuration_text,
            training_overrides=experiment.config.overrides,
            dataset=config.dataset,
            source_sha256=source_hash,
            random_seed=experiment.config.seed,
            started_at=started,
            finished_at=utc_now(),
            runtime_seconds=time.monotonic() - timer,
            exit_code=exit_code,
            status=status,
            failure_reason=failure,
            cleanup_errors=tuple(cleanup_errors),
            report=report,
        )
        artifacts.provenance_path.write_text(provenance.model_dump_json(indent=2))
        if status == ExecutionStatus.SUCCEEDED:
            assert report is not None
            return ExperimentResult(
                status=ExperimentStatus.SUCCEEDED,
                value=report.metrics[experiment.config.metric_name],
                execution=provenance,
            )
        return ExperimentResult(status=ExperimentStatus.FAILED, error=failure, execution=provenance)
