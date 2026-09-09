"""Versioned research snapshots with validated provenance links."""

from typing import Literal, Self
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field, model_validator

from labpilot.models.budget import ResearchBudget
from labpilot.models.common import (
    DomainModel,
    FakeOutcome,
    NonNegative,
    ResearchDecision,
    RunStatus,
    Step,
    Text,
    utc_now,
)
from labpilot.models.execution import ExecutionConfig
from labpilot.models.experiments import Baseline, CodePatch, Experiment, Metric, Trial
from labpilot.models.literature import Claim, Evidence, Hypothesis, Paper


class DecisionRecord(DomainModel):
    experiment_id: UUID
    hypothesis_id: UUID | None
    decision: ResearchDecision
    reason: Text
    improvement: float | None = Field(default=None, allow_inf_nan=False)


class SimulationConfig(DomainModel):
    """Persisted fake scenario. The final outcome repeats if iterations outnumber it."""

    outcomes: tuple[FakeOutcome, ...] = (FakeOutcome.IMPROVE,)
    seed: NonNegative = 42

    @model_validator(mode="after")
    def nonempty(self) -> Self:
        if not self.outcomes:
            raise ValueError("At least one fake outcome is required")
        return self


class ResearchState(DomainModel):
    """Single durable source of truth, including the next executable step.

    Future integration metadata should use new typed, versioned fields; no open-ended
    dictionary is needed until those contracts exist.
    """

    schema_version: Literal[1] = 1
    research_id: UUID = Field(default_factory=uuid4)
    research_goal: Text
    status: RunStatus = RunStatus.READY
    next_step: Step = Step.LITERATURE
    revision: NonNegative = 0
    papers: tuple[Paper, ...] = ()
    claims: tuple[Claim, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    hypotheses: tuple[Hypothesis, ...] = ()
    active_hypothesis_id: UUID | None = None
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    baseline_experiment_id: UUID | None = None
    baseline: Baseline = Field(default_factory=Baseline)
    patches: tuple[CodePatch, ...] = ()
    experiments: tuple[Experiment, ...] = ()
    trials: tuple[Trial, ...] = ()
    metrics: tuple[Metric, ...] = ()
    budget: ResearchBudget = Field(default_factory=ResearchBudget)
    decision: ResearchDecision | None = None
    decisions: tuple[DecisionRecord, ...] = ()
    iteration: NonNegative = 0
    simulation: SimulationConfig = Field(default_factory=SimulationConfig)
    termination_reason: Text | None = None
    created_at: AwareDatetime = Field(default_factory=utc_now)
    updated_at: AwareDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_integrity(self) -> Self:
        collections = (
            self.papers,
            self.claims,
            self.evidence,
            self.hypotheses,
            self.patches,
            self.experiments,
            self.trials,
            self.metrics,
        )
        all_ids = [item.id for collection in collections for item in collection]
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("Domain object IDs must be unique within a run")
        papers = {item.id for item in self.papers}
        claims = {item.id for item in self.claims}
        evidence = {item.id for item in self.evidence}
        hypotheses = {item.id for item in self.hypotheses}
        patches = {item.id: item for item in self.patches}
        experiments = {item.id: item for item in self.experiments}
        trials = {item.id: item for item in self.trials}
        links_valid = (
            all(item.paper_id in papers for item in self.claims)
            and all(item.claim_id in claims for item in self.evidence)
            and all(set(item.evidence_ids) <= evidence for item in self.hypotheses)
            and all(item.hypothesis_id in hypotheses for item in self.patches)
            and all(
                item.hypothesis_id is None or item.hypothesis_id in hypotheses
                for item in self.experiments
            )
            and all(item.experiment_id in experiments for item in self.trials)
            and all(
                item.experiment_id in experiments
                and item.trial_id in trials
                and trials[item.trial_id].experiment_id == item.experiment_id
                for item in self.metrics
            )
            and all(
                item.patch_id is None
                or (
                    item.patch_id in patches
                    and patches[item.patch_id].hypothesis_id == item.hypothesis_id
                )
                for item in self.experiments
            )
            and all(
                item.experiment_id in experiments
                and experiments[item.experiment_id].hypothesis_id == item.hypothesis_id
                for item in self.decisions
            )
        )
        if not links_valid:
            raise ValueError("Broken provenance reference")
        if self.baseline_experiment_id is not None:
            baseline = experiments.get(self.baseline_experiment_id)
            if (
                baseline is None
                or baseline.purpose.value != "BASELINE"
                or baseline.status.value != "SUCCEEDED"
            ):
                raise ValueError(
                    "Baseline reference must identify a successful baseline experiment"
                )
        for item in self.experiments:
            if item.result and item.result.execution:
                provenance = item.result.execution
                if (
                    provenance.research_id != self.research_id
                    or provenance.experiment_id != item.id
                    or provenance.hypothesis_id != item.hypothesis_id
                ):
                    raise ValueError("Execution provenance identity does not match the experiment")
        if self.active_hypothesis_id is not None and self.active_hypothesis_id not in hypotheses:
            raise ValueError("Active hypothesis must exist in state")
        if self.iteration != self.budget.iterations:
            raise ValueError("Iteration and budget usage must agree")
        if self.budget.experiments != len(self.experiments):
            raise ValueError("Experiment count and budget usage must agree")
        failures = sum(item.status.value == "FAILED" for item in self.experiments)
        if failures != self.budget.failed_experiments:
            raise ValueError("Failure count and budget usage must agree")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        if (self.status == RunStatus.COMPLETED) != (self.next_step == Step.END):
            raise ValueError("Completed runs must have the END cursor, and vice versa")
        if self.status == RunStatus.COMPLETED and self.termination_reason is None:
            raise ValueError("Completed runs require a termination reason")
        if self.decision != (self.decisions[-1].decision if self.decisions else None):
            raise ValueError("Latest decision must agree with decision history")
        return self

    def evolve(self, **changes: object) -> Self:
        """Create a fully revalidated snapshot (unlike unchecked model_copy updates)."""
        values = self.model_dump()
        values.update(changes)
        return type(self).model_validate(values)
