from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import BaseModel

from labpilot.agent.service import AgentLoopService
from labpilot.hpo.models import ExperimentPlan
from labpilot.llm.deepseek import DeepSeekLLMClient
from labpilot.llm.models import InspectedFile, LLMSettings, RepositoryInspection
from labpilot.models.budget import ResearchBudget
from labpilot.models.common import ChangeType, EvidenceSource, MetricDirection, Step
from labpilot.models.literature import Hypothesis
from labpilot.models.state import ResearchState
from labpilot.services.real import configure_docker, prepare_example

pytestmark = pytest.mark.live_llm


class Connectivity(BaseModel):
    ok: bool


def test_live_deepseek_structured_connectivity() -> None:
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY is unavailable")
    result = DeepSeekLLMClient.from_environment().generate_structured(
        research_id=uuid4(),
        operation="live_connectivity",
        prompt_template="live:v1",
        system_prompt="Return JSON only.",
        user_prompt='Return JSON with exactly {"ok": true}.',
        response_model=Connectivity,
        max_output_tokens=128,
        max_attempts=1,
    )
    assert result.output.ok and result.usage[0].total_tokens > 0


def test_live_deepseek_generates_validated_patch(tmp_path: Path) -> None:
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY is unavailable")
    source = tmp_path / "source"
    source.mkdir()
    (source / "train.py").write_text("print('fixture')\n")
    (source / "config.yaml").write_text("dropout: 0.0\n")
    repo = prepare_example(source, tmp_path / "baseline")
    execution = configure_docker(repo, tmp_path / "runtime")
    hypothesis = Hypothesis(
        statement="Change the fixture message to improved fixture",
        motivation="Validate the live code role",
        evidence_source=EvidenceSource.REPOSITORY_AND_EXPERIMENT_HISTORY,
        expected_effect="Print the updated message",
        confidence=1,
        estimated_cost=1,
        falsification_criteria="The source does not contain the updated message",
        change_type=ChangeType.CODE_CHANGE,
    )
    plan = ExperimentPlan(
        id=uuid4(),
        hypothesis_id=hypothesis.id,
        rationale="Modify one literal",
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
        model_summary="One print statement",
        configuration_summary="Fixture configuration",
        available_hyperparameters=("dropout",),
        primary_metric="validation_accuracy",
        metric_direction=MetricDirection.MAXIMIZE,
        possible_change_points=("train.py",),
        constraints=("Only change the string literal",),
        warnings=(),
    )
    settings = LLMSettings.from_environment().model_copy(
        update={"max_retries": 1, "max_patch_repairs": 1, "max_output_tokens": 1024}
    )
    state = ResearchState(
        research_goal="Validate live patch generation",
        next_step=Step.GENERATE_PATCH,
        execution=execution,
        llm=settings,
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
            max_llm_tokens=20_000,
        ),
    )
    result = AgentLoopService(DeepSeekLLMClient(settings)).generate_patch(state)
    assert result.next_step == Step.EXPERIMENT, result.model_dump_json(indent=2)
    assert len(result.patches) == 1
    assert "+print('improved fixture')" in result.patches[0].diff
    assert (repo / "train.py").read_text() == "print('fixture')\n"
