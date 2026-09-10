from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import httpx
import pytest
from pydantic import ValidationError

from labpilot.agent.service import AgentLoopService
from labpilot.graph.workflow import execute
from labpilot.literature.agent import EvidenceClassifier, LiteratureAgentService
from labpilot.literature.arxiv import ArxivProvider
from labpilot.literature.dedup import deduplicate_papers
from labpilot.literature.providers import LiteratureProviderError
from labpilot.literature.semantic_scholar import SemanticScholarProvider
from labpilot.literature.service import LiteratureRetrievalService
from labpilot.llm.fake import FakeLLMClient
from labpilot.llm.models import (
    ExperimentPlanProposal,
    LLMSettings,
    RepositoryInspection,
    RepositoryInspectionSummary,
    ResearchCritique,
)
from labpilot.models.budget import ResearchBudget
from labpilot.models.common import (
    ChangeType,
    EvidenceRelation,
    EvidenceSource,
    ExperimentStatus,
    GroundingStatus,
    MetricDirection,
    ResearchDecision,
    SourceScope,
    Step,
)
from labpilot.models.execution import ExecutionConfig, ExperimentPurpose
from labpilot.models.experiments import Baseline, Experiment, ExperimentResult
from labpilot.models.literature import (
    Claim,
    ClaimBatch,
    ClaimDraft,
    Evidence,
    EvidenceClassificationDraft,
    EvidenceDraft,
    EvidenceSynthesis,
    EvidenceSynthesisDraft,
    GroundedHypothesisBatch,
    GroundedHypothesisProposal,
    LiteratureQuery,
    LiteratureQueryDraft,
    LiteratureQueryPlan,
    LiteratureQueryPlanDraft,
    LiteratureSettings,
    Paper,
    PaperCandidate,
)
from labpilot.models.state import ResearchState
from labpilot.models.training import TrainingOverrides
from labpilot.persistence.repository import SQLiteResearchRepository
from labpilot.services.fakes import fake_services
from labpilot.services.real import configure_docker, prepare_example


class CountingProvider:
    name = "arxiv"

    def __init__(self, papers: tuple[PaperCandidate, ...]) -> None:
        self.papers = papers
        self.calls = 0

    def search(self, query: str, max_results: int) -> tuple[PaperCandidate, ...]:
        del query
        self.calls += 1
        return self.papers[:max_results]


class FailingProvider:
    name = "semantic_scholar"

    def search(self, query: str, max_results: int) -> tuple[PaperCandidate, ...]:
        del query, max_results
        raise LiteratureProviderError("rate limited")


class MeasuredRunner:
    def __init__(self) -> None:
        self.calls: list[UUID] = []

    def run(self, experiment: Experiment, baseline: Baseline) -> ExperimentResult:
        self.calls.append(experiment.id)
        value = 0.90 if experiment.purpose == ExperimentPurpose.BASELINE else 0.92
        return ExperimentResult(status=ExperimentStatus.SUCCEEDED, value=value)


def inspection(tmp_path: Path) -> RepositoryInspection:
    return RepositoryInspection(
        repo_path=str(tmp_path),
        base_commit_sha="a" * 40,
        training_entrypoint="train.py",
        important_files=({"path": "train.py", "size_bytes": 10},),
        file_tree=("train.py",),
        context_characters=10,
        model_summary="small MLP",
        configuration_summary="dropout configurable",
        available_hyperparameters=("dropout",),
        primary_metric="validation_accuracy",
        metric_direction=MetricDirection.MAXIMIZE,
        possible_change_points=("train.py",),
        constraints=(),
        warnings=(),
    )


def candidate(**updates: object) -> PaperCandidate:
    values: dict[str, object] = {
        "title": "Dropout improves neural network generalization",
        "authors": ("A. Author",),
        "abstract": "Moderate dropout improved validation accuracy on image classification.",
        "published_at": date(2020, 1, 1),
        "external_id": "123",
        "provider": "arxiv",
    }
    values.update(updates)
    return PaperCandidate.model_validate(values)


def test_query_plan_is_bounded() -> None:
    query = LiteratureQueryDraft(
        query="dropout image classification",
        motivation="Find applicable regularization evidence",
        target_concepts=("dropout",),
    )
    with pytest.raises(ValidationError):
        LiteratureQueryPlanDraft(queries=(query, query, query, query))


