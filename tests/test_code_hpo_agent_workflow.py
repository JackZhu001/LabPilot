from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import uuid5

from labpilot.execution.git import git
from labpilot.graph.workflow import execute
from labpilot.hpo.models import StudyStatus
from labpilot.hpo.search_space import FloatParameter, SearchSpace
from labpilot.llm.fake import FakeLLMClient
from labpilot.llm.models import (
    ExperimentPlanProposal,
    HypothesisBatch,
    HypothesisProposal,
    LLMSettings,
    PatchProposal,
    RepositoryInspectionSummary,
    ResearchCritique,
)
from labpilot.models.budget import ResearchBudget
from labpilot.models.common import (
    ChangeType,
    ExperimentStatus,
    MetricDirection,
    ResearchDecision,
    RunStatus,
    Step,
)
from labpilot.models.execution import ExperimentPurpose
from labpilot.models.experiments import Baseline, Experiment, ExperimentResult
from labpilot.models.state import ResearchState
from labpilot.persistence.repository import SQLiteResearchRepository
from labpilot.services.fakes import fake_services
from labpilot.services.real import configure_docker, prepare_example


class CodeHPORunner:
    def __init__(self) -> None:
        self.calls: list[Experiment] = []

    def run(self, experiment: Experiment, baseline: Baseline) -> ExperimentResult:
        self.calls.append(experiment)
        if experiment.purpose == ExperimentPurpose.BASELINE:
            return ExperimentResult(status=ExperimentStatus.SUCCEEDED, value=0.8)
        assert experiment.patch_id is not None and experiment.config.apply_patch
        assert '+    return "gelu"' in experiment.config.patch_diff
        assert experiment.config.overrides is not None
        dropout = experiment.config.overrides.dropout
        assert dropout is not None
        return ExperimentResult(status=ExperimentStatus.SUCCEEDED, value=0.82 + dropout / 100)


def proposal(statement: str, change_type: ChangeType) -> HypothesisProposal:
    return HypothesisProposal(
        statement=statement,
        motivation="Exercise the requested bounded intervention",
        expected_effect="Improve validation accuracy",
        expected_impact=0.2,
        confidence=0.8,
        estimated_cost=1,
        falsification_criteria="Validation accuracy does not improve",
        change_type=change_type,
    )


def test_code_change_hpo_route_and_completed_resume_are_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "model.py").write_text('def activation() -> str:\n    return "relu"\n')
    (source / "train.py").write_text("print('train fixture')\n")
    (source / "config.yaml").write_text("dropout: 0.0\n")
    repo = prepare_example(source, tmp_path / "baseline")
    before = git(repo, "rev-parse", "HEAD").strip()
    state = ResearchState(
        research_goal="Require a source change with bounded HPO",
        next_step=Step.INSPECT_REPOSITORY,
        execution=configure_docker(repo, tmp_path / "runtime"),
        llm=LLMSettings(max_retries=0, max_patch_repairs=1),
        required_change_type=ChangeType.CODE_CHANGE_WITH_HPO,
        max_hypothesis_generation_attempts=2,
        baseline=Baseline(min_delta=0.01),
        budget=ResearchBudget(
            max_iterations=1,
            max_experiments=4,
            max_failed_experiments=1,
            max_replans=0,
            max_hpo_trials=3,
            max_llm_calls=6,
            max_llm_tokens=100_000,
        ),
    )
    hypothesis_id = uuid5(state.research_id, "llm-hypothesis:1")
    inspection = RepositoryInspectionSummary(
        training_entrypoint="train.py",
        model_summary="A tiny activation fixture",
        configuration_summary="Dropout is configurable",
        available_hyperparameters=("dropout",),
        primary_metric="validation_accuracy",
        metric_direction=MetricDirection.MAXIMIZE,
        possible_change_points=("model.py",),
        constraints=("Keep the patch to model.py",),
        warnings=(),
    )
    rejected = HypothesisBatch(proposals=(proposal("Only tune dropout", ChangeType.CONFIG_ONLY),))
    accepted = HypothesisBatch(
        proposals=(
            proposal(
                "Replace ReLU with GELU and tune dropout",
                ChangeType.CODE_CHANGE_WITH_HPO,
            ),
        )
    )
    search_space = SearchSpace(
        parameters=(FloatParameter(name="dropout", low=0.05, high=0.2, step=0.05),)
    )
    plan = ExperimentPlanProposal(
        rationale="Test one activation change across a bounded dropout search",
        change_type=ChangeType.CODE_CHANGE_WITH_HPO,
        files_to_inspect=("model.py", "train.py"),
        files_to_modify=("model.py",),
        search_space=search_space,
        primary_metric="validation_accuracy",
        direction=MetricDirection.MAXIMIZE,
        estimated_trials=3,
        estimated_runtime_seconds=3,
        falsification_criteria="Best trial does not improve by 0.01",
        expected_effect="GELU and dropout improve generalization",
        validation_checks=("python compile",),
    )
    patch = PatchProposal(
        hypothesis_id=hypothesis_id,
        target_files=("model.py",),
        base_commit_sha=before,
        unified_diff=(
            "diff --git a/model.py b/model.py\n"
            "--- a/model.py\n"
            "+++ b/model.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def activation() -> str:\n"
            '-    return "relu"\n'
            '+    return "gelu"\n'
        ),
        explanation="Use GELU while leaving the configurable dropout path intact",
        risk_notes=("Small activation behavior change",),
    )
    critique = ResearchCritique(
        hypothesis_id=hypothesis_id,
        decision=ResearchDecision.KEEP,
        summary="The best measured trial exceeded the deterministic threshold.",
        likely_explanation="The activation and bounded dropout setting helped.",
        next_step_advice="Retain the validated candidate.",
        adequately_tested=True,
    )
    client = FakeLLMClient((inspection, rejected, accepted, plan, patch, critique))
    runner = CodeHPORunner()
    services = replace(fake_services(state.simulation), experiment=runner, llm=client)
    store = SQLiteResearchRepository(tmp_path / "state.sqlite3")
    store.create(state)

    result = execute(store, state.research_id, services=services)

    assert result.status == RunStatus.COMPLETED
    assert len(result.hypothesis_batches) == 2 and client.calls == 6
    assert result.hypotheses[-1].change_type == ChangeType.CODE_CHANGE_WITH_HPO
    assert result.plans[-1].change_type == ChangeType.CODE_CHANGE_WITH_HPO
    assert result.plans[-1].search_space == search_space
    assert result.patches[-1].diff != patch.unified_diff
    assert '+    return "gelu"' in result.patches[-1].diff
    assert "index " in result.patches[-1].diff
    assert result.studies[-1].status == StudyStatus.SUCCEEDED
    hpo_trials = [item for item in result.trials if item.study_id is not None]
    assert len(hpo_trials) == 3
    best = next(item for item in hpo_trials if item.id == result.studies[-1].best_trial_id)
    assert best.primary_metric_value == max(item.primary_metric_value for item in hpo_trials)
    assert result.decisions[-1].experiment_id == best.experiment_id
    assert result.decision == ResearchDecision.KEEP
    assert git(repo, "rev-parse", "HEAD").strip() == before
    assert git(repo, "status", "--porcelain") == ""

    resumed_client = FakeLLMClient(())
    resumed_runner = CodeHPORunner()
    resumed = execute(
        store,
        state.research_id,
        services=replace(services, llm=resumed_client, experiment=resumed_runner),
    )
    assert resumed == result
    assert resumed_client.calls == 0
    assert resumed_runner.calls == []
    store.close()
