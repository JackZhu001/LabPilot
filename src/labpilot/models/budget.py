"""Hard, deterministic limits on autonomous work."""

from typing import Self

from pydantic import model_validator

from labpilot.models.common import DomainModel, NonNegative


class ResearchBudget(DomainModel):
    max_iterations: NonNegative = 3
    max_experiments: NonNegative = 3
    max_failed_experiments: NonNegative = 2
    max_replans: NonNegative = 2
    iterations: NonNegative = 0
    experiments: NonNegative = 0
    failed_experiments: NonNegative = 0
    replans: NonNegative = 0

    @model_validator(mode="after")
    def validate_usage(self) -> Self:
        for key in ("iterations", "experiments", "failed_experiments", "replans"):
            if getattr(self, key) > getattr(self, f"max_{key}"):
                raise ValueError(f"{key} usage exceeds limit")
        if self.failed_experiments > self.experiments:
            raise ValueError("Failed experiments cannot exceed total experiments")
        return self

    def can_run_experiment(self) -> bool:
        return (
            self.experiments < self.max_experiments
            and self.failed_experiments < self.max_failed_experiments
        )

    def can_continue(self) -> bool:
        """Whether a new iteration may start; an active iteration may still finish."""
        return self.iterations < self.max_iterations and self.can_run_experiment()

    def can_replan(self) -> bool:
        return self.replans < self.max_replans and self.can_continue()

    def consume(self, **usage: int) -> Self:
        """Return validated usage increments, rejecting negative or unknown counters."""
        values = self.model_dump()
        for key, amount in usage.items():
            if key not in {"iterations", "experiments", "failed_experiments", "replans"}:
                raise ValueError(f"Unknown budget counter: {key}")
            if amount < 0:
                raise ValueError("Budget usage cannot decrease")
            values[key] += amount
        return type(self).model_validate(values)
