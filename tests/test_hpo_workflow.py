from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest

from labpilot.graph.workflow import execute
from labpilot.hpo.models import HPOConfig, OptimizationStudy, StudyStatus
from labpilot.hpo.optuna import PersistentStudy, StudyConflictError
from labpilot.hpo.search_space import CategoricalParameter, SearchSpace
from labpilot.models.budget import ResearchBudget
from labpilot.models.common import ExperimentStatus, MetricDirection, ResearchDecision, Step
from labpilot.models.execution import ExecutionConfig
from labpilot.models.experiments import Baseline, Experiment, ExperimentResult
from labpilot.models.state import ResearchState
from labpilot.persistence.repository import SQLiteResearchRepository
from labpilot.services.fakes import fake_services


class ObjectiveRunner:
    def __init__(self, failed_numbers: tuple[int, ...] = ()) -> None:
        self.calls: list[UUID] = []
        self.failed_numbers = failed_numbers

    def run(self, experiment: Experiment, baseline: Baseline) -> ExperimentResult:
        self.calls.append(experiment.id)
        if experiment.sequence in self.failed_numbers:
            return ExperimentResult(
                status=ExperimentStatus.FAILED, error="Fixture execution failure"
            )
        assert experiment.config.overrides is not None
        return ExperimentResult(
            status=ExperimentStatus.SUCCEEDED, value=0.9 - experiment.config.overrides.dropout / 10
        )


def initial(tmp_path: Path, count: int = 5, **changes: object) -> ResearchState:
    return ResearchState(
        research_goal="Optimize fixture",
        hpo=HPOConfig(max_trials=count),
        execution=ExecutionConfig(runtime_root=tmp_path / "runtime"),
        budget=ResearchBudget(
            max_experiments=count, max_hpo_trials=count, max_failed_experiments=count, max_replans=0
        ),
    ).evolve(**changes)


@pytest.mark.parametrize("direction", list(MetricDirection))
def test_persistent_study_search(
    tmp_path: Path, repository: SQLiteResearchRepository, direction: MetricDirection
) -> None:
    state = repository.create(initial(tmp_path, baseline=Baseline(direction=direction)))
    runner = ObjectiveRunner()
    final = execute(
        repository,
        state.research_id,
        services=replace(fake_services(state.simulation), experiment=runner),
    )
    study = final.studies[0]
    assert study.completed_trials == len(runner.calls) == 5
    assert final.budget.hpo_trials == final.budget.experiments == 5
    assert len({tuple(t.parameters.as_dict().items()) for t in final.trials}) == 5
    best = next(t for t in final.trials if t.id == study.best_trial_id)
    objective = max if direction == MetricDirection.MAXIMIZE else min
    assert best.primary_metric_value == objective(t.primary_metric_value for t in final.trials)
    assert final.decisions[-1].experiment_id == best.experiment_id
    assert final.decision == (
        ResearchDecision.KEEP if direction == MetricDirection.MAXIMIZE else ResearchDecision.REJECT
    )
    with PersistentStudy(study) as stored:
        assert len(stored.study.trials) == 5
        assert stored.study.best_value == best.primary_metric_value
    assert ResearchState.model_validate_json(final.model_dump_json()) == final
    assert OptimizationStudy.model_validate_json(study.model_dump_json()) == study


@pytest.mark.parametrize("pause", [4, 5, 6, 7, 10, 12, 15])
def test_resume_at_trial_boundaries(tmp_path: Path, pause: int) -> None:
    state = initial(tmp_path)
    store = SQLiteResearchRepository(tmp_path / "state.sqlite3")
    store.create(state)
    first = ObjectiveRunner()
    checkpoint = execute(
        store,
        state.research_id,
        stop_after=pause,
        services=replace(fake_services(state.simulation), experiment=first),
    )
    completed_ids = {e.id for e in checkpoint.experiments if e.result is not None}
    store.close()
    reopened = SQLiteResearchRepository(tmp_path / "state.sqlite3")
    second = ObjectiveRunner()
    result = execute(
        reopened,
        state.research_id,
        services=replace(fake_services(state.simulation), experiment=second),
    )
    assert not completed_ids.intersection(second.calls)
    assert len(first.calls) + len(second.calls) == 5
    assert result.studies[0].id == checkpoint.studies[0].id
    assert len(result.trials) == result.budget.hpo_trials == 5
    assert execute(reopened, state.research_id) == result
    reopened.close()


