import pytest

from labpilot.decisions.engine import DecisionEngine
from labpilot.models.budget import ResearchBudget
from labpilot.models.common import ExperimentStatus, MetricDirection, ResearchDecision
from labpilot.models.experiments import Baseline, ExperimentResult


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.9, ResearchDecision.KEEP),
        (0.81, ResearchDecision.KEEP),
        (0.7, ResearchDecision.REJECT),
        (0.79, ResearchDecision.REJECT),
        (0.8, ResearchDecision.REPLAN),
        (0.805, ResearchDecision.REPLAN),
        (0.795, ResearchDecision.REPLAN),
        (0.809999, ResearchDecision.REPLAN),
    ],
)
def test_numerical_decision(value: float, expected: ResearchDecision) -> None:
    assessment = DecisionEngine().decide(
        ExperimentResult(status=ExperimentStatus.SUCCEEDED, value=value),
        Baseline(),
        ResearchBudget(),
    )
    assert assessment.decision == expected
    assert assessment.improvement == pytest.approx(value - 0.8)


@pytest.mark.parametrize(("value", "expected"), [(0.79, "KEEP"), (0.81, "REJECT"), (0.8, "REPLAN")])
def test_minimize(value: float, expected: str) -> None:
    assessment = DecisionEngine().decide(
        ExperimentResult(status=ExperimentStatus.SUCCEEDED, value=value),
        Baseline(direction=MetricDirection.MINIMIZE),
        ResearchBudget(),
    )
    assert assessment.decision == expected


@pytest.mark.parametrize("failed", [True, False])
@pytest.mark.parametrize(
    ("budget", "expected"),
    [
        (ResearchBudget(), "REPLAN"),
        (ResearchBudget(max_replans=0), "REJECT"),
        (ResearchBudget(max_iterations=0), "REJECT"),
        (ResearchBudget(max_experiments=0), "REJECT"),
        (ResearchBudget(max_failed_experiments=0), "REJECT"),
    ],
)
def test_retry_policy(failed: bool, budget: ResearchBudget, expected: str) -> None:
    result = (
        ExperimentResult(status=ExperimentStatus.FAILED, error="Fixture")
        if failed
        else ExperimentResult(status=ExperimentStatus.SUCCEEDED, value=0.8)
    )
    assert DecisionEngine().decide(result, Baseline(), budget).decision == expected


def test_improvement_kept_on_last_experiment() -> None:
    budget = ResearchBudget(max_iterations=1, iterations=1, max_experiments=1, experiments=1)
    result = ExperimentResult(status=ExperimentStatus.SUCCEEDED, value=0.82)
    assert DecisionEngine().decide(result, Baseline(), budget).decision == ResearchDecision.KEEP
