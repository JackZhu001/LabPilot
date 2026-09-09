"""Source → claim → evidence → hypothesis provenance."""

from datetime import date
from uuid import UUID, uuid4

from pydantic import Field, HttpUrl

from labpilot.models.common import (
    Confidence,
    DomainModel,
    EvidenceRelation,
    HypothesisStatus,
    Text,
)


class Paper(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    title: Text
    authors: tuple[Text, ...] = Field(min_length=1)
    abstract: Text
    url: HttpUrl | None = None
    published_at: date | None = None
    external_id: Text | None = None
    source_provider: Text


class Claim(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    statement: Text
    confidence: Confidence


class Evidence(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    claim_id: UUID
    relation: EvidenceRelation
    summary: Text
    confidence: Confidence


class Hypothesis(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    statement: Text
    motivation: Text
    evidence_ids: tuple[UUID, ...] = Field(min_length=1)
    expected_effect: Text
    confidence: Confidence
    estimated_cost: float = Field(ge=0, allow_inf_nan=False)
    falsification_criteria: Text
    status: HypothesisStatus = HypothesisStatus.PROPOSED
