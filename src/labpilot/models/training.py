"""Supported config-only interventions for the MNIST runner contract."""

from typing import Annotated

from pydantic import Field

from labpilot.models.common import DomainModel


class TrainingOverrides(DomainModel):
    learning_rate: Annotated[float, Field(gt=0, lt=1, allow_inf_nan=False, strict=True)] | None = (
        None
    )
    dropout: Annotated[float, Field(ge=0, lt=1, allow_inf_nan=False, strict=True)] | None = None
    hidden_dim: Annotated[int, Field(gt=0, strict=True)] | None = None
    batch_size: Annotated[int, Field(gt=0, strict=True)] | None = None
    epochs: Annotated[int, Field(gt=0, strict=True)] | None = None
