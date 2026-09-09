from uuid import uuid4

import pytest
from pydantic import ValidationError

from labpilot.models.budget import ResearchBudget
from labpilot.models.common import EvidenceRelation, ExperimentStatus
from labpilot.models.experiments import Baseline, ExperimentResult
from labpilot.models.literature import Claim, Evidence
from labpilot.models.state import ResearchState


def test_state_roundtrip() -> None:
    state = ResearchState(research_goal="Does dropout help?")
    assert ResearchState.model_validate_json(state.model_dump_json()) == state
    with pytest.raises(ValidationError):
        state.research_goal = "changed"


@pytest.mark.parametrize("goal", ["", "  "])
def test_nonempty_goal(goal: str) -> None:
    with pytest.raises(ValidationError):
        ResearchState(research_goal=goal)


@pytest.mark.parametrize("confidence", [-0.01, 1.01, float("nan"), float("inf")])
def test_confidence_validation(confidence: float) -> None:
    with pytest.raises(ValidationError):
        Claim(paper_id=uuid4(), statement="Claim", confidence=confidence)


@pytest.mark.parametrize("relation", list(EvidenceRelation))
def test_evidence_relationships(relation: EvidenceRelation) -> None:
    evidence = Evidence(claim_id=uuid4(), relation=relation, summary="Fixture", confidence=0.5)
    assert Evidence.model_validate_json(evidence.model_dump_json()).relation == relation


@pytest.mark.parametrize(
    "changes",
    [
        {"unexpected": 1},
        {"schema_version": 2},
        {"active_hypothesis_id": uuid4()},
        {"iteration": 1},
        {"next_step": "end"},
        {"claims": [Claim(paper_id=uuid4(), statement="Orphan", confidence=1)]},
    ],
)
def test_snapshot_integrity(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ResearchState(research_goal="Goal").evolve(**changes)


@pytest.mark.parametrize(
    "values",
    [
        {"value": float("nan")},
        {"value": float("inf")},
        {"min_delta": 0},
        {"regression_delta": -1},
    ],
)
def test_baseline_validation(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Baseline.model_validate(values)


@pytest.mark.parametrize(
    "values",
    [
        {"status": "RUNNING"},
        {"status": "SUCCEEDED"},
        {"status": "FAILED"},
        {"status": "FAILED", "error": "Oops", "value": 1.0},
    ],
)
def test_result_validation(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ExperimentResult.model_validate(values)


def test_failed_result_is_valid() -> None:
    assert ExperimentResult(status=ExperimentStatus.FAILED, error="Oops").value is None


def test_budget_boundaries() -> None:
    budget = ResearchBudget(max_iterations=1, max_experiments=1)
    assert budget.can_continue() and budget.can_replan()
    active = budget.consume(iterations=1)
    assert not active.can_continue()
    assert active.can_run_experiment()  # Last allowed iteration can finish.
    exhausted = active.consume(experiments=1)
    assert not exhausted.can_run_experiment() and not exhausted.can_replan()
    assert budget.iterations == 0


@pytest.mark.parametrize("limit", ["max_iterations", "max_experiments", "max_failed_experiments"])
def test_zero_work_budget(limit: str) -> None:
    assert not ResearchBudget.model_validate({limit: 0}).can_continue()


def test_replan_zero_still_allows_initial_work() -> None:
    budget = ResearchBudget(max_replans=0)
    assert budget.can_continue() and not budget.can_replan()


@pytest.mark.parametrize("usage", [{"iterations": -1}, {"unknown": 1}, {"experiments": 4}])
def test_invalid_budget_consumption(usage: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        ResearchBudget().consume(**usage)


def test_failure_budget() -> None:
    budget = ResearchBudget(max_failed_experiments=1).consume(experiments=1, failed_experiments=1)
    assert not budget.can_continue() and not budget.can_replan()
    with pytest.raises(ValidationError):
        ResearchBudget(failed_experiments=1)
