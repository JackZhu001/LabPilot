"""Hard, deterministic limits on autonomous work."""

from typing import Self

from pydantic import model_validator

from labpilot.models.common import DomainModel, NonNegative


class ResearchBudget(DomainModel):
    max_literature_queries: NonNegative = 0
    literature_queries: NonNegative = 0
    max_papers: NonNegative = 0
    papers: NonNegative = 0
    max_claims: NonNegative = 0
    claims: NonNegative = 0
    max_llm_calls: NonNegative = 0
    llm_calls: NonNegative = 0
    max_llm_tokens: NonNegative = 0
    llm_tokens: NonNegative = 0
    max_hpo_trials: NonNegative = 0
    hpo_trials: NonNegative = 0
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
        for key in (
            "iterations",
            "experiments",
            "failed_experiments",
            "replans",
            "hpo_trials",
            "llm_calls",
            "llm_tokens",
            "literature_queries",
            "papers",
            "claims",
        ):
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

    def can_run_hpo_trial(self) -> bool:
        return self.hpo_trials < self.max_hpo_trials and self.can_run_experiment()

    def can_call_llm(self, estimated_tokens: int = 1) -> bool:
        return (
            estimated_tokens >= 0
            and self.llm_calls < self.max_llm_calls
            and self.llm_tokens + estimated_tokens <= self.max_llm_tokens
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
            if key not in {
                "iterations",
                "experiments",
                "failed_experiments",
                "replans",
                "hpo_trials",
                "llm_calls",
                "llm_tokens",
                "literature_queries",
                "papers",
                "claims",
            }:
                raise ValueError(f"Unknown budget counter: {key}")
            if amount < 0:
                raise ValueError("Budget usage cannot decrease")
            values[key] += amount
        return type(self).model_validate(values)