def test_arxiv_provider_normalizes_atom_response(monkeypatch: pytest.MonkeyPatch) -> None:
    xml = b"""<?xml version='1.0'?>
    <feed xmlns='http://www.w3.org/2005/Atom' xmlns:arxiv='http://arxiv.org/schemas/atom'>
      <entry><id>http://arxiv.org/abs/1234.5678v1</id><title> A useful paper </title>
      <summary> A measured result. </summary><published>2020-01-02T00:00:00Z</published>
      <author><name>A. Author</name></author><arxiv:doi>10.1/example</arxiv:doi></entry>
    </feed>"""
    response = httpx.Response(
        200, content=xml, request=httpx.Request("GET", "https://export.arxiv.org")
    )

    class Client:
        def __init__(self, **kwargs: object) -> None:
            pass

        def __enter__(self) -> Client:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def get(self, *args: object, **kwargs: object) -> httpx.Response:
            return response

    monkeypatch.setattr(httpx, "Client", Client)
    paper = ArxivProvider().search("regularization", 1)[0]
    assert paper.arxiv_id == "1234.5678v1"
    assert paper.doi == "10.1/example"
    assert paper.abstract == "A measured result."


def test_arxiv_provider_skips_malformed_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    xml = b"""<feed xmlns='http://www.w3.org/2005/Atom'>
      <entry><id>not a url</id><title>Malformed</title><published>not-a-date</published></entry>
    </feed>"""
    response = httpx.Response(
        200, content=xml, request=httpx.Request("GET", "https://export.arxiv.org")
    )

    class Client:
        def __init__(self, **kwargs: object) -> None:
            pass

        def __enter__(self) -> Client:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def get(self, *args: object, **kwargs: object) -> httpx.Response:
            return response

    monkeypatch.setattr(httpx, "Client", Client)
    assert ArxivProvider().search("regularization", 1) == ()


def test_semantic_scholar_provider_normalizes_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = httpx.Response(
        200,
        json={
            "data": [
                {
                    "paperId": "s2-id",
                    "title": "A useful paper",
                    "authors": [{"name": "A. Author"}],
                    "abstract": "A measured result.",
                    "publicationDate": "2020-01-02",
                    "url": "https://www.semanticscholar.org/paper/s2-id",
                    "externalIds": {"DOI": "10.1/example", "ArXiv": "1234.5678"},
                    "venue": "TestConf",
                }
            ]
        },
        request=httpx.Request("GET", "https://api.semanticscholar.org"),
    )

    class Client:
        def __init__(self, **kwargs: object) -> None:
            pass

        def __enter__(self) -> Client:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def get(self, *args: object, **kwargs: object) -> httpx.Response:
            return response

    monkeypatch.setattr(httpx, "Client", Client)
    paper = SemanticScholarProvider(env={}).search("regularization", 1)[0]
    assert paper.external_id == "s2-id"
    assert paper.arxiv_id == "1234.5678"
    assert paper.venue == "TestConf"


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (
            candidate(doi="10.1/ABC"),
            candidate(provider="semantic_scholar", doi="https://doi.org/10.1/abc"),
        ),
        (
            candidate(arxiv_id="1706.12345v1"),
            candidate(provider="semantic_scholar", arxiv_id="1706.12345"),
        ),
        (
            candidate(),
            candidate(
                provider="semantic_scholar",
                external_id="other",
                title="Dropout: improves neural-network generalization!",
            ),
        ),
    ],
)
def test_deduplication_identifier_and_conservative_title(
    left: PaperCandidate, right: PaperCandidate
) -> None:
    result = deduplicate_papers((left, right))
    assert len(result) == 1
    assert {ref.provider for ref in result[0][1]} == {left.provider, right.provider}


def test_cache_avoids_duplicate_provider_calls_and_failure_degrades(tmp_path: Path) -> None:
    working = CountingProvider((candidate(),))
    service = LiteratureRetrievalService((FailingProvider(), working), tmp_path / "cache")
    query = LiteratureQuery(
        id=uuid4(), query="dropout", motivation="test", target_concepts=("dropout",)
    )
    plan = LiteratureQueryPlan(queries=(query,))
    first, failures = service.retrieve(uuid4(), plan, 3)
    second, _ = service.retrieve(uuid4(), plan, 3)
    assert len(first) == len(second) == 1
    assert working.calls == 1
    assert failures and failures[0].startswith("semantic_scholar:")


