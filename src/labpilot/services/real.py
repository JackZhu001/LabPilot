"""Real-mode setup and experiment state transitions shared by graph and CLI."""

import difflib
import shutil
from dataclasses import replace
from pathlib import Path
from uuid import uuid5

from labpilot.execution.git import WorktreeManager, git
from labpilot.execution.runner import DockerExperimentRunner
from labpilot.hpo.models import TrialStatus
from labpilot.models.common import ExperimentStatus, Step
from labpilot.models.execution import ExecutionConfig, ExecutionEnvironment, ExperimentPurpose
from labpilot.models.experiments import (
    Baseline,
    CodePatch,
    Experiment,
    ExperimentConfig,
    Metric,
    Trial,
)
from labpilot.models.state import ResearchState
from labpilot.services.fakes import fake_services
from labpilot.services.interfaces import ResearchServices


def services_for(state: ResearchState) -> ResearchServices:
    services = fake_services(state.simulation)
    if state.execution.environment == ExecutionEnvironment.DOCKER:
        return replace(services, experiment=DockerExperimentRunner(state.execution))
    return services


def prepare_example(source: Path, destination: Path) -> Path:
    """Create a dedicated baseline repository; refuse to overwrite any destination."""
    if destination.exists():
        raise ValueError(f"Destination already exists: {destination}")
    source, destination = source.resolve(), destination.resolve()
    shutil.copytree(
        source, destination, ignore=shutil.ignore_patterns(".git", "__pycache__", "outputs")
    )
    git(destination, "init", "--initial-branch=baseline")
    git(destination, "add", ".")
    git(
        destination,
        "-c",
        "user.name=LabPilot",
        "-c",
        "user.email=labpilot@example.invalid",
        "commit",
        "-m",
        "Initialize MNIST baseline fixture",
    )
    return destination


def predefined_dropout_patch(repo: Path) -> str:
    """Build a fixed 0.0 → 0.3 configuration intervention without writing the repo."""
    original = (repo / "config.yaml").read_text()
    if original.count("dropout: 0.0\n") != 1:
        raise ValueError("Predefined patch requires exactly one 'dropout: 0.0' configuration line")
    updated = original.replace("dropout: 0.0\n", "dropout: 0.3\n")
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile="a/config.yaml",
            tofile="b/config.yaml",
        )
    )


def configure_docker(
    repo: Path,
    runtime_root: Path,
    *,
    patch: Path | None = None,
    image: str = "labpilot-mnist:phase2",
    build_image: bool = True,
    timeout_seconds: float = 180,
    training_command: tuple[str, ...] = ("python", "train.py"),
) -> ExecutionConfig:
    repo, runtime_root = repo.resolve(), runtime_root.resolve()
    manager = WorktreeManager(repo, runtime_root / "worktrees")
    sha = manager.validate_clean_baseline()
    diff = patch.read_text() if patch else predefined_dropout_patch(repo)
    # Format/conflict validation happens inside the experiment so failures are durable results.
    return ExecutionConfig(
        environment=ExecutionEnvironment.DOCKER,
        baseline_repo_path=repo,
        base_commit_sha=sha,
        runtime_root=runtime_root,
        patch_diff=diff,
        image=image,
        build_image=build_image,
        timeout_seconds=timeout_seconds,
        training_command=training_command,
    )


def execute_real_experiment(
    state: ResearchState,
    services: ResearchServices,
    *,
    purpose: ExperimentPurpose,
) -> ResearchState:
    """One runner invocation and one budget charge, committed by the existing node adapter."""
    baseline_run = purpose == ExperimentPurpose.BASELINE
    identity = (
        f"baseline:{state.budget.experiments + 1}"
        if baseline_run
        else f"experiment:{state.iteration}"
    )
    experiment_id = uuid5(state.research_id, identity)
    hypothesis_id = None if baseline_run else state.active_hypothesis_id
    patch: CodePatch | None = None
    if not baseline_run:
        if hypothesis_id is None:
            raise ValueError("Candidate experiment requires a hypothesis")
        patch = CodePatch(
            id=uuid5(experiment_id, "patch"),
            hypothesis_id=hypothesis_id,
            experiment_id=experiment_id,
            base_commit_sha=state.execution.base_commit_sha,
            description="Predefined experiment patch",
            diff=state.execution.patch_diff,
        )
    experiment = Experiment(
        id=experiment_id,
        research_id=state.research_id,
        purpose=purpose,
        hypothesis_id=hypothesis_id,
        sequence=state.budget.experiments + 1,
        patch_id=patch.id if patch else None,
        status=ExperimentStatus.RUNNING,
        config=ExperimentConfig(
            seed=state.simulation.seed,
            metric_name=state.baseline.metric_name,
            direction=state.baseline.direction,
        ),
    )
    result = services.experiment.run(experiment, state.baseline)
    experiment = Experiment.model_validate(
        {
            **experiment.model_dump(),
            "status": result.status,
            "error": result.error,
            "result": result,
        }
    )
    trial = Trial(
        id=uuid5(experiment_id, "trial:0"),
        experiment_id=experiment_id,
        seed=experiment.config.seed,
        status=TrialStatus(result.status.value),
    )
    metrics = state.metrics
    if result.status == ExperimentStatus.SUCCEEDED:
        if result.execution and result.execution.report:
            values = result.execution.report.metrics
        else:
            assert result.value is not None
            values = {state.baseline.metric_name: result.value}
        metrics = (
            *metrics,
            *(
                Metric(
                    id=uuid5(trial.id, name),
                    experiment_id=experiment_id,
                    trial_id=trial.id,
                    name=name,
                    value=value,
                )
                for name, value in values.items()
            ),
        )
    changes: dict[str, object] = {
        "experiments": (*state.experiments, experiment),
        "trials": (*state.trials, trial),
        "metrics": metrics,
        "patches": (*state.patches, patch) if patch else state.patches,
        "budget": state.budget.consume(
            experiments=1, failed_experiments=int(result.status == ExperimentStatus.FAILED)
        ),
        "next_step": Step.ANALYZE,
    }
    if baseline_run and result.status == ExperimentStatus.SUCCEEDED:
        changes.update(
            baseline=Baseline.model_validate(
                {**state.baseline.model_dump(), "value": result.value}
            ),
            baseline_experiment_id=experiment.id,
            next_step=Step.HYPOTHESIS,
        )
    return state.evolve(**changes)
