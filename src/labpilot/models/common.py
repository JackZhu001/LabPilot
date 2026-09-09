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


class MetricDirection(StrEnum):
    MAXIMIZE = "MAXIMIZE"
    MINIMIZE = "MINIMIZE"


class RunStatus(StrEnum):
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"


class Step(StrEnum):
    LITERATURE = "literature"
    EVIDENCE = "evidence"
    HYPOTHESIS = "hypothesis"
    EXPERIMENT = "experiment"
    ANALYZE = "analyze"
    DECISION = "decision"
    END = "end"


class FakeOutcome(StrEnum):
    IMPROVE = "improve"
    REGRESS = "regress"
    INCONCLUSIVE = "inconclusive"
    FAIL = "fail"
