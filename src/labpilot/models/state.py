"""Versioned research snapshots with validated provenance links."""

from typing import Literal, Self
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field, model_validator

from labpilot.hpo.models import ExperimentPlan, HPOConfig, OptimizationStudy
from labpilot.llm.models import (
    HypothesisBatch,
    LLMSettings,
    LLMUsage,
    PatchProposal,
    RepositoryInspection,
    ResearchCritique,
)
from labpilot.models.budget import ResearchBudget
from labpilot.models.common import (
    ChangeType,
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
from labpilot.models.literature import (
    Claim,
    Evidence,
    EvidenceSynthesis,
    GroundedHypothesisBatch,
    Hypothesis,
    LiteratureQueryPlan,
    LiteratureSettings,
    Paper,
)


class DecisionRecord(DomainModel):
    experiment_id: UUID | None
    study_id: UUID | None = None
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
    literature_settings: LiteratureSettings = Field(default_factory=LiteratureSettings)
    literature_query_plan: LiteratureQueryPlan | None = None
    literature_failures: tuple[Text, ...] = ()
    claim_extraction_index: NonNegative = 0
    evidence_synthesis: EvidenceSynthesis | None = None
    grounded_hypothesis_batches: tuple[GroundedHypothesisBatch, ...] = ()
    claims: tuple[Claim, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    hypotheses: tuple[Hypothesis, ...] = ()
    active_hypothesis_id: UUID | None = None
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    llm: LLMSettings | None = None
    repository_inspection: RepositoryInspection | None = None
    hypothesis_batches: tuple[HypothesisBatch, ...] = ()
    required_change_type: ChangeType | None = None
    max_hypothesis_generation_attempts: int = Field(default=1, ge=1, le=2)
    hypothesis_generation_attempts: NonNegative = 0
    active_plan_id: UUID | None = None
    patch_proposals: tuple[PatchProposal, ...] = ()
    critic_summaries: tuple[ResearchCritique, ...] = ()
    llm_usage: tuple[LLMUsage, ...] = ()
    hpo: HPOConfig | None = None
    plans: tuple[ExperimentPlan, ...] = ()
    studies: tuple[OptimizationStudy, ...] = ()
    active_study_id: UUID | None = None
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
            self.plans,
            self.studies,
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
        plans = {item.id: item for item in self.plans}
        studies = {item.id: item for item in self.studies}
        experiments = {item.id: item for item in self.experiments}
        trials = {item.id: item for item in self.trials}
        links_valid = (
            all(item.paper_id in papers for item in self.claims)
            and all(
                item.claim_id in claims
                and (
                    item.paper_id is None
                    or (
                        item.paper_id in papers
                        and next(
                            claim for claim in self.claims if claim.id == item.claim_id
                        ).paper_id
                        == item.paper_id
                    )
                )
                and (item.target_hypothesis_id is None or item.target_hypothesis_id in hypotheses)
                for item in self.evidence
            )
            and all(set(item.evidence_ids) <= evidence for item in self.hypotheses)
            and all(item.hypothesis_id in hypotheses for item in self.patches)
            and all(
                item.hypothesis_id in hypotheses
                and (
                    item.patch_id is None
                    or (
                        item.patch_id in patches
                        and patches[item.patch_id].hypothesis_id == item.hypothesis_id
                    )
                )
                for item in self.plans
            )
            and all(
                item.research_id == self.research_id
                and item.hypothesis_id in hypotheses
                and item.plan_id in plans
                and plans[item.plan_id].hypothesis_id == item.hypothesis_id
                and plans[item.plan_id].search_space == item.search_space
                and plans[item.plan_id].primary_metric == item.primary_metric
                and plans[item.plan_id].direction == item.direction
                for item in self.studies
            )
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
                (
                    item.experiment_id is None
                    and item.study_id is not None
                    and item.study_id in studies
                )
                or (
                    item.experiment_id in experiments
                    and experiments[item.experiment_id].hypothesis_id == item.hypothesis_id
                    and (item.study_id is None or item.study_id in studies)
                )
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
        study_ids = set(studies)
        if self.active_study_id is not None and self.active_study_id not in study_ids:
            raise ValueError("Active study is missing")
        if self.active_plan_id is not None and self.active_plan_id not in plans:
            raise ValueError("Active plan is missing")
        if self.repository_inspection is not None:
            if (
                self.repository_inspection.base_commit_sha != self.execution.base_commit_sha
                or self.repository_inspection.repo_path != str(self.execution.baseline_repo_path)
            ):
                raise ValueError("Repository inspection does not match execution configuration")
        if any(item.hypothesis_id not in hypotheses for item in self.patch_proposals):
            raise ValueError("Patch proposal references an unknown hypothesis")
        if any(item.hypothesis_id not in hypotheses for item in self.critic_summaries):
            raise ValueError("Critique references an unknown hypothesis")
        if self.budget.llm_calls != len(self.llm_usage):
            raise ValueError("LLM call budget must equal persisted usage records")
        if self.budget.llm_tokens != sum(item.total_tokens for item in self.llm_usage):
            raise ValueError("LLM token budget must equal persisted usage records")
        if self.literature_settings.enabled:
            if self.budget.papers != len(self.papers) or self.budget.claims != len(self.claims):
                raise ValueError("Literature budget usage must equal accepted provenance records")
            query_count = (
                len(self.literature_query_plan.queries) if self.literature_query_plan else 0
            )
            if self.budget.literature_queries != query_count:
                raise ValueError("Literature query budget must equal the accepted query plan")
        if self.hypothesis_generation_attempts > self.max_hypothesis_generation_attempts:
            raise ValueError("Hypothesis generation attempts exceed the configured limit")
        hpo_trials = [trial for trial in self.trials if trial.study_id is not None]
        if self.budget.hpo_trials != len(hpo_trials):
            raise ValueError("HPO budget usage must equal accepted trial count")
        if any(
            t.study_id not in study_ids
            or t.research_id != self.research_id
            or t.hypothesis_id != studies[t.study_id].hypothesis_id
            for t in hpo_trials
        ):
            raise ValueError("HPO trial references an unknown study or research run")
        identities = [(t.study_id, t.optuna_trial_number) for t in hpo_trials]
        if len(identities) != len(set(identities)):
            raise ValueError("Duplicate Optuna trial identity")
        for study in self.studies:
            members = [trial for trial in hpo_trials if trial.study_id == study.id]
            best = trials.get(study.best_trial_id) if study.best_trial_id is not None else None
            successful = sum(trial.status.value == "SUCCEEDED" for trial in members)
            if study.completed_trials != successful:
                raise ValueError("Study successful-trial count does not match trial records")
            if study.failed_trials != sum(trial.status.value == "FAILED" for trial in members):
                raise ValueError("Study failed-trial count does not match trial records")
            if study.pruned_trials != sum(trial.status.value == "PRUNED" for trial in members):
                raise ValueError("Study pruned-trial count does not match trial records")
            if study.best_trial_id is not None and (
                best is None or best.study_id != study.id or best.status.value != "SUCCEEDED"
            ):
                raise ValueError("Study best trial must be a successful member")
        if self.iteration != self.budget.iterations:
            raise ValueError("Iteration and budget usage must agree")
        if self.budget.experiments != len(self.experiments):
            raise ValueError("Experiment count and budget usage must agree")
        failures = sum(item.status.value == "FAILED" for item in self.experiments)
        if failures != self.budget.failed_experiments:
            raise ValueError("Failure count and budget usage must agree")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot precede created_at")
        terminal = self.status in {RunStatus.COMPLETED, RunStatus.FAILED}
        if terminal != (self.next_step == Step.END):
            raise ValueError("Terminal runs must have the END cursor, and vice versa")
        if terminal and self.termination_reason is None:
            raise ValueError("Terminal runs require a termination reason")
        if self.status == RunStatus.BLOCKED and self.next_step == Step.END:
            raise ValueError("Blocked runs must retain their retry cursor")
        if self.decision != (self.decisions[-1].decision if self.decisions else None):
            raise ValueError("Latest decision must agree with decision history")
        return self

    def evolve(self, **changes: object) -> Self:
        """Create a fully revalidated snapshot (unlike unchecked model_copy updates)."""
        values = self.model_dump()
        values.update(changes)
        return type(self).model_validate(values)
