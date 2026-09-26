from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from labpilot.execution.docker import ContainerResult, DockerClient, DockerError
from labpilot.execution.git import GitError, git
from labpilot.execution.runner import DockerExperimentRunner
from labpilot.models.common import ExperimentStatus
from labpilot.models.execution import ExecutionConfig, ExperimentArtifact, ExperimentPurpose
from labpilot.models.experiments import Baseline, Experiment, ExperimentConfig
from labpilot.services.real import configure_docker, prepare_example


class FixtureDocker(DockerClient):
    def __init__(self, outcome: str = "success") -> None:
        self.outcome = outcome
        self.calls = 0

    def prepare_image(self, config: ExecutionConfig, artifacts: ExperimentArtifact) -> str:
        if self.outcome == "build":
            raise DockerError("Docker build failed")
        return "sha256:fixture"

    def run(
        self,
        config: ExecutionConfig,
        artifacts: ExperimentArtifact,
        experiment_id: UUID,
        image_id: str,
        seed: int,
        metric_name: str = "validation_accuracy",
        direction: str = "MAXIMIZE",
    ) -> ContainerResult:
        del metric_name, direction
        self.calls += 1
        if self.outcome == "missing":
            pass
        elif self.outcome == "malformed":
            artifacts.metrics_path.write_text("invalid")
        elif self.outcome == "primary":
            artifacts.metrics_path.write_text('{"schema_version":1,"metrics":{"other":0.9}}')
        else:
            artifacts.metrics_path.write_text(
                '{"schema_version":1,"metrics":{"validation_accuracy":0.9}}'
            )
        return ContainerResult(
            "fixture-container", 1 if self.outcome == "exit" else 0, self.outcome == "timeout"
        )


@pytest.fixture()
def execution_config(tmp_path: Path) -> ExecutionConfig:
    source = tmp_path / "source"
    source.mkdir()
    (source / "config.yaml").write_text("seed: 42\ndropout: 0.0\n")
    repo = prepare_example(source, tmp_path / "baseline")
    return configure_docker(repo, tmp_path / "runtime", build_image=False)


def experiment() -> Experiment:
    return Experiment(research_id=uuid4(), hypothesis_id=uuid4(), sequence=1)


@pytest.mark.parametrize(
    ("outcome", "reason"),
    [
        ("build", "build failed"),
        ("exit", "code 1"),
        ("timeout", "timeout"),
        ("missing", "Missing"),
        ("malformed", "Invalid metrics"),
        ("primary", "Missing primary"),
    ],
)
def test_structured_failures(execution_config: ExecutionConfig, outcome: str, reason: str) -> None:
    result = DockerExperimentRunner(execution_config, FixtureDocker(outcome)).run(
        experiment(), Baseline()
    )
    assert result.status == ExperimentStatus.FAILED
    assert reason in result.error
    assert result.execution.git.baseline_clean_after
    assert result.execution.git.baseline_sha_after == execution_config.base_commit_sha
    assert result.execution.artifacts.provenance_path.is_file()
    assert not result.execution.git.worktree_path.exists()


def test_success_records_exact_source(execution_config: ExecutionConfig) -> None:
    result = DockerExperimentRunner(execution_config, FixtureDocker()).run(experiment(), Baseline())
    assert result.status == ExperimentStatus.SUCCEEDED and result.value == 0.9
    assert "+dropout: 0.3" in result.execution.git.actual_git_diff
    assert result.execution.docker.image_id == "sha256:fixture"
    assert result.execution.configuration_text == "seed: 42\ndropout: 0.3\n"
    assert result.execution.source_sha256
    assert not (result.execution.artifacts.source_path / ".git").exists()
    assert result.execution.artifacts.stdout_path.exists()
    assert result.execution.artifacts.stderr_path.exists()
    assert git(execution_config.baseline_repo_path, "status", "--porcelain") == ""


def test_experiment_patch_overrides_stale_runner_configuration(
    execution_config: ExecutionConfig,
) -> None:
    patch = (
        "--- a/config.yaml\n+++ b/config.yaml\n@@ -1,2 +1,2 @@\n"
        " seed: 42\n-dropout: 0.0\n+dropout: 0.1\n"
    )
    candidate = experiment().model_copy(update={"config": ExperimentConfig(patch_diff=patch)})
    result = DockerExperimentRunner(execution_config, FixtureDocker()).run(candidate, Baseline())
    assert result.status == ExperimentStatus.SUCCEEDED
    assert "+dropout: 0.1" in result.execution.git.actual_git_diff
    assert "+dropout: 0.3" not in result.execution.git.actual_git_diff


@pytest.mark.parametrize(
    "patch",
    ["invalid", "--- a/config.yaml\n+++ b/config.yaml\n@@ -1 +1 @@\n-nonexistent\n+changed\n"],
)
def test_bad_patch_is_structured(execution_config: ExecutionConfig, patch: str) -> None:
    config = execution_config.model_copy(update={"patch_diff": patch})
    docker = FixtureDocker()
    result = DockerExperimentRunner(config, docker).run(experiment(), Baseline())
    assert result.status == ExperimentStatus.FAILED
    assert docker.calls == 0
    assert result.execution.git.baseline_clean_after


def test_cleanup_failure_preserves_metric(
    execution_config: ExecutionConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = DockerExperimentRunner(execution_config, FixtureDocker())
    cleanup = runner.worktrees.cleanup_worktree

    def fail(path: Path) -> None:
        raise GitError("cleanup", "Fixture cleanup failure")

    monkeypatch.setattr(runner.worktrees, "cleanup_worktree", fail)
    result = runner.run(experiment(), Baseline())
    assert result.status == ExperimentStatus.SUCCEEDED and result.value == 0.9
    assert "Fixture cleanup failure" in result.execution.cleanup_errors[0]
    cleanup(result.execution.git.worktree_path)


def test_unmodified_baseline_uses_same_runner(execution_config: ExecutionConfig) -> None:
    candidate = experiment()
    baseline = Experiment.model_validate(
        {**candidate.model_dump(), "hypothesis_id": None, "purpose": ExperimentPurpose.BASELINE}
    )
    result = DockerExperimentRunner(execution_config, FixtureDocker()).run(baseline, Baseline())
    assert result.status == ExperimentStatus.SUCCEEDED
    assert result.execution.git.actual_git_diff == ""
    assert "dropout: 0.0" in result.execution.configuration_text


def test_provenance_validation(execution_config: ExecutionConfig) -> None:
    result = DockerExperimentRunner(execution_config, FixtureDocker()).run(experiment(), Baseline())
    raw = result.execution.model_dump()
    raw["exit_code"] = 1
    with pytest.raises(ValidationError):
        type(result.execution).model_validate(raw)


def test_patch_text_preserves_whitespace(execution_config: ExecutionConfig) -> None:
    assert execution_config.patch_diff.endswith("\n")
    restored = ExecutionConfig.model_validate_json(execution_config.model_dump_json())
    assert restored.patch_diff == execution_config.patch_diff