def extraction_state(tmp_path: Path, response: ClaimBatch) -> ResearchState:
    paper = Paper(
        title="Regularization study",
        abstract="Moderate dropout improved validation accuracy on image classification.",
        source_provider="arxiv",
    )
    return ResearchState(
        research_goal="Improve accuracy",
        next_step=Step.EXTRACT_CLAIMS,
        execution=ExecutionConfig(runtime_root=tmp_path),
        llm=LLMSettings(max_retries=0),
        literature_settings=LiteratureSettings(enabled=True, max_claims_per_paper=2),
        papers=(paper,),
        budget=ResearchBudget(
            max_literature_queries=1,
            max_papers=1,
            papers=1,
            max_claims=2,
            max_llm_calls=2,
            max_llm_tokens=10_000,
        ),
    )


def test_claim_source_provenance_and_unsupported_span_rejection(tmp_path: Path) -> None:
    supported = ClaimDraft(
        statement="Dropout improved validation accuracy",
        confidence=0.8,
        source_span="Moderate dropout improved validation accuracy",
        source_scope=SourceScope.ABSTRACT,
    )
    unsupported = ClaimDraft(
        statement="Normalization caused the gain",
        confidence=0.9,
        source_span="Normalization caused the gain",
        source_scope=SourceScope.ABSTRACT,
    )
    batch = ClaimBatch(claims=(supported, unsupported))
    state = extraction_state(tmp_path, batch)
    service = LiteratureAgentService(
        replace(fake_services(state.simulation), llm=FakeLLMClient((batch,)))
    )
    result = service.extract_claims(state)
    assert len(result.claims) == 1
    assert result.claims[0].paper_id == state.papers[0].id
    assert result.claims[0].source_span == supported.source_span
    assert result.budget.claims == 1


@pytest.mark.parametrize("relation", tuple(EvidenceRelation))
def test_evidence_classifier_retains_explicit_relation(
    tmp_path: Path, relation: EvidenceRelation
) -> None:
    paper = Paper(title="Study", abstract="A measured result.", source_provider="arxiv")
    claim = Claim(
        paper_id=paper.id,
        statement="A measured result",
        confidence=0.8,
        source_span="A measured result.",
        source_scope=SourceScope.ABSTRACT,
    )
    output = EvidenceClassificationDraft(
        relation=relation,
        summary=f"The claim is {relation.value.lower()}",
        confidence=0.7,
    )
    state = ResearchState(
        research_goal="Test a candidate",
        llm=LLMSettings(max_retries=0),
        budget=ResearchBudget(max_llm_calls=1, max_llm_tokens=10_000),
    )
    services = replace(fake_services(state.simulation), llm=FakeLLMClient((output,)))
    evidence, updated = EvidenceClassifier(services).classify(
        state, claim=claim, candidate_hypothesis="Use the intervention"
    )
    assert evidence.relation == relation
    assert evidence.claim_id == claim.id and evidence.paper_id == paper.id
    assert evidence.source_span == claim.source_span
    assert updated.budget.llm_calls == 1


