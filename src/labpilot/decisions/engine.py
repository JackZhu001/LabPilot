"""Pure numerical policy, independent of orchestration and persistence."""

from math import isclose

from labpilot.models.budget import ResearchBudget
from labpilot.models.common import DomainModel, ExperimentStatus, MetricDirection, ResearchDecision
from labpilot.models.experiments import Baseline, ExperimentResult


class DecisionAssessment(DomainModel):
    decision: ResearchDecision
    reason: str
    improvement: float | None = None


class DecisionEngine:
    """Absolute delta thresholds; positive improvement always means better.

    A tight floating-point tolerance makes decimal threshold boundaries stable.
    Replanning is allowed only when another iteration and experiment can run.
    """

    def decide(
        self, result: ExperimentResult, baseline: Baseline, budget: ResearchBudget
    ) -> DecisionAssessment:
        if result.status == ExperimentStatus.FAILED:
            return self._retry_or_reject("Experiment failed", budget)
        assert result.value is not None  # Guaranteed by ExperimentResult validation.
        delta = result.value - baseline.value
        if baseline.direction == MetricDirection.MINIMIZE:
            delta = -delta
        if delta >= baseline.min_delta or isclose(
            delta, baseline.min_delta, rel_tol=1e-12, abs_tol=0.0
        ):
            return DecisionAssessment(
                decision=ResearchDecision.KEEP,
                reason="Metric meets the minimum improvement threshold",
                improvement=delta,
            )
        if delta <= -baseline.regression_delta or isclose(
            delta, -baseline.regression_delta, rel_tol=1e-12, abs_tol=0.0
        ):
            return DecisionAssessment(
                decision=ResearchDecision.REJECT,
                reason="Metric meets the regression threshold",
                improvement=delta,
            )
        return self._retry_or_reject("Metric is inconclusive", budget, delta)

    @staticmethod
    def _retry_or_reject(
        reason: str, budget: ResearchBudget, delta: float | None = None
    ) -> DecisionAssessment:
        retry = budget.can_replan()
        return DecisionAssessment(
            decision=ResearchDecision.REPLAN if retry else ResearchDecision.REJECT,
            reason=f"{reason}; {'replan available' if retry else 'no replan budget remains'}",
            improvement=delta,
        )
