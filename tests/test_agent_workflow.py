from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid5

from labpilot.agent.service import AgentLoopService
from labpilot.graph.workflow import execute
from labpilot.llm.fake import FakeLLMClient
from labpilot.llm.models import (
    ExperimentPlanProposal,
    HypothesisBatch,
    HypothesisProposal,
    LLMSettings,
    RepositoryInspectionSummary,
    ResearchCritique,
)
from labpilot.models.budget import ResearchBudget
from labpilot.models.common import (
    ChangeType,
    ExperimentStatus,
    MetricDirection,
    ResearchDecision,
    Step,
)
from labpilot.models.execution import ExperimentPurpose
from labpilot.models.experiments import Baseline, Experiment, ExperimentResult
from labpilot.models.state import ResearchState
from labpilot.models.training import TrainingOverrides
from labpilot.persistence.repository import SQLiteResearchRepository
from labpilot.services.fakes import fake_services
from labpilot.services.real import configure_docker, prepare_example


class MeasuredRunner:
    def __init__(self) -> None:
        self.calls: list[UUID] = []

    def run(self, experiment: Experiment, baseline: Baseline) -> ExperimentResult:
        self.calls.append(experiment.id)
        value = 0.9 if experiment.purpose == ExperimentPurpose.BASELINE else 0.92
        return ExperimentResult(status=ExperimentStatus.SUCCEEDED, value=value)


def test_agent_steps_checkpoint_resume_and_decision_stays_deterministic(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "train.py").write_text("print('fixture')\n")
    (source / "config.yaml").write_text("dropout: 0.0\n")
    repo = prepare_example(source, tmp_path / "baseline")
    state = ResearchState(
        research_goal="Improve accuracy",
        next_step=Step.INSPECT_REPOSITORY,
        execution=configure_docker(repo, tmp_path / "runtime"),
        llm=LLMSettings(max_retries=0),
        baseline=Baseline(min_delta=0.01),
        budget=ResearchBudget(
            max_iterations=1,
            max_experiments=2,
            max_failed_experiments=1,
            max_replans=0,
            max_llm_calls=4,
            max_llm_tokens=50_000,
        ),
    )
    hypothesis_id = uuid5(state.research_id, "llm-hypothesis:1")
    inspection = RepositoryInspectionSummary(
        training_entrypoint="train.py",
        model_summary="Small fixture model",
        configuration_summary="Dropout is configurable",
        available_hyperparameters=("dropout",),
        primary_metric="validation_accuracy",
        metric_direction=MetricDirection.MAXIMIZE,
        possible_change_points=("config.yaml",),
        constraints=("CPU only",),
        warnings=(),
    )
    batch = HypothesisBatch(
        proposals=(
            HypothesisProposal(
                statement="Increase dropout to 0.2",
                motivation="Test regularization",
                expected_effect="Improve validation accuracy",
                expected_impact=0.2,
                confidence=0.8,
                estimated_cost=1,
                falsification_criteria="Accuracy fails to improve",
                change_type=ChangeType.CONFIG_ONLY,
            ),
        )
    )
    plan = ExperimentPlanProposal(
        rationale="Change one validated parameter",
        change_type=ChangeType.CONFIG_ONLY,
        files_to_inspect=("config.yaml",),
        files_to_modify=(),
        configuration_overrides=TrainingOverrides(dropout=0.2),
        primary_metric="validation_accuracy",
        direction=MetricDirection.MAXIMIZE,
        estimated_trials=1,
        estimated_runtime_seconds=1,
        falsification_criteria="Accuracy fails to improve",
        expected_effect="Improve validation accuracy",
        validation_checks=("configuration schema",),
    )
    critique = ResearchCritique(
        hypothesis_id=hypothesis_id,
        decision=ResearchDecision.KEEP,
        summary="The measured improvement met policy.",
        likely_explanation="The configuration improved generalization.",
        next_step_advice="Retain the measured configuration.",
        adequately_tested=True,
    )
    store = SQLiteResearchRepository(tmp_path / "state.sqlite3")
    store.create(state)
    runner = MeasuredRunner()
    first_client = FakeLLMClient((inspection, batch))
    services = replace(fake_services(state.simulation), experiment=runner, llm=first_client)
    paused = execute(store, state.research_id, stop_after=3, services=services)
    assert paused.next_step == Step.PLAN_EXPERIMENT
    assert first_client.calls == 2 and len(runner.calls) == 1
    baseline_id = runner.calls[0]
    store.close()

    reopened = SQLiteResearchRepository(tmp_path / "state.sqlite3")
    second_client = FakeLLMClient((plan, critique))
    result = execute(
        reopened,
        state.research_id,
        services=replace(services, llm=second_client),
    )
    assert second_client.calls == 2
    assert runner.calls.count(baseline_id) == 1
    assert result.decision == ResearchDecision.KEEP
    assert result.decisions[-1].reason == "Metric meets the minimum improvement threshold"
    assert result.critic_summaries[-1].decision == result.decision
    assert result.budget.llm_calls == len(result.llm_usage) == 4
    assert result.budget.llm_tokens == sum(item.total_tokens for item in result.llm_usage)
    assert result.experiments[-1].config.overrides == TrainingOverrides(dropout=0.2)
    history = AgentLoopService._history(result)
    assert history[-1]["plan"] is not None
    assert history[-1]["trial_parameters"] == [{"values": []}]
    assert history[-1]["metrics"] == [0.92]
    assert history[-1]["baseline_metric"] == 0.9
    assert history[-1]["decision"] == "KEEP"
    reopened.close()
