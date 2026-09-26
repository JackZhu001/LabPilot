"""Typed scientific provenance from provider result to selected hypothesis."""

from datetime import date
from typing import Annotated, Literal, Self
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field, HttpUrl, model_validator

from labpilot.models.common import (
    ChangeType,
    Confidence,
    DomainModel,
    EvidenceRelation,
    EvidenceSource,
    GroundingStatus,
    HypothesisStatus,
    SourceScope,
    Text,
)


class LiteratureSettings(DomainModel):
    enabled: bool = False
    providers: tuple[Literal["arxiv", "semantic_scholar"], ...] = (
        "arxiv",
        "semantic_scholar",
    )
    max_claims_per_paper: int = Field(default=3, ge=1, le=3)


class LiteratureQueryDraft(DomainModel):
    query: Text
    motivation: Text
    target_concepts: tuple[Text, ...] = Field(min_length=1, max_length=8)
    max_results: int = Field(default=3, ge=1, le=10)


class LiteratureQueryPlanDraft(DomainModel):
    queries: tuple[LiteratureQueryDraft, ...] = Field(min_length=1, max_length=3)


class LiteratureQuery(LiteratureQueryDraft):
    id: UUID = Field(default_factory=uuid4)


class LiteratureQueryPlan(DomainModel):
    queries: tuple[LiteratureQuery, ...] = Field(min_length=1, max_length=3)


class ProviderReference(DomainModel):
    provider: Text
    external_id: Text | None = None
    url: HttpUrl | None = None


class PaperCandidate(DomainModel):
    title: Text
    authors: tuple[Text, ...] = ()
    abstract: Text | None = None
    published_at: date | None = None
    url: HttpUrl | None = None
    doi: Text | None = None
    arxiv_id: Text | None = None
    external_id: Text | None = None
    provider: Text
    venue: Text | None = None


class Paper(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    title: Text
    authors: tuple[Text, ...] = ()
    abstract: Text | None = None
    url: HttpUrl | None = None
    published_at: date | None = None
    doi: Text | None = None
    arxiv_id: Text | None = None
    external_id: Text | None = None
    source_provider: Text
    venue: Text | None = None
    retrieved_at: AwareDatetime | None = None
    query_id: UUID | None = None
    provider_references: tuple[ProviderReference, ...] = ()


class ClaimDraft(DomainModel):
    statement: Text
    claim_type: Text | None = None
    confidence: Confidence
    source_span: Text
    source_scope: Literal[SourceScope.ABSTRACT] = SourceScope.ABSTRACT


class ClaimBatch(DomainModel):
    claims: tuple[ClaimDraft, ...] = Field(max_length=3)


class Claim(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    paper_id: UUID
    statement: Text
    claim_type: Text | None = None
    confidence: Confidence
    source_span: Text | None = None
    source_scope: SourceScope | None = None


class EvidenceDraft(DomainModel):
    claim_id: UUID
    relation: EvidenceRelation
    summary: Text
    confidence: Confidence
    applicability_notes: Text | None = None


class EvidenceClassificationDraft(DomainModel):
    relation: EvidenceRelation
    summary: Text
    confidence: Confidence
    applicability_notes: Text | None = None


class EvidenceSynthesisDraft(DomainModel):
    consistent_findings: tuple[Text, ...] = Field(max_length=8)
    conflicting_findings: tuple[Text, ...] = Field(max_length=8)
    gaps: tuple[Text, ...] = Field(max_length=8)
    evidence: tuple[EvidenceDraft, ...]


class EvidenceSynthesis(DomainModel):
    consistent_findings: tuple[Text, ...] = ()
    conflicting_findings: tuple[Text, ...] = ()
    gaps: tuple[Text, ...] = ()


class Evidence(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    claim_id: UUID
    paper_id: UUID | None = None
    relation: EvidenceRelation
    target_hypothesis_id: UUID | None = None
    summary: Text
    confidence: Confidence
    source_span: Text | None = None
    applicability_notes: Text | None = None


class GroundedHypothesisProposal(DomainModel):
    statement: Text
    motivation: Text
    supporting_evidence_ids: tuple[UUID, ...] = ()
    contradicting_evidence_ids: tuple[UUID, ...] = ()
    neutral_evidence_ids: tuple[UUID, ...] = ()
    evidence_confidence: Confidence
    expected_effect: Text
    expected_impact: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
    confidence: Confidence
    estimated_cost: float = Field(ge=0, allow_inf_nan=False)
    falsification_criteria: Text
    change_type: ChangeType

    @model_validator(mode="after")
    def unique_links(self) -> Self:
        links = (
            *self.supporting_evidence_ids,
            *self.contradicting_evidence_ids,
            *self.neutral_evidence_ids,
        )
        if not links:
            raise ValueError("A grounded hypothesis must reference at least one evidence item")
        if len(links) != len(set(links)):
            raise ValueError("An evidence item may have only one relation per hypothesis")
        return self


class GroundedHypothesisBatch(DomainModel):
    proposals: tuple[GroundedHypothesisProposal, ...] = Field(min_length=1, max_length=3)


class Hypothesis(DomainModel):
    id: UUID = Field(default_factory=uuid4)
    statement: Text
    motivation: Text
    evidence_ids: tuple[UUID, ...] = ()
    supporting_evidence_ids: tuple[UUID, ...] = ()
    contradicting_evidence_ids: tuple[UUID, ...] = ()
    neutral_evidence_ids: tuple[UUID, ...] = ()
    evidence_confidence: Confidence = 0
    grounding_status: GroundingStatus = GroundingStatus.REPOSITORY_ONLY
    evidence_source: EvidenceSource = EvidenceSource.FIXTURE
    change_type: ChangeType = ChangeType.CODE_CHANGE
    expected_effect: Text
    confidence: Confidence
    estimated_cost: float = Field(ge=0, allow_inf_nan=False)
    falsification_criteria: Text
    status: HypothesisStatus = HypothesisStatus.PROPOSED

    @model_validator(mode="after")
    def evidence_union(self) -> Self:
        categorized = {
            *self.supporting_evidence_ids,
            *self.contradicting_evidence_ids,
            *self.neutral_evidence_ids,
        }
        if categorized and categorized != set(self.evidence_ids):
            raise ValueError("Hypothesis evidence_ids must equal categorized evidence links")
        return self
