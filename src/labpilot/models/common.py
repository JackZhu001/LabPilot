"""Shared validation and explicit workflow vocabulary."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Confidence = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
NonNegative = Annotated[int, Field(ge=0, strict=True)]
Text = Annotated[str, Field(min_length=1)]


def utc_now() -> datetime:
    return datetime.now(UTC)


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class ResearchDecision(StrEnum):
    KEEP = "KEEP"
    REJECT = "REJECT"
    REPLAN = "REPLAN"


class EvidenceRelation(StrEnum):
    SUPPORT = "SUPPORT"
    CONTRADICT = "CONTRADICT"
    NEUTRAL = "NEUTRAL"


class ExperimentStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class HypothesisStatus(StrEnum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    REPLANNED = "REPLANNED"


class EvidenceSource(StrEnum):
    FIXTURE = "FIXTURE"
    REPOSITORY_AND_EXPERIMENT_HISTORY = "REPOSITORY_AND_EXPERIMENT_HISTORY"
    SCIENTIFIC_LITERATURE = "SCIENTIFIC_LITERATURE"


class GroundingStatus(StrEnum):
    LITERATURE_GROUNDED = "LITERATURE_GROUNDED"
    PARTIALLY_GROUNDED = "PARTIALLY_GROUNDED"
    REPOSITORY_ONLY = "REPOSITORY_ONLY"


class SourceScope(StrEnum):
    ABSTRACT = "ABSTRACT"


class ChangeType(StrEnum):
    CONFIG_ONLY = "CONFIG_ONLY"
    CODE_CHANGE = "CODE_CHANGE"
    CODE_CHANGE_WITH_HPO = "CODE_CHANGE_WITH_HPO"


class MetricDirection(StrEnum):
    MAXIMIZE = "MAXIMIZE"
    MINIMIZE = "MINIMIZE"


class RunStatus(StrEnum):
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class Step(StrEnum):
    INSPECT_REPOSITORY = "inspect_repository"
    PLAN_LITERATURE_QUERIES = "plan_literature_queries"
    RETRIEVE_PAPERS = "retrieve_papers"
    EXTRACT_CLAIMS = "extract_claims"
    SYNTHESIZE_EVIDENCE = "synthesize_evidence"
    GENERATE_HYPOTHESES = "generate_hypotheses"
    PLAN_EXPERIMENT = "plan_experiment"
    GENERATE_PATCH = "generate_patch"
    CRITIQUE = "critique"
    LITERATURE = "literature"
    EVIDENCE = "evidence"
    BASELINE = "baseline"
    HYPOTHESIS = "hypothesis"
    EXPERIMENT = "experiment"
    HPO_PLAN = "hpo_plan"
    HPO_SUGGEST = "hpo_suggest"
    HPO_EXECUTE = "hpo_execute"
    HPO_SYNC = "hpo_sync"
    ANALYZE = "analyze"
    DECISION = "decision"
    END = "end"


class FakeOutcome(StrEnum):
    IMPROVE = "improve"
    REGRESS = "regress"
    INCONCLUSIVE = "inconclusive"
    FAIL = "fail"
