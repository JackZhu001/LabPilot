"""Checkpoint-sized outer-loop transitions composed from typed LLM roles and tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar, cast
from uuid import UUID, uuid5

from pydantic import BaseModel

from labpilot.agent.patches import PatchPolicyError, PatchValidator
from labpilot.agent.repository import RepositoryInspector
from labpilot.execution.git import WorktreeManager
from labpilot.hpo.models import ExperimentPlan, HPOConfig, TrialStatus
from labpilot.llm.client import LLMClient, StructuredLLMResult
from labpilot.llm.errors import LLMBudgetError
from labpilot.llm.models import (
    ExperimentPlanProposal,
    HypothesisBatch,
    HypothesisProposal,
    PatchProposal,
    RepositoryInspection,
    RepositoryInspectionSummary,
    ResearchCritique,
)
from labpilot.models.common import (
    ChangeType,
    EvidenceRelation,
    EvidenceSource,
    ExperimentStatus,
    GroundingStatus,
    RunStatus,
    Step,
    utc_now,
)
from labpilot.models.experiments import CodePatch, Experiment, ExperimentResult, Trial
from labpilot.models.literature import (
    GroundedHypothesisBatch,
    GroundedHypothesisProposal,
    Hypothesis,
)
from labpilot.models.state import ResearchState
from labpilot.models.training import TrainingOverrides
from labpilot.prompts import load_prompt

T = TypeVar("T", bound=BaseModel)


def compact_json(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(
        value,
        default=lambda item: item.model_dump(mode="json"),
        separators=(",", ":"),
        sort_keys=True,
    )


class AgentLoopService:
    def __init__(self, client: LLMClient) -> None:
        self.client = client

    @staticmethod
    def _fail(state: ResearchState, reason: str) -> ResearchState:
        return state.evolve(status=RunStatus.FAILED, next_step=Step.END, termination_reason=reason)

    def _invoke(
        self,
        state: ResearchState,
        *,
        operation: str,
        template: str,
        user_prompt: str,
        response_model: type[T],
    ) -> tuple[StructuredLLMResult[T], ResearchState]:
        if state.llm is None:
            raise ValueError("Agent loop requires persisted LLM settings")
        remaining_calls = state.budget.max_llm_calls - state.budget.llm_calls
        remaining_tokens = state.budget.max_llm_tokens - state.budget.llm_tokens
        system_prompt = load_prompt(template)
        if remaining_calls < 1 or remaining_tokens < 128:
            raise LLMBudgetError("LLM call or token budget exhausted")
        result = self.client.generate_structured(
            research_id=state.research_id,
            operation=operation,
            prompt_template=f"{template}:v1",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
            max_output_tokens=state.llm.max_output_tokens,
            max_attempts=remaining_calls,
            max_total_tokens=remaining_tokens,
        )
        calls, tokens = len(result.usage), sum(item.total_tokens for item in result.usage)
        if calls > remaining_calls or tokens > remaining_tokens:
            raise LLMBudgetError("Provider usage exceeded the remaining LLM budget")
        return result, state.evolve(
            llm_usage=(*state.llm_usage, *result.usage),
            budget=state.budget.consume(llm_calls=calls, llm_tokens=tokens),
        )

    def inspect_repository(self, state: ResearchState) -> ResearchState:
        config = state.execution
        if config.baseline_repo_path is None or config.base_commit_sha is None:
            raise ValueError("Repository inspection requires Docker repository configuration")
        context = RepositoryInspector().inspect(config.baseline_repo_path, config.base_commit_sha)
        prompt = (
            f"Research goal: {state.research_goal}\n"
            f"Base commit: {context.base_commit_sha}\n"
            f"Tracked file tree: {compact_json(context.file_tree)}\n"
            f"Selected repository content:{context.content}"
        )
        result, state = self._invoke(
            state,
            operation="repository_inspection",
            template="repository_inspection",
            user_prompt=prompt,
            response_model=RepositoryInspectionSummary,
        )
        summary = result.output
        if summary.training_entrypoint not in context.file_tree:
            return self._fail(state, "LLM selected an unknown training entrypoint")
        inspection = RepositoryInspection(
            id=uuid5(state.research_id, "repository-inspection"),
            repo_path=str(context.repo_path),
            base_commit_sha=context.base_commit_sha,
            important_files=context.important_files,
            file_tree=context.file_tree,
            context_characters=len(context.content),
            **summary.model_dump(),
        )
        return state.evolve(
            repository_inspection=inspection,
            next_step=(
                Step.PLAN_LITERATURE_QUERIES if state.literature_settings.enabled else Step.BASELINE
            ),
        )

    @staticmethod
    def _history(state: ResearchState) -> list[dict[str, object]]:
        decisions = {item.hypothesis_id: item for item in state.decisions}
        plans = {item.hypothesis_id: item for item in state.plans}
        patches = {item.id: item for item in state.patches}
        history: list[dict[str, object]] = []
        for item in state.hypotheses:
            plan = plans.get(item.id)
            experiments = [exp for exp in state.experiments if exp.hypothesis_id == item.id]
            experiment_ids = {exp.id for exp in experiments}
            trials = [trial for trial in state.trials if trial.experiment_id in experiment_ids]
            patch = patches.get(plan.patch_id) if plan and plan.patch_id else None
            decision = decisions.get(item.id)
            history.append(
                {
                    "statement": item.statement,
                    "change_type": item.change_type.value,
                    "plan": plan.model_dump(mode="json") if plan else None,
                    "patch_summary": patch.description if patch else None,
                    "trial_parameters": [
                        trial.parameters.model_dump(mode="json") for trial in trials
                    ],
                    "metrics": [exp.result.value for exp in experiments if exp.result],
                    "baseline_metric": state.baseline.value,
                    "failure_reasons": [
                        exp.error or (exp.result.error if exp.result else None)
                        for exp in experiments
                        if exp.error or (exp.result and exp.result.error)
                    ],
                    "decision": decision.decision.value if decision else None,
                    "decision_reason": decision.reason if decision else None,
                }
            )
        return history

    @staticmethod
    def _select(
        proposals: tuple[HypothesisProposal, ...],
        tested: tuple[Hypothesis, ...],
        required_change_type: ChangeType | None = None,
    ) -> HypothesisProposal:
        prior = {" ".join(item.statement.lower().split()) for item in tested}
        candidates = [
            item
            for item in proposals
            if " ".join(item.statement.lower().split()) not in prior
            and (required_change_type is None or item.change_type == required_change_type)
        ]
        if not candidates:
            if required_change_type is not None:
                raise ValueError(
                    f"No new hypothesis satisfied required change type {required_change_type}"
                )
            raise ValueError("All generated hypotheses duplicate experiment history")
        return min(
            candidates,
            key=lambda item: (
                -(item.confidence * item.expected_impact) / (1 + item.estimated_cost),
                item.estimated_cost,
                item.statement,
            ),
        )

    def generate_hypotheses(self, state: ResearchState) -> ResearchState:
        if state.repository_inspection is None:
            raise ValueError("Hypothesis generation requires repository inspection")
        if not state.budget.can_continue():
            raise LLMBudgetError("Research budget exhausted before hypothesis generation")
        constraint = ""
        if state.required_change_type is not None:
            supported_parameters = tuple(TrainingOverrides.model_fields)
            constraint = (
                f"Validation constraint: every proposal must use change_type "
                f"{state.required_change_type.value}. It must require a real source-code change; "
                "for CODE_CHANGE_WITH_HPO, explicitly pair that source change with HPO over one "
                f"or more of these supported parameters: {compact_json(supported_parameters)}. "
                "Do not propose tuning a new parameter outside that list. "
                "Do not offer CONFIG_ONLY alternatives.\n"
            )
        prior_attempts = (
            state.hypothesis_batches[-state.hypothesis_generation_attempts :]
            if state.hypothesis_generation_attempts
            else ()
        )
        grounded = bool(state.evidence)
        prompt = (
            f"Research goal: {state.research_goal}\n"
            f"{constraint}"
            f"Repository inspection: {compact_json(state.repository_inspection)}\n"
            f"Prior experiment history: {compact_json(self._history(state))}\n"
            f"Rejected hypothesis batches from this generation step: "
            f"{compact_json(prior_attempts)}\n"
            f"Remaining experiments: "
            f"{state.budget.max_experiments - state.budget.experiments}; "
            f"remaining HPO trials: {state.budget.max_hpo_trials - state.budget.hpo_trials}.\n"
            f"Evidence synthesis: {compact_json(state.evidence_synthesis)}\n"
            f"Evidence records: {compact_json(state.evidence)}"
        )
        result, state = self._invoke(
            state,
            operation="grounded_hypothesis_generation" if grounded else "hypothesis_generation",
            template="grounded_hypothesis_generation" if grounded else "hypothesis_generation",
            user_prompt=prompt,
            response_model=GroundedHypothesisBatch if grounded else HypothesisBatch,
        )
        attempts = state.hypothesis_generation_attempts + 1
        batches = state.hypothesis_batches
        grounded_batches = state.grounded_hypothesis_batches
        if grounded:
            grounded_batch = GroundedHypothesisBatch.model_validate(result.output)
            grounded_batches = (*grounded_batches, grounded_batch)
            grounded_proposals = grounded_batch.proposals
        else:
            batch = HypothesisBatch.model_validate(result.output)
            batches = (*batches, batch)
            plain_proposals = batch.proposals
        proposal: HypothesisProposal | GroundedHypothesisProposal
        try:
            if grounded:
                valid_ids = {item.id for item in state.evidence}
                claim_to_evidence = {item.claim_id: item.id for item in state.evidence}
                grounded_proposals = tuple(
                    self._canonicalize_grounded(item, valid_ids, claim_to_evidence)
                    for item in grounded_proposals
                )
                grounded_proposals = tuple(
                    item
                    for item in grounded_proposals
                    if set(item.supporting_evidence_ids)
                    | set(item.contradicting_evidence_ids)
                    | set(item.neutral_evidence_ids)
                    <= valid_ids
                )
                proposal = self._select_grounded(
                    grounded_proposals, state.hypotheses, state.required_change_type
                )
            else:
                proposal = self._select(
                    plain_proposals, state.hypotheses, state.required_change_type
                )
        except ValueError as exc:
            rejected = state.evolve(
                hypothesis_batches=batches,
                grounded_hypothesis_batches=grounded_batches,
                hypothesis_generation_attempts=attempts,
                next_step=Step.GENERATE_HYPOTHESES,
            )
            if attempts < state.max_hypothesis_generation_attempts:
                return rejected
            return self._fail(rejected, str(exc))
        iteration = state.iteration + 1
        hypothesis_id = uuid5(state.research_id, f"llm-hypothesis:{iteration}")
        if grounded:
            grounded_proposal = cast(GroundedHypothesisProposal, proposal)
            evidence_ids = (
                *grounded_proposal.supporting_evidence_ids,
                *grounded_proposal.contradicting_evidence_ids,
                *grounded_proposal.neutral_evidence_ids,
            )
            hypothesis = Hypothesis(
                id=hypothesis_id,
                evidence_source=EvidenceSource.SCIENTIFIC_LITERATURE,
                grounding_status=(
                    GroundingStatus.LITERATURE_GROUNDED
                    if grounded_proposal.supporting_evidence_ids
                    else GroundingStatus.PARTIALLY_GROUNDED
                ),
                evidence_ids=evidence_ids,
                **grounded_proposal.model_dump(exclude={"expected_impact"}),
            )
            linked_evidence = tuple(
                type(item).model_validate(
                    {
                        **item.model_dump(),
                        "target_hypothesis_id": hypothesis_id,
                        "relation": (
                            EvidenceRelation.SUPPORT
                            if item.id in grounded_proposal.supporting_evidence_ids
                            else EvidenceRelation.CONTRADICT
                            if item.id in grounded_proposal.contradicting_evidence_ids
                            else EvidenceRelation.NEUTRAL
                        ),
                    }
                )
                if item.id in evidence_ids
                else item
                for item in state.evidence
            )
        else:
            hypothesis = Hypothesis(
                id=hypothesis_id,
                evidence_source=EvidenceSource.REPOSITORY_AND_EXPERIMENT_HISTORY,
                grounding_status=GroundingStatus.REPOSITORY_ONLY,
                evidence_ids=(),
                **proposal.model_dump(exclude={"expected_impact"}),
            )
            linked_evidence = state.evidence
        return state.evolve(
            hypothesis_batches=batches,
            grounded_hypothesis_batches=grounded_batches,
            evidence=linked_evidence,
            hypothesis_generation_attempts=0,
            hypotheses=(*state.hypotheses, hypothesis),
            active_hypothesis_id=hypothesis.id,
            active_plan_id=None,
            active_study_id=None,
            iteration=iteration,
            budget=state.budget.consume(iterations=1),
            next_step=Step.PLAN_EXPERIMENT,
        )

    @staticmethod
    def _canonicalize_grounded(
        proposal: GroundedHypothesisProposal,
        evidence_ids: set[UUID],
        claim_to_evidence: dict[UUID, UUID],
    ) -> GroundedHypothesisProposal:
        """Accept an exact claim ID as shorthand for its one persisted evidence record."""

        def resolve(values: tuple[UUID, ...]) -> tuple[UUID, ...]:
            return tuple(
                value if value in evidence_ids else claim_to_evidence.get(value, value)
                for value in values
            )

        return proposal.model_copy(
            update={
                "supporting_evidence_ids": resolve(proposal.supporting_evidence_ids),
                "contradicting_evidence_ids": resolve(proposal.contradicting_evidence_ids),
                "neutral_evidence_ids": resolve(proposal.neutral_evidence_ids),
            }
        )

    @staticmethod
    def _select_grounded(
        proposals: tuple[GroundedHypothesisProposal, ...],
        tested: tuple[Hypothesis, ...],
        required_change_type: ChangeType | None = None,
    ) -> GroundedHypothesisProposal:
        prior = {" ".join(item.statement.lower().split()) for item in tested}
        candidates = [
            item
            for item in proposals
            if " ".join(item.statement.lower().split()) not in prior
            and (required_change_type is None or item.change_type == required_change_type)
        ]
        if not candidates:
            raise ValueError("No valid new evidence-grounded hypothesis was generated")
        return min(
            candidates,
            key=lambda item: (
                -(
                    item.confidence
                    * item.expected_impact
                    * item.evidence_confidence
                    * (1 + len(item.supporting_evidence_ids))
                    / (1 + len(item.contradicting_evidence_ids))
                )
                / (1 + item.estimated_cost),
                item.estimated_cost,
                item.statement,
            ),
        )

    def plan_experiment(self, state: ResearchState) -> ResearchState:
        if state.repository_inspection is None or state.active_hypothesis_id is None:
            raise ValueError("Planning requires inspection and selected hypothesis")
        inspection = state.repository_inspection
        hypothesis = next(
            item for item in state.hypotheses if item.id == state.active_hypothesis_id
        )
        required_change_type = state.required_change_type or hypothesis.change_type
        supported_parameters = tuple(TrainingOverrides.model_fields)
        prompt = (
            f"Research goal: {state.research_goal}\n"
            f"Selected hypothesis: {compact_json(hypothesis)}\n"
            f"Required plan change type: {required_change_type.value}.\n"
            f"Supported SearchSpace parameter names: {compact_json(supported_parameters)}. "
            "Do not invent other tunable parameter names.\n"
            f"Allowed repository paths (copy these exact strings): "
            f"{compact_json(inspection.file_tree)}\n"
            f"Repository inspection: {compact_json(inspection)}\n"
            f"Remaining HPO trials: {state.budget.max_hpo_trials - state.budget.hpo_trials}."
        )
        result, state = self._invoke(
            state,
            operation="experiment_planning",
            template="experiment_planning",
            user_prompt=prompt,
            response_model=ExperimentPlanProposal,
        )
        proposal = result.output
        if proposal.change_type != hypothesis.change_type:
            return self._fail(
                state, "Experiment plan change type differs from the selected hypothesis"
            )
        if (
            state.required_change_type is not None
            and proposal.change_type != state.required_change_type
        ):
            return self._fail(state, "Experiment plan violates the required change type")
        known = set(inspection.file_tree)
        by_name = {
            Path(path).name: path
            for path in inspection.file_tree
            if sum(Path(item).name == Path(path).name for item in inspection.file_tree) == 1
        }

        def resolve_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
            resolved = []
            for value in paths:
                candidate = value.strip().strip("`'\"")
                parts = candidate.split()
                if parts:
                    candidate = parts[-1].strip("`'\"")
                candidate = candidate.removeprefix("a/").removeprefix("b/")
                resolved.append(
                    candidate if candidate in known else by_name.get(Path(candidate).name, value)
                )
            return tuple(resolved)

        proposal = proposal.model_copy(
            update={
                "files_to_inspect": tuple(
                    path for path in resolve_paths(proposal.files_to_inspect) if path in known
                ),
                "files_to_modify": resolve_paths(proposal.files_to_modify),
            }
        )
        if not set(proposal.files_to_inspect + proposal.files_to_modify) <= known:
            return self._fail(state, "Experiment plan references unknown repository files")
        if (
            proposal.primary_metric != state.baseline.metric_name
            or proposal.direction != state.baseline.direction
        ):
            return self._fail(state, "Experiment plan cannot replace the configured objective")
        if proposal.search_space is not None:
            if len(proposal.search_space.parameters) > 6:
                return self._fail(state, "LLM search spaces are limited to six parameters")
            supported = set(TrainingOverrides.model_fields)
            if any(item.name not in supported for item in proposal.search_space.parameters):
                return self._fail(state, "LLM search space contains unsupported parameters")
            for parameter in proposal.search_space.parameters:
                choices = getattr(parameter, "choices", ())
                if len(choices) > 16:
                    return self._fail(state, "Categorical search choices exceed the project limit")
        remaining = min(
            state.budget.max_hpo_trials - state.budget.hpo_trials,
            state.budget.max_experiments - state.budget.experiments,
        )
        trials = min(proposal.estimated_trials, remaining) if proposal.search_space else 1
        if trials < 1:
            raise LLMBudgetError("No experiment budget remains for the proposed plan")
        identity = uuid5(hypothesis.id, "llm-plan")
        plan = ExperimentPlan(
            id=identity,
            hypothesis_id=hypothesis.id,
            patch_id=None,
            rationale=proposal.rationale,
            change_type=proposal.change_type,
            files_to_inspect=proposal.files_to_inspect,
            files_to_modify=proposal.files_to_modify,
            configuration_overrides=proposal.configuration_overrides,
            search_space=proposal.search_space,
            primary_metric=proposal.primary_metric,
            direction=proposal.direction,
            max_trials=trials,
            estimated_runtime_seconds=proposal.estimated_runtime_seconds,
            falsification_criteria=proposal.falsification_criteria,
            expected_effect=proposal.expected_effect,
            validation_checks=proposal.validation_checks,
        )
        changes: dict[str, object] = {
            "plans": (*state.plans, plan),
            "active_plan_id": plan.id,
            "hpo": None,
        }
        if proposal.search_space is not None:
            changes["hpo"] = HPOConfig(
                max_trials=trials,
                sampler_seed=state.hpo.sampler_seed if state.hpo else 42,
                search_space=proposal.search_space,
            )
        needs_patch = bool(plan.files_to_modify)
        changes["next_step"] = (
            Step.GENERATE_PATCH
            if needs_patch
            else Step.HPO_PLAN
            if proposal.search_space is not None
            else Step.EXPERIMENT
        )
        return state.evolve(**changes)

    def generate_patch(self, state: ResearchState) -> ResearchState:
        if state.active_plan_id is None or state.active_hypothesis_id is None:
            raise ValueError("Patch generation requires an active plan and hypothesis")
        if state.execution.baseline_repo_path is None or state.execution.base_commit_sha is None:
            raise ValueError("Patch generation requires a configured repository")
        plan = next(item for item in state.plans if item.id == state.active_plan_id)
        hypothesis = next(
            item for item in state.hypotheses if item.id == state.active_hypothesis_id
        )
        manager = WorktreeManager(
            state.execution.baseline_repo_path, state.execution.runtime_root / "worktrees"
        )
        validator = PatchValidator(manager)
        source_context = RepositoryInspector(max_context_characters=40_000).read_selected(
            state.execution.baseline_repo_path,
            tuple(dict.fromkeys(plan.files_to_inspect + plan.files_to_modify)),
        )
        feedback = ""
        current = state
        for attempt in range(state.llm.max_patch_repairs + 1 if state.llm else 1):
            prompt = (
                f"Hypothesis: {compact_json(hypothesis)}\n"
                f"Experiment plan: {compact_json(plan)}\n"
                f"Repository inspection: {compact_json(state.repository_inspection)}\n"
                f"Required hypothesis_id: {hypothesis.id}\n"
                f"Required base_commit_sha: {state.execution.base_commit_sha}\n"
                f"Allowed target files: {compact_json(plan.files_to_modify)}\n"
                f"Selected source content:{source_context}{feedback}"
            )
            result, current = self._invoke(
                current,
                operation="code_patch_generation",
                template="code_patch_generation",
                user_prompt=prompt,
                response_model=PatchProposal,
            )
            proposal = result.output.model_copy(update={"repair_attempt": attempt})
            current = current.evolve(patch_proposals=(*current.patch_proposals, proposal))
            if proposal.hypothesis_id != hypothesis.id:
                error = "Patch proposal hypothesis identity differs from the selected hypothesis"
            else:
                try:
                    actual = validator.validate(
                        proposal,
                        expected_sha=state.execution.base_commit_sha,
                        allowed_targets=plan.files_to_modify,
                    )
                except PatchPolicyError as exc:
                    error = str(exc)
                else:
                    patch = CodePatch(
                        id=uuid5(plan.id, "validated-patch"),
                        hypothesis_id=hypothesis.id,
                        base_commit_sha=state.execution.base_commit_sha,
                        description=proposal.explanation,
                        diff=actual,
                    )
                    updated_plan = plan.model_copy(update={"patch_id": patch.id})
                    return current.evolve(
                        patches=(*current.patches, patch),
                        plans=tuple(
                            updated_plan if item.id == plan.id else item for item in current.plans
                        ),
                        execution=current.execution.model_copy(update={"patch_diff": actual}),
                        next_step=Step.HPO_PLAN
                        if plan.search_space is not None
                        else Step.EXPERIMENT,
                    )
            feedback = f"\nPrevious patch was rejected: {error}. Repair it."
        if not current.budget.can_run_experiment():
            return self._fail(current, "Patch validation failed and experiment budget is exhausted")
        experiment_id = uuid5(plan.id, "preflight-failure")
        failure = "Patch repair limit exhausted: " + error
        experiment = Experiment(
            id=experiment_id,
            research_id=current.research_id,
            hypothesis_id=hypothesis.id,
            sequence=current.budget.experiments + 1,
            status=ExperimentStatus.FAILED,
            error=failure,
            result=ExperimentResult(status=ExperimentStatus.FAILED, error=failure),
        )
        trial = Trial(
            id=uuid5(experiment_id, "trial:0"),
            experiment_id=experiment_id,
            seed=current.simulation.seed,
            status=TrialStatus.FAILED,
            failure_reason=failure,
            started_at=utc_now(),
            finished_at=utc_now(),
            created_at=utc_now(),
        )
        return current.evolve(
            experiments=(*current.experiments, experiment),
            trials=(*current.trials, trial),
            budget=current.budget.consume(experiments=1, failed_experiments=1),
            next_step=Step.ANALYZE,
        )

    def critique(self, state: ResearchState) -> ResearchState:
        if state.decision is None or state.active_hypothesis_id is None:
            raise ValueError("Critique requires a deterministic decision")
        hypothesis = next(
            item for item in state.hypotheses if item.id == state.active_hypothesis_id
        )
        latest = state.decisions[-1]
        latest_trials = [item.model_dump(mode="json") for item in state.trials[-8:]]
        prompt = (
            f"Hypothesis: {compact_json(hypothesis)}\n"
            f"Deterministic decision: {compact_json(latest)}\n"
            f"Baseline: {compact_json(state.baseline)}\n"
            f"Latest trials: {compact_json(latest_trials)}\n"
            f"Required hypothesis_id: {hypothesis.id}."
        )
        result, state = self._invoke(
            state,
            operation="research_critique",
            template="research_critic",
            user_prompt=prompt,
            response_model=ResearchCritique,
        )
        critique = result.output
        if critique.hypothesis_id != hypothesis.id or critique.decision != state.decision:
            return self._fail(
                state, "Research critic attempted to change decision identity or value"
            )
        return state.evolve(
            critic_summaries=(*state.critic_summaries, critique), next_step=Step.DECISION
        )
