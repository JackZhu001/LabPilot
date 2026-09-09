"""Explicit Docker checks: actual MNIST, persisted resume, timeout, and nonzero exit."""

import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from labpilot.execution.git import git
from labpilot.execution.runner import DockerExperimentRunner
from labpilot.graph.workflow import execute
from labpilot.models.budget import ResearchBudget
from labpilot.models.common import ExperimentStatus, RunStatus
from labpilot.models.execution import ExperimentPurpose
from labpilot.models.experiments import Baseline, Experiment
from labpilot.models.state import ResearchState
from labpilot.persistence.repository import SQLiteResearchRepository
from labpilot.services.real import configure_docker, prepare_example

pytestmark = pytest.mark.docker
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def docker_ready() -> None:
    try:
        available = subprocess.run(["docker", "info"], capture_output=True, timeout=20, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("Docker is unavailable")
    if available.returncode:
        pytest.skip("Docker daemon is unavailable")


@pytest.fixture(scope="module")
def image(docker_ready: None) -> str:
    # Build errors with a reachable daemon are test failures, never skips.
    name = "labpilot-mnist:phase2"
    subprocess.run(
        ["docker", "build", "-t", name, str(ROOT / "examples/mnist_baseline")],
        check=True,
        timeout=1200,
        capture_output=True,
    )
    return name


def test_mnist_baseline_patch_and_resume(tmp_path: Path, image: str) -> None:
    repo = prepare_example(ROOT / "examples/mnist_baseline", tmp_path / "baseline")
    before = git(repo, "rev-parse", "HEAD").strip()
    config = configure_docker(repo, tmp_path / "runtime", image=image, build_image=False)
    database = tmp_path / "runs.sqlite3"
    store = SQLiteResearchRepository(database)
    initial = store.create(
        ResearchState(
            research_goal="Dropout comparison",
            execution=config,
            budget=ResearchBudget(max_experiments=2, max_replans=0),
        )
    )
    paused = execute(store, initial.research_id, stop_after=5)
    assert len(paused.experiments) == 2
    assert all(exp.status == ExperimentStatus.SUCCEEDED for exp in paused.experiments), (
        paused.model_dump_json()
    )
    store.close()
    reopened = SQLiteResearchRepository(database)
    completed = execute(reopened, initial.research_id)
    assert completed.status == RunStatus.COMPLETED
    assert completed.experiments == paused.experiments
    assert completed.budget.experiments == 2
    assert completed.baseline_experiment_id == completed.experiments[0].id
    for exp in completed.experiments:
        execution = exp.result.execution
        assert execution.git.baseline_clean_after
        assert execution.docker.image_id.startswith("sha256:")
        assert execution.artifacts.metrics_path.is_file()
        assert not execution.git.worktree_path.exists()
    assert completed.experiments[0].result.execution.git.actual_git_diff == ""
    assert "+dropout: 0.3" in completed.experiments[1].result.execution.git.actual_git_diff
    assert git(repo, "rev-parse", "HEAD").strip() == before
    assert git(repo, "status", "--porcelain") == ""
    reopened.close()


@pytest.mark.parametrize(
    ("command", "timeout", "reason"),
    [
        (("python", "-c", "import time; time.sleep(30)"), 1.0, "timeout"),
        (("python", "-c", "raise SystemExit(7)"), 15.0, "code 7"),
        (("python", "-c", "print('No metrics written')"), 15.0, "Missing"),
    ],
)
def test_real_container_failure(
    tmp_path: Path, image: str, command: tuple[str, ...], timeout: float, reason: str
) -> None:
    repo = prepare_example(ROOT / "examples/mnist_baseline", tmp_path / "baseline")
    config = configure_docker(
        repo,
        tmp_path / "runtime",
        image=image,
        build_image=False,
        training_command=command,
        timeout_seconds=timeout,
    )
    experiment = Experiment(
        research_id=uuid4(), hypothesis_id=None, purpose=ExperimentPurpose.BASELINE, sequence=1
    )
    result = DockerExperimentRunner(config).run(experiment, Baseline())
    assert result.status == ExperimentStatus.FAILED and reason in result.error
    assert result.execution.git.baseline_clean_after
    remaining = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"name=labpilot-{experiment.id}", "-q"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert remaining.stdout.strip() == ""
