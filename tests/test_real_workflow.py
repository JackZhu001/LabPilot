from dataclasses import replace
from pathlib import Path

import pytest

from labpilot.graph.workflow import execute
from labpilot.models.budget import ResearchBudget
from labpilot.models.common import ExperimentStatus, ResearchDecision, Step
from labpilot.models.experiments import Baseline, Experiment, ExperimentResult
from labpilot.models.state import ResearchState
from labpilot.persistence.repository import SQLiteResearchRepository
from labpilot.services.fakes import fake_services
from labpilot.services.real import configure_docker, prepare_example


class MeasuredRunner:
    def __init__(self, values: tuple[float | None, ...]) -> None:
        self.values = values
        self.calls = 0

    def run(self, experiment: Experiment, baseline: Baseline) -> ExperimentResult:
        value = self.values[self.calls]
        self.calls += 1
        return (
            ExperimentResult(status=ExperimentStatus.FAILED, error="Fixture training failure")
            if value is None
            else ExperimentResult(status=ExperimentStatus.SUCCEEDED, value=value)
        )


def make_state(tmp_path: Path, **changes: object) -> ResearchState:
    source = tmp_path / "source"
    source.mkdir()
    (source / "config.yaml").write_text("dropout: 0.0\n")
    repo = prepare_example(source, tmp_path / "baseline")
    state = ResearchState(
        research_goal="Dropout", execution=configure_docker(repo, tmp_path / "runtime")
    )
    return state.evolve(**changes)


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ((0.8, 0.85), ResearchDecision.KEEP),
        ((0.8, 0.7), ResearchDecision.REJECT),
        ((0.8, 0.8, 0.85), ResearchDecision.KEEP),
        ((0.8, None, 0.85), ResearchDecision.KEEP),
        ((None, 0.8, 0.85), ResearchDecision.KEEP),
        ((None, None), ResearchDecision.REJECT),
    ],
)
def test_real_routes(
    tmp_path: Path,
    repository: SQLiteResearchRepository,
    values: tuple[float | None, ...],
    expected: ResearchDecision,
) -> None:
    state = repository.create(make_state(tmp_path))
    runner = MeasuredRunner(values)
    services = replace(fake_services(state.simulation), experiment=runner)
    result = execute(repository, state.research_id, services=services)
    assert result.decision == expected
    assert result.budget.experiments == runner.calls == len(values)
    assert result.budget.failed_experiments == values.count(None)
    assert ResearchState.model_validate_json(result.model_dump_json()) == result
    if values != (None, None):
        assert result.baseline.value == 0.8
        assert result.baseline_experiment_id is not None
        assert result.patches[-1].experiment_id == result.experiments[-1].id


@pytest.mark.parametrize("pause", [3, 5])
def test_real_resume_skips_committed_runs(
    tmp_path: Path, repository: SQLiteResearchRepository, pause: int
) -> None:
    state = repository.create(make_state(tmp_path))
    runner = MeasuredRunner((0.8, 0.85))
    services = replace(fake_services(state.simulation), experiment=runner)
    paused = execute(repository, state.research_id, services=services, stop_after=pause)
    assert paused.next_step == (Step.HYPOTHESIS if pause == 3 else Step.ANALYZE)
    result = execute(repository, state.research_id, services=services)
    assert result.decision == ResearchDecision.KEEP
    assert runner.calls == 2 and result.budget.experiments == 2
    assert execute(repository, state.research_id, services=services) == result
    assert runner.calls == 2


def test_baseline_counts_against_budget(
    tmp_path: Path, repository: SQLiteResearchRepository
) -> None:
    state = repository.create(make_state(tmp_path, budget=ResearchBudget(max_experiments=1)))
    runner = MeasuredRunner((0.8,))
    result = execute(
        repository,
        state.research_id,
        services=replace(fake_services(state.simulation), experiment=runner),
    )
    assert runner.calls == 1 and not result.patches
    assert result.budget.experiments == 1 and result.iteration == 0


def test_full_execution_provenance_survives_storage(
    tmp_path: Path, repository: SQLiteResearchRepository
) -> None:
    from labpilot.execution.runner import DockerExperimentRunner
    from tests.test_real_runner import FixtureDocker

    state = repository.create(make_state(tmp_path, budget=ResearchBudget(max_replans=0)))
    services = replace(
        fake_services(state.simulation),
        experiment=DockerExperimentRunner(state.execution, FixtureDocker()),
    )
    completed = execute(repository, state.research_id, services=services)
    restored = repository.load(state.research_id)
    assert restored == completed
    assert completed.decision == ResearchDecision.REJECT
    assert len(completed.experiments) == 2
    assert all(exp.result.execution for exp in completed.experiments)
    assert completed.patches[0].diff.endswith("\n")
