"""Discriminated search-space definitions and typed sampled values."""

from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, StrictFloat, StrictInt, StrictStr, model_validator

from labpilot.models.common import DomainModel, Text

Scalar = (
    StrictBool | StrictInt | Annotated[StrictFloat, Field(allow_inf_nan=False)] | StrictStr | None
)
Finite = Annotated[float, Field(allow_inf_nan=False)]


class FloatParameter(DomainModel):
    name: Text
    type: Literal["float"] = "float"
    low: Finite
    high: Finite
    step: Annotated[float, Field(gt=0, allow_inf_nan=False)] | None = None
    log: bool = False

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.low >= self.high:
            raise ValueError("low must be strictly below high")
        if self.log and (self.low <= 0 or self.step is not None):
            raise ValueError("Log floats require positive bounds and no step")
        if self.step is not None:
            span = Decimal(str(self.high)) - Decimal(str(self.low))
            if Decimal(str(self.step)) > span or span % Decimal(str(self.step)) != 0:
                raise ValueError("Step must divide the range exactly")
        return self


class IntParameter(DomainModel):
    name: Text
    type: Literal["int"] = "int"
    low: StrictInt
    high: StrictInt
    step: Annotated[int, Field(gt=0, strict=True)] = 1
    log: bool = False

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.low >= self.high:
            raise ValueError("low must be strictly below high")
        if self.log and (self.low <= 0 or self.step != 1):
            raise ValueError("Log integers require positive bounds and step=1")
        if self.step > self.high - self.low or (self.high - self.low) % self.step:
            raise ValueError("Step must divide the range exactly")
        return self


class CategoricalParameter(DomainModel):
    name: Text
    type: Literal["categorical"] = "categorical"
    choices: tuple[Scalar, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_choices(self) -> Self:
        # Equality duplicates (including 1/1.0/True) are ambiguous to Optuna.
        if len(set(self.choices)) != len(self.choices):
            raise ValueError("Categorical choices must be unique")
        return self


Parameter = Annotated[
    FloatParameter | IntParameter | CategoricalParameter, Field(discriminator="type")
]


class SearchSpace(DomainModel):
    parameters: tuple[Parameter, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_names(self) -> Self:
        if len({p.name for p in self.parameters}) != len(self.parameters):
            raise ValueError("Duplicate parameter names")
        return self


class ParameterValue(DomainModel):
    name: Text
    value: Scalar


class SampledParameters(DomainModel):
    values: tuple[ParameterValue, ...] = ()

    @model_validator(mode="after")
    def unique_names(self) -> Self:
        if len({p.name for p in self.values}) != len(self.values):
            raise ValueError("Duplicate sampled parameter names")
        return self

    def as_dict(self) -> dict[str, bool | int | float | str | None]:
        """Convert only at JSON/Optuna/config validation boundaries."""
        return {p.name: p.value for p in self.values}


def mnist_search_space() -> SearchSpace:
    return SearchSpace(
        parameters=(
            FloatParameter(name="learning_rate", low=1e-4, high=5e-3, log=True),
            FloatParameter(name="dropout", low=0.0, high=0.5),
            CategoricalParameter(name="hidden_dim", choices=(64, 128, 256)),
            CategoricalParameter(name="batch_size", choices=(32, 64, 128)),
        )
    )