def test_conflicting_evidence_and_grounded_hypothesis_links(tmp_path: Path) -> None:
    paper = Paper(title="Study", abstract="A B C", source_provider="arxiv")
    claims = tuple(
        Claim(
            id=uuid4(),
            paper_id=paper.id,
            statement=f"claim {relation.value}",
            confidence=0.8,
            source_span=letter,
            source_scope=SourceScope.ABSTRACT,
        )
        for relation, letter in zip(EvidenceRelation, ("A", "B", "C"), strict=True)
    )
    evidence = tuple(
        Evidence(
            id=uuid4(),
            claim_id=claim.id,
            paper_id=paper.id,
            relation=relation,
            summary=f"{relation.value} finding",
            confidence=0.7,
            source_span=claim.source_span,
        )
        for claim, relation in zip(claims, EvidenceRelation, strict=True)
    )
    proposal = GroundedHypothesisProposal(
        statement="Test moderate dropout",
        motivation="Evidence is promising but conditional",
        supporting_evidence_ids=(claims[0].id,),
        contradicting_evidence_ids=(claims[1].id,),
        neutral_evidence_ids=(claims[2].id,),
        evidence_confidence=0.7,
        expected_effect="Improve accuracy",
        expected_impact=0.2,
        confidence=0.75,
        estimated_cost=1,
        falsification_criteria="Accuracy does not improve",
        change_type=ChangeType.CONFIG_ONLY,
    )
    state = ResearchState(
        research_goal="Improve accuracy",
        next_step=Step.GENERATE_HYPOTHESES,
        execution=ExecutionConfig(
            baseline_repo_path=tmp_path,
            base_commit_sha="a" * 40,
            runtime_root=tmp_path,
        ),
        llm=LLMSettings(max_retries=0),
        repository_inspection=inspection(tmp_path),
        literature_settings=LiteratureSettings(enabled=True),
        papers=(paper,),
        claims=claims,
        evidence=evidence,
        evidence_synthesis=EvidenceSynthesis(
            conflicting_findings=("Results vary by training regime",)
        ),
        budget=ResearchBudget(
            max_literature_queries=1,
            max_papers=1,
            papers=1,
            max_claims=3,
            claims=3,
            max_iterations=1,
            max_experiments=1,
            max_llm_calls=1,
            max_llm_tokens=10_000,
        ),
    )
    result = AgentLoopService(
        FakeLLMClient((GroundedHypothesisBatch(proposals=(proposal,)),))
    ).generate_hypotheses(state)
    hypothesis = result.hypotheses[-1]
    assert hypothesis.grounding_status == GroundingStatus.LITERATURE_GROUNDED
    assert hypothesis.evidence_source == EvidenceSource.SCIENTIFIC_LITERATURE
    assert set(hypothesis.evidence_ids) == {item.id for item in evidence}
    assert {item.relation for item in result.evidence} == set(EvidenceRelation)
    assert all(item.target_hypothesis_id == hypothesis.id for item in result.evidence)


def test_no_literature_falls_back_to_repository_grounding(tmp_path: Path) -> None:
    from labpilot.llm.models import HypothesisBatch, HypothesisProposal

    proposal = HypothesisProposal(
        statement="Test dropout",
        motivation="Repository exposes dropout",
        expected_effect="Improve accuracy",
        expected_impact=0.2,
        confidence=0.7,
        estimated_cost=1,
        falsification_criteria="No improvement",
        change_type=ChangeType.CONFIG_ONLY,
    )
    state = ResearchState(
        research_goal="Improve accuracy",
        next_step=Step.GENERATE_HYPOTHESES,
        execution=ExecutionConfig(
            baseline_repo_path=tmp_path, base_commit_sha="a" * 40, runtime_root=tmp_path
        ),
        llm=LLMSettings(max_retries=0),
        repository_inspection=inspection(tmp_path),
        budget=ResearchBudget(
            max_iterations=1,
            max_experiments=1,
            max_llm_calls=1,
            max_llm_tokens=10_000,
        ),
    )
    result = AgentLoopService(
        FakeLLMClient((HypothesisBatch(proposals=(proposal,)),))
    ).generate_hypotheses(state)
    assert result.hypotheses[-1].grounding_status == GroundingStatus.REPOSITORY_ONLY


def test_literature_budget_exhaustion_skips_additional_queries(tmp_path: Path) -> None:
    state = ResearchState(
        research_goal="Improve accuracy",
        next_step=Step.PLAN_LITERATURE_QUERIES,
        llm=LLMSettings(),
        execution=ExecutionConfig(
            baseline_repo_path=tmp_path,
            base_commit_sha="a" * 40,
            runtime_root=tmp_path,
        ),
        repository_inspection=inspection(tmp_path),
        literature_settings=LiteratureSettings(enabled=True),
        budget=ResearchBudget(),
    )
    client = FakeLLMClient(())
    service = LiteratureAgentService(replace(fake_services(state.simulation), llm=client))
    result = service.plan_queries(state)
    assert result.next_step == Step.RETRIEVE_PAPERS
    assert client.calls == 0


