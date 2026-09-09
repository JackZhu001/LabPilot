from dataclasses import replace
from pathlib import Path

import pytest

from labpilot.graph.workflow import execute, route_next
from labpilot.models.budget import ResearchBudget
from labpilot.models.common import FakeOutcome, ResearchDecision, RunStatus, Step
from labpilot.models.experiments import Baseline, Experiment, ExperimentResult
from labpilot.models.state import ResearchState, SimulationConfig
from labpilot.persistence.repository import SQLiteResearchRepository
from labpilot.services.fakes import fake_services


@pytest.mark.parametrize(
    ("outcomes", "expected", "iterations"),
    [
        ((FakeOutcome.IMPROVE,), "KEEP", 1),
        ((FakeOutcome.REGRESS,), "REJECT", 1),
        ((FakeOutcome.INCONCLUSIVE, FakeOutcome.IMPROVE), "KEEP", 2),
        ((FakeOutcome.FAIL, FakeOutcome.IMPROVE), "KEEP", 2),
        ((FakeOutcome.INCONCLUSIVE,), "REJECT", 3),
        ((FakeOutcome.FAIL,), "REJECT", 2),
    ],
)
def test_graph_routes(
    repository: SQLiteResearchRepository,
    outcomes: tuple[FakeOutcome, ...],
    expected: str,
    iterations: int,
) -> None:
    initial = repository.create(
        ResearchState(research_goal="Goal", simulation=SimulationConfig(outcomes=outcomes))
    )
    result = execute(repository, initial.research_id)
    assert result.decision == expected
    assert result.iteration == iterations
    assert result.status == RunStatus.COMPLETED and result.next_step == Step.END
    assert result.budget.experiments == iterations
    assert len(result.decisions) == iterations
    assert result.budget.replans == iterations - 1
    assert all(item.decision == ResearchDecision.REPLAN for item in result.decisions[:-1])
    assert ResearchState.model_validate_json(result.model_dump_json()) == result
    assert repository.load(initial.research_id) == result
    assert execute(repository, initial.research_id) == result


@pytest.mark.parametrize("limit", ["max_iterations", "max_experiments", "max_failed_experiments"])
def test_budget_stops_before_experiment(repository: SQLiteResearchRepository, limit: str) -> None:
    state = repository.create(
        ResearchState(research_goal="Goal", budget=ResearchBudget.model_validate({limit: 0}))
    )
    result = execute(repository, state.research_id)
    assert result.status == RunStatus.COMPLETED
    assert result.iteration == 0 and not result.experiments
    assert result.decision is None
    assert "budget exhausted" in result.termination_reason.lower()


@pytest.mark.parametrize(
    "budget",
    [
        ResearchBudget(max_iterations=1),
        ResearchBudget(max_experiments=1),
        ResearchBudget(max_replans=0),
    ],
)
def test_budgets_prevent_replan(
    repository: SQLiteResearchRepository, budget: ResearchBudget
) -> None:
    state = repository.create(
        ResearchState(
            research_goal="Goal",
            budget=budget,
            simulation=SimulationConfig(outcomes=(FakeOutcome.INCONCLUSIVE,)),
        )
    )
    result = execute(repository, state.research_id)
    assert result.decision == ResearchDecision.REJECT
    assert result.iteration == 1 and result.budget.replans == 0


@pytest.mark.parametrize("stop_after", range(1, 10))
def test_resume_every_step(tmp_path: Path, stop_after: int) -> None:
    path = tmp_path / "resume.sqlite3"
    initial = ResearchState(
        research_goal="Goal",
        simulation=SimulationConfig(
            outcomes=(FakeOutcome.INCONCLUSIVE, FakeOutcome.IMPROVE),
        ),
    )
    first = SQLiteResearchRepository(path)
    first.create(initial)
    paused = execute(first, initial.research_id, stop_after=stop_after)
    assert paused.status == RunStatus.PAUSED
    assert paused.revision == stop_after
    first.close()

    reopened = SQLiteResearchRepository(path)
    resumed = execute(reopened, initial.research_id)
    reopened.close()
    control = SQLiteResearchRepository(tmp_path / "control.sqlite3")
    control.create(initial)
    uninterrupted = execute(control, initial.research_id)
    control.close()
    assert resumed.model_dump(exclude={"updated_at"}) == uninterrupted.model_dump(
        exclude={"updated_at"}
    )
    assert resumed.decision == ResearchDecision.KEEP
    assert len(resumed.experiments) == 2


def test_repeated_single_step_resume(repository: SQLiteResearchRepository) -> None:
    state = repository.create(ResearchState(research_goal="Goal"))
    for _ in range(6):
        state = execute(repository, state.research_id, stop_after=1)
    assert state.status == RunStatus.COMPLETED
    assert state.revision == 6 and len(state.experiments) == 1


def test_unexpected_runner_exception_preserves_cursor(repository: SQLiteResearchRepository) -> None:
    class BrokenRunner:
        def run(self, experiment: Experiment, baseline: Baseline) -> ExperimentResult:
            raise RuntimeError("Unexpected implementation error")

    initial = repository.create(ResearchState(research_goal="Goal"))
    services = replace(fake_services(initial.simulation), experiment=BrokenRunner())
    with pytest.raises(RuntimeError, match="Unexpected"):
        execute(repository, initial.research_id, services=services)
    checkpoint = repository.load(initial.research_id)
    assert checkpoint.next_step == Step.EXPERIMENT
    assert not checkpoint.experiments and checkpoint.budget.experiments == 0
    result = execute(repository, initial.research_id)
    assert result.decision == ResearchDecision.KEEP
    assert len(result.hypotheses) == 1


def test_committed_experiment_is_not_rerun(repository: SQLiteResearchRepository) -> None:
    class ForbiddenRunner:
        def run(self, experiment: Experiment, baseline: Baseline) -> ExperimentResult:
            raise AssertionError("Committed experiment was executed twice")

    initial = repository.create(ResearchState(research_goal="Goal"))
    execute(repository, initial.research_id, stop_after=4)
    services = replace(fake_services(initial.simulation), experiment=ForbiddenRunner())
    assert (
        execute(repository, initial.research_id, services=services).decision
        == ResearchDecision.KEEP
    )


def test_route_pause_and_cursor() -> None:
    state = ResearchState(research_goal="Goal", next_step=Step.HYPOTHESIS)
    assert route_next({"research": state, "completed_steps": 0}) == "hypothesis"
    assert (
        route_next({"research": state.evolve(status=RunStatus.PAUSED), "completed_steps": 1})
        == "__end__"
    )


def test_long_bounded_cycle(repository: SQLiteResearchRepository) -> None:
    initial = repository.create(
        ResearchState(
            research_goal="Goal",
            budget=ResearchBudget(max_iterations=12, max_experiments=12, max_replans=11),
            simulation=SimulationConfig(outcomes=(FakeOutcome.INCONCLUSIVE,)),
        )
    )
    result = execute(repository, initial.research_id)
    assert result.iteration == 12 and result.decision == ResearchDecision.REJECT


def test_stop_after_validation(repository: SQLiteResearchRepository) -> None:
    initial = repository.create(ResearchState(research_goal="Goal"))
    with pytest.raises(ValueError, match="positive"):
        execute(repository, initial.research_id, stop_after=0)
