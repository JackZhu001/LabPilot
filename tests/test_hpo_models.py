from uuid import uuid4

import optuna
import pytest
from pydantic import ValidationError

from labpilot.hpo.mapper import OptunaParameterMapper, experiment_config
from labpilot.hpo.models import TrialStatus
from labpilot.hpo.search_space import (
    CategoricalParameter,
    FloatParameter,
    IntParameter,
    ParameterValue,
    SampledParameters,
    SearchSpace,
)
from labpilot.hpo.selection import select_best
from labpilot.models.common import MetricDirection, utc_now
from labpilot.models.experiments import ExperimentConfig, Trial


@pytest.mark.parametrize(
    "values",
    [
        {"low": 1, "high": 1},
        {"low": 2, "high": 1},
        {"low": 0, "high": 1, "log": True},
        {"low": -1, "high": 1, "log": True},
        {"low": 1, "high": 10, "log": True, "step": 1},
        {"low": 0, "high": 1, "step": 0},
        {"low": 0, "high": 1, "step": 2},
        {"low": 0, "high": 1, "step": 0.3},
        {"low": 0, "high": float("inf")},
    ],
)
def test_float_validation(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        FloatParameter.model_validate({"name": "x", **values})


@pytest.mark.parametrize(
    "values",
    [
        {"low": 1, "high": 1},
        {"low": 2, "high": 1},
        {"low": 0, "high": 5, "log": True},
        {"low": 1, "high": 5, "log": True, "step": 2},
        {"low": 1, "high": 5, "step": 0},
        {"low": 1, "high": 5, "step": 6},
        {"low": 1, "high": 5, "step": 3},
        {"low": 1.5, "high": 5},
    ],
)
def test_integer_validation(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        IntParameter.model_validate({"name": "x", **values})


@pytest.mark.parametrize("choices", [(), (1, 1), (True, 1), (float("nan"),), ({"nested": 1},)])
def test_categorical_validation(choices: tuple[object, ...]) -> None:
    with pytest.raises(ValidationError):
        CategoricalParameter.model_validate({"name": "x", "choices": choices})


def test_duplicate_names() -> None:
    with pytest.raises(ValidationError):
        SearchSpace(
            parameters=(
                IntParameter(name="x", low=1, high=3),
                FloatParameter(name="x", low=0, high=1),
            )
        )


def test_optuna_mapping_all_types() -> None:
    space = SearchSpace(
        parameters=(
            FloatParameter(name="log_float", low=1e-4, high=1e-2, log=True),
            FloatParameter(name="stepped", low=0, high=1, step=0.1),
            IntParameter(name="integer", low=2, high=8, step=2),
            IntParameter(name="log_int", low=1, high=16, log=True),
            CategoricalParameter(name="category", choices=("a", "b")),
        )
    )
    study = optuna.create_study(sampler=optuna.samplers.TPESampler(seed=42))
    trial = study.ask()
    sampled = OptunaParameterMapper().sample(space, trial)
    assert sampled.as_dict() == trial.params
    assert trial.distributions["log_float"].log
    assert trial.distributions["stepped"].step == 0.1
    assert trial.distributions["integer"].step == 2
    assert trial.distributions["log_int"].log
    assert trial.distributions["category"].choices == ("a", "b")
    assert SearchSpace.model_validate_json(space.model_dump_json()) == space


def record(number: int, value: float | None, status: TrialStatus = TrialStatus.SUCCEEDED) -> Trial:
    now = utc_now()
    return Trial(
        experiment_id=uuid4(),
        study_id=uuid4(),
        research_id=uuid4(),
        hypothesis_id=uuid4(),
        seed=42,
        status=status,
        optuna_trial_number=number,
        primary_metric_name="accuracy",
        primary_metric_value=value,
        failure_reason="Failure" if status == TrialStatus.FAILED else None,
        started_at=now,
        finished_at=now,
        created_at=now,
    )


@pytest.mark.parametrize("direction", list(MetricDirection))
def test_best_trial_selection_and_tie_break(direction: MetricDirection) -> None:
    records = (
        record(4, 0.8),
        record(2, 0.8),
        record(5, None, TrialStatus.FAILED),
        record(0, 0.99, TrialStatus.PRUNED),
        record(6, 0.7),
    )
    best = select_best(records, direction)
    assert best.optuna_trial_number == (2 if direction == MetricDirection.MAXIMIZE else 6)
    assert select_best((records[2], records[3]), direction) is None
    assert Trial.model_validate_json(best.model_dump_json()) == best


@pytest.mark.parametrize(
    "parameters",
    [
        {"dropout": 1.5},
        {"hidden_dim": 3.5},
        {"batch_size": -1},
        {"unknown": 1},
        {"learning_rate": "0.01"},
    ],
)
def test_invalid_parameter_mapping(parameters: dict[str, object]) -> None:
    values = SampledParameters.model_validate(
        {"values": [{"name": k, "value": v} for k, v in parameters.items()]}
    )
    with pytest.raises(ValidationError):
        experiment_config(ExperimentConfig(), values)


def test_valid_mapping() -> None:
    values = SampledParameters(
        values=(
            ParameterValue(name="dropout", value=0.3),
            ParameterValue(name="hidden_dim", value=64),
        )
    )
    config = experiment_config(ExperimentConfig(), values)
    assert config.overrides.dropout == 0.3 and config.overrides.hidden_dim == 64