def test_phase5_checkpoint_resume_preserves_provider_and_provenance(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "train.py").write_text("print('fixture')\n")
    (source / "config.yaml").write_text("dropout: 0.0\n")
    repo = prepare_example(source, tmp_path / "baseline")
    state = ResearchState(
        research_goal="Improve image classification accuracy with lightweight regularization",
        next_step=Step.INSPECT_REPOSITORY,
        execution=configure_docker(repo, tmp_path / "runtime"),
        llm=LLMSettings(max_retries=0),
        literature_settings=LiteratureSettings(
            enabled=True, providers=("arxiv",), max_claims_per_paper=1
        ),
        baseline=Baseline(min_delta=0.01),
        budget=ResearchBudget(
            max_literature_queries=1,
            max_papers=1,
            max_claims=1,
            max_iterations=1,
            max_experiments=2,
            max_failed_experiments=1,
            max_replans=0,
            max_llm_calls=7,
            max_llm_tokens=50_000,
        ),
    )
    paper_id = uuid5(state.research_id, "paper:0")
    claim_id = uuid5(paper_id, "claim:0")
    evidence_id = uuid5(claim_id, "evidence:0")
    hypothesis_id = uuid5(state.research_id, "llm-hypothesis:1")
    inspection_output = RepositoryInspectionSummary(
        training_entrypoint="train.py",
        model_summary="small fixture model",
        configuration_summary="dropout is configurable",
        available_hyperparameters=("dropout",),
        primary_metric="validation_accuracy",
        metric_direction=MetricDirection.MAXIMIZE,
        possible_change_points=("config.yaml",),
        constraints=(),
        warnings=(),
    )
    query_plan = LiteratureQueryPlanDraft(
        queries=(
            LiteratureQueryDraft(
                query="dropout image classification",
                motivation="Find regularization evidence",
                target_concepts=("dropout", "generalization"),
                max_results=1,
            ),
        )
    )
    claim_batch = ClaimBatch(
        claims=(
            ClaimDraft(
                statement="Moderate dropout improved validation accuracy",
                confidence=0.8,
                source_span="Moderate dropout improved validation accuracy",
                source_scope=SourceScope.ABSTRACT,
            ),
        )
    )
    synthesis = EvidenceSynthesisDraft(
        consistent_findings=("Dropout can improve validation accuracy",),
        conflicting_findings=(),
        gaps=("Applicability to this small MLP is uncertain",),
        evidence=(
            EvidenceDraft(
                claim_id=claim_id,
                relation=EvidenceRelation.SUPPORT,
                summary="The paper reports a relevant validation gain",
                confidence=0.75,
                applicability_notes="Image classification task is aligned",
            ),
        ),
    )
    grounded = GroundedHypothesisBatch(
        proposals=(
            GroundedHypothesisProposal(
                statement="Increase dropout to 0.2",
                motivation="One relevant paper reports a validation gain",
                supporting_evidence_ids=(evidence_id,),
                evidence_confidence=0.75,
                expected_effect="Improve validation accuracy",
                expected_impact=0.2,
                confidence=0.75,
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
        summary="The measured gain met the deterministic threshold",
        likely_explanation="Moderate regularization improved generalization",
        next_step_advice="Retain the configuration",
        adequately_tested=True,
    )
    provider = CountingProvider((candidate(),))
    runner = MeasuredRunner()
    store = SQLiteResearchRepository(tmp_path / "state.sqlite3")
    store.create(state)
    first_client = FakeLLMClient((inspection_output, query_plan))
    services = replace(
        fake_services(state.simulation),
        experiment=runner,
        llm=first_client,
        literature_providers=(provider,),
    )
    paused = execute(store, state.research_id, stop_after=3, services=services)
    assert paused.next_step == Step.EXTRACT_CLAIMS
    assert provider.calls == 1
    store.close()

    reopened = SQLiteResearchRepository(tmp_path / "state.sqlite3")
    second_client = FakeLLMClient((claim_batch, synthesis, grounded, plan, critique))
    result = execute(
        reopened,
        state.research_id,
        services=replace(services, llm=second_client),
    )
    assert provider.calls == 1
    assert result.decision == ResearchDecision.KEEP
    assert len(result.papers) == len(result.claims) == len(result.evidence) == 1
    assert result.hypotheses[-1].supporting_evidence_ids == (evidence_id,)
    assert result.evidence[0].target_hypothesis_id == hypothesis_id
    assert result.budget.literature_queries == 1
    assert second_client.calls == 5
    reopened.close()
