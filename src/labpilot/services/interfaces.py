"""Injection boundaries for future integrations; no external implementations yet."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from labpilot.literature.providers import LiteratureProvider as SearchLiteratureProvider
from labpilot.llm.client import LLMClient
from labpilot.models.experiments import Baseline, Experiment, ExperimentResult
from labpilot.models.literature import Claim, Evidence, Hypothesis, Paper


class LiteratureProvider(Protocol):
    def retrieve(self, research_id: UUID, goal: str) -> tuple[Paper, ...]: ...


class EvidenceExtractor(Protocol):
    def extract(
        self, papers: tuple[Paper, ...]
    ) -> tuple[tuple[Claim, ...], tuple[Evidence, ...]]: ...


class HypothesisGenerator(Protocol):
    def generate(
        self, research_id: UUID, goal: str, evidence: tuple[Evidence, ...], iteration: int
    ) -> Hypothesis: ...


class ExperimentRunner(Protocol):
    def run(self, experiment: Experiment, baseline: Baseline) -> ExperimentResult: ...


@dataclass(frozen=True)
class ResearchServices:
    """Service dependencies shared by research transitions."""

    literature: LiteratureProvider
    evidence: EvidenceExtractor
    hypothesis: HypothesisGenerator
    experiment: ExperimentRunner
    llm: LLMClient | None = None
    literature_providers: tuple[SearchLiteratureProvider, ...] = ()
