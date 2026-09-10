"""Optuna suggestions and validated training configuration mapping."""

from optuna.trial import Trial

from labpilot.hpo.search_space import (
    CategoricalParameter,
    FloatParameter,
    ParameterValue,
    SampledParameters,
    Scalar,
    SearchSpace,
)
from labpilot.models.experiments import ExperimentConfig
from labpilot.models.training import TrainingOverrides


class OptunaParameterMapper:
    def sample(self, space: SearchSpace, trial: Trial) -> SampledParameters:
        values: list[ParameterValue] = []
        for parameter in space.parameters:
            value: Scalar
            if isinstance(parameter, FloatParameter):
                value = trial.suggest_float(
                    parameter.name,
                    parameter.low,
                    parameter.high,
                    log=parameter.log,
                    step=parameter.step,
                )
            elif isinstance(parameter, CategoricalParameter):
                value = trial.suggest_categorical(parameter.name, parameter.choices)
            else:
                value = trial.suggest_int(
                    parameter.name,
                    parameter.low,
                    parameter.high,
                    log=parameter.log,
                    step=parameter.step,
                )
            values.append(ParameterValue(name=parameter.name, value=value))
        return SampledParameters(values=tuple(values))


def experiment_config(base: ExperimentConfig, parameters: SampledParameters) -> ExperimentConfig:
    values = base.overrides.model_dump(exclude_none=True) if base.overrides else {}
    values.update(parameters.as_dict())
    overrides = TrainingOverrides.model_validate(values)
    return ExperimentConfig.model_validate({**base.model_dump(), "overrides": overrides})
