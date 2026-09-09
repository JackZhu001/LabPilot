"""Stable best-trial selection independent of Optuna and graph execution."""

from labpilot.hpo.models import TrialStatus
from labpilot.models.common import MetricDirection
from labpilot.models.experiments import Trial


def select_best(trials: tuple[Trial, ...], direction: MetricDirection) -> Trial | None:
    eligible = [
        trial
        for trial in trials
        if trial.status == TrialStatus.SUCCEEDED and trial.primary_metric_value is not None
    ]
    if not eligible:
        return None

    def rank(trial: Trial) -> tuple[float, int, str]:
        assert trial.primary_metric_value is not None
        value = trial.primary_metric_value
        return (
            -value if direction == MetricDirection.MAXIMIZE else value,
            trial.optuna_trial_number if trial.optuna_trial_number is not None else 0,
            str(trial.id),
        )

    return min(eligible, key=rank)