def test_resume_sampler_matches_uninterrupted(tmp_path: Path) -> None:
    sequences = []
    for mode in ("continuous", "resume"):
        directory = tmp_path / mode
        state = initial(directory, count=6)
        store = SQLiteResearchRepository(directory / "state.sqlite3")
        store.create(state)
        runner = ObjectiveRunner()
        services = replace(fake_services(state.simulation), experiment=runner)
        if mode == "resume":
            execute(store, state.research_id, stop_after=13, services=services)
        result = execute(store, state.research_id, services=services)
        sequences.append([t.parameters for t in result.trials])
        store.close()
    assert sequences[0] == sequences[1]


@pytest.mark.parametrize("failures", [(1,), (1, 2, 3, 4, 5)])
def test_failed_trials_do_not_abort(
    tmp_path: Path, repository: SQLiteResearchRepository, failures: tuple[int, ...]
) -> None:
    state = repository.create(initial(tmp_path))
    runner = ObjectiveRunner(failures)
    final = execute(
        repository,
        state.research_id,
        services=replace(fake_services(state.simulation), experiment=runner),
    )
    study = final.studies[0]
    assert len(runner.calls) == 5
    assert study.failed_trials == final.budget.failed_experiments == len(failures)
    assert study.completed_trials == 5 - len(failures)
    if len(failures) == 5:
        assert study.status == StudyStatus.FAILED and study.best_trial_id is None
        assert final.decision == ResearchDecision.REJECT
    else:
        assert study.status == StudyStatus.SUCCEEDED
    with PersistentStudy(study) as stored:
        assert sum(t.state.name == "FAIL" for t in stored.study.trials) == len(failures)


@pytest.mark.parametrize("limit", [0, 2])
def test_trial_budget_exhaustion(
    tmp_path: Path, repository: SQLiteResearchRepository, limit: int
) -> None:
    state = repository.create(
        initial(tmp_path, budget=ResearchBudget(max_experiments=5, max_hpo_trials=limit))
    )
    runner = ObjectiveRunner()
    result = execute(
        repository,
        state.research_id,
        services=replace(fake_services(state.simulation), experiment=runner),
    )
    assert result.budget.hpo_trials == len(runner.calls) == limit
    if limit == 0:
        assert result.studies[0].status == StudyStatus.FAILED
        assert result.decision == ResearchDecision.REJECT


def test_invalid_configuration_is_failed_trial(
    tmp_path: Path, repository: SQLiteResearchRepository
) -> None:
    config = HPOConfig(
        max_trials=2,
        search_space=SearchSpace(
            parameters=(CategoricalParameter(name="dropout", choices=(2.0,)),)
        ),
    )
    state = repository.create(initial(tmp_path, count=2, hpo=config))
    runner = ObjectiveRunner()
    result = execute(
        repository,
        state.research_id,
        services=replace(fake_services(state.simulation), experiment=runner),
    )
    assert not runner.calls
    assert result.studies[0].failed_trials == result.budget.hpo_trials == 2
    assert all("Invalid trial configuration" in t.failure_reason for t in result.trials)


def test_orphan_ask_is_adopted(tmp_path: Path, repository: SQLiteResearchRepository) -> None:
    state = repository.create(initial(tmp_path, count=2))
    planned = execute(repository, state.research_id, stop_after=4)
    with PersistentStudy(planned.studies[0]) as adapter:
        number, parameters = adapter.suggest(0)
    runner = ObjectiveRunner()
    result = execute(
        repository,
        state.research_id,
        services=replace(fake_services(state.simulation), experiment=runner),
    )
    assert result.trials[0].parameters == parameters
    assert result.trials[0].optuna_trial_number == number
    assert len(runner.calls) == 2


def test_tell_is_idempotent_after_interruption(
    tmp_path: Path, repository: SQLiteResearchRepository
) -> None:
    state = repository.create(initial(tmp_path, count=2))
    runner = ObjectiveRunner()
    services = replace(fake_services(state.simulation), experiment=runner)
    checkpoint = execute(repository, state.research_id, stop_after=6, services=services)
    assert checkpoint.next_step == Step.HPO_SYNC
    with PersistentStudy(checkpoint.studies[0]) as adapter:
        adapter.synchronize(checkpoint.trials[0])
        adapter.synchronize(checkpoint.trials[0])
        changed = checkpoint.trials[0].model_copy(update={"primary_metric_value": 0.1})
        with pytest.raises(StudyConflictError):
            adapter.synchronize(changed)
    result = execute(repository, state.research_id, services=services)
    assert len(runner.calls) == 2 and result.studies[0].completed_trials == 2
