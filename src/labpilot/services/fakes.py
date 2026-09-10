"""Offline fixtures with stable IDs and explicitly simulated outcomes."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID, uuid5

from labpilot.models.common import (
    EvidenceRelation,
    ExperimentStatus,
    FakeOutcome,
    GroundingStatus,
    SourceScope,
)
from labpilot.models.experiments import Baseline, Experiment, ExperimentResult
from labpilot.models.literature import Claim, Evidence, Hypothesis, Paper
from labpilot.models.state import SimulationConfig
from labpilot.services.interfaces import ResearchServices


class FakeLiteratureProvider:
    def retrieve(self, research_id: UUID, goal: str) -> tuple[Paper, ...]:
        return (
            Paper(
                id=uuid5(research_id, "paper:0"),
                title=f"Synthetic literature for: {goal}",
                authors=("LabPilot Fixture",),
                abstract="Synthetic fixture; not a real publication or scientific evidence.",
                published_at=date(2024, 1, 1),
                external_id="fixture:0",
                source_provider="fake",
                retrieved_at=datetime(2024, 1, 1, tzinfo=UTC),
            ),
        )


class FakeEvidenceExtractor:
    def extract(self, papers: tuple[Paper, ...]) -> tuple[tuple[Claim, ...], tuple[Evidence, ...]]:
        claims = tuple(
            Claim(
                id=uuid5(paper.id, "claim:0"),
                paper_id=paper.id,
                statement="A controlled intervention may improve the objective (synthetic).",
                confidence=0.5,
                source_span="Synthetic fixture; not a real publication or scientific evidence.",
                source_scope=SourceScope.ABSTRACT,
            )
            for paper in papers
        )
        evidence = tuple(
            Evidence(
                id=uuid5(claim.id, "evidence:0"),
                claim_id=claim.id,
                paper_id=claim.paper_id,
                relation=EvidenceRelation.SUPPORT,
                summary="Synthetic supporting evidence used only to exercise provenance.",
                confidence=0.5,
            )
            for claim in claims
        )
        return claims, evidence


class FakeHypothesisGenerator:
    def generate(
        self, research_id: UUID, goal: str, evidence: tuple[Evidence, ...], iteration: int
    ) -> Hypothesis:
        return Hypothesis(
            id=uuid5(research_id, f"hypothesis:{iteration}"),
            statement=f"Synthetic hypothesis {iteration}: {goal}",
            motivation="Exercise the research loop with traceable fixture evidence.",
            evidence_ids=tuple(item.id for item in evidence),
            supporting_evidence_ids=tuple(item.id for item in evidence),
            evidence_confidence=0.5,
            grounding_status=GroundingStatus.LITERATURE_GROUNDED,
            expected_effect="Improve the configured objective by the minimum delta.",
            confidence=0.5,
            estimated_cost=0,
            falsification_criteria="The objective falls short of the minimum improvement.",
        )


@dataclass(frozen=True)
class FakeExperimentRunner:
    simulation: SimulationConfig

    def run(self, experiment: Experiment, baseline: Baseline) -> ExperimentResult:
        index = min(experiment.sequence - 1, len(self.simulation.outcomes) - 1)
        outcome = self.simulation.outcomes[index]
        if outcome == FakeOutcome.FAIL:
            return ExperimentResult(
                status=ExperimentStatus.FAILED, error="Simulated runner failure"
            )
        sign = 1 if baseline.direction.value == "MAXIMIZE" else -1
        change = {
            FakeOutcome.IMPROVE: 2 * baseline.min_delta * sign,
            FakeOutcome.REGRESS: -2 * baseline.regression_delta * sign,
            FakeOutcome.INCONCLUSIVE: 0.0,
        }[outcome]
        return ExperimentResult(status=ExperimentStatus.SUCCEEDED, value=baseline.value + change)


def fake_services(simulation: SimulationConfig) -> ResearchServices:
    """Build the default offline service bundle from persisted scenario settings."""
    return ResearchServices(
        FakeLiteratureProvider(),
        FakeEvidenceExtractor(),
        FakeHypothesisGenerator(),
        FakeExperimentRunner(simulation),
    )
