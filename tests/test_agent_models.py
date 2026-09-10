from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from labpilot.agent.service import AgentLoopService
from labpilot.llm.fake import FakeLLMClient
from labpilot.llm.models import (
    ExperimentPlanProposal,
    HypothesisProposal,
    InspectedFile,
    LLMSettings,
    PatchProposal,
    RepositoryInspection,
)
from labpilot.models.budget import ResearchBudget
from labpilot.models.common import (
    ChangeType,
    EvidenceSource,
    MetricDirection,
    Step,
)
from labpilot.models.literature import Hypothesis
from labpilot.models.state import ResearchState
from labpilot.services.real import configure_docker, prepare_example


def test_llm_budget_and_plan_contracts() -> None:
    budget = ResearchBudget(max_llm_calls=1, max_llm_tokens=20)
    assert budget.can_call_llm(20) and not budget.can_call_llm(21)
    used = budget.consume(llm_calls=1, llm_tokens=20)
    assert not used.can_call_llm()
    with pytest.raises(ValidationError):
        ExperimentPlanProposal(
            rationale="Invalid HPO plan",
            change_type=ChangeType.CODE_CHANGE_WITH_HPO,
            files_to_modify=("train.py",),
            primary_metric="accuracy",
            direction=MetricDirection.MAXIMIZE,
            estimated_runtime_seconds=1,
            falsification_criteria="No improvement",
            expected_effect="Improve",
            validation_checks=("compile",),
        )


def test_duplicate_hypothesis_is_rejected() -> None:
    prior = Hypothesis(
        statement="Add dropout",
        motivation="Fixture",
        evidence_source=EvidenceSource.REPOSITORY_AND_EXPERIMENT_HISTORY,
        expected_effect="Improve",
        confidence=0.5,
        estimated_cost=1,
        falsification_criteria="No gain",
    )
    proposal = HypothesisProposal(
        statement="  add   DROPOUT ",
        motivation="Duplicate",
        expected_effect="Improve",
        expected_impact=0.2,
        confidence=0.8,
        estimated_cost=1,
        falsification_criteria="No gain",
        change_type=ChangeType.CODE_CHANGE,
    )
    with pytest.raises(ValueError, match="duplicate"):
        AgentLoopService._select((proposal,), (prior,))


def test_patch_repair_limit_becomes_structured_preflight_failure(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "train.py").write_text("print('fixture')\n")
    (source / "config.yaml").write_text("dropout: 0.0\n")
    repo = prepare_example(source, tmp_path / "baseline")
    execution = configure_docker(repo, tmp_path / "runtime")
    hypothesis = Hypothesis(
        id=uuid4(),
        statement="Change training output",
        motivation="Fixture",
        evidence_source=EvidenceSource.REPOSITORY_AND_EXPERIMENT_HISTORY,
        expected_effect="Improve",
        confidence=0.5,
        estimated_cost=1,
        falsification_criteria="No improvement",
        change_type=ChangeType.CODE_CHANGE,
    )
    from labpilot.hpo.models import ExperimentPlan

    plan = ExperimentPlan(
        id=uuid4(),
        hypothesis_id=hypothesis.id,
        rationale="Fixture",
        change_type=ChangeType.CODE_CHANGE,
        files_to_inspect=("train.py",),
        files_to_modify=("train.py",),
        primary_metric="validation_accuracy",
        direction=MetricDirection.MAXIMIZE,
        max_trials=1,
    )
    inspection = RepositoryInspection(
        repo_path=str(repo),
        base_commit_sha=execution.base_commit_sha,
        training_entrypoint="train.py",
        important_files=(InspectedFile(path="train.py", size_bytes=17),),
        file_tree=("config.yaml", "train.py"),
        context_characters=17,
        model_summary="Fixture",
        configuration_summary="Fixture",
        available_hyperparameters=("dropout",),
        primary_metric="validation_accuracy",
        metric_direction=MetricDirection.MAXIMIZE,
        possible_change_points=("train.py",),
        constraints=(),
        warnings=(),
    )
    state = ResearchState(
        research_goal="Fixture",
        next_step=Step.GENERATE_PATCH,
        execution=execution,
        llm=LLMSettings(max_retries=0, max_patch_repairs=1),
        repository_inspection=inspection,
        hypotheses=(hypothesis,),
        active_hypothesis_id=hypothesis.id,
        plans=(plan,),
        active_plan_id=plan.id,
        iteration=1,
        budget=ResearchBudget(
            max_iterations=1,
            iterations=1,
            max_experiments=1,
            max_failed_experiments=1,
            max_llm_calls=2,
            max_llm_tokens=50_000,
        ),
    )
    invalid = PatchProposal(
        hypothesis_id=hypothesis.id,
        target_files=("train.py",),
        base_commit_sha=execution.base_commit_sha,
        unified_diff="not a unified diff",
        explanation="Invalid fixture",
        risk_notes=(),
    )
    client = FakeLLMClient((invalid, invalid))
    result = AgentLoopService(client).generate_patch(state)
    assert client.calls == result.budget.llm_calls == 2
    assert result.next_step == Step.ANALYZE
    assert result.experiments[-1].error.startswith("Patch repair limit exhausted")
    assert len(result.patch_proposals) == 2
