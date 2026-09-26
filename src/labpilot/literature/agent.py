"""Checkpoint-sized LLM roles for query planning, claims, and evidence synthesis."""

from uuid import UUID, uuid5

from labpilot.agent.service import AgentLoopService, compact_json
from labpilot.literature.service import LiteratureRetrievalService
from labpilot.models.common import SourceScope, Step
from labpilot.models.literature import (
    Claim,
    ClaimBatch,
    Evidence,
    EvidenceClassificationDraft,
    EvidenceSynthesis,
    EvidenceSynthesisDraft,
    LiteratureQuery,
    LiteratureQueryPlan,
    LiteratureQueryPlanDraft,
)
from labpilot.models.state import ResearchState
from labpilot.services.interfaces import ResearchServices


class EvidenceClassifier:
    """Classify one validated claim against a candidate hypothesis."""

    def __init__(self, services: ResearchServices) -> None:
        if services.llm is None:
            raise ValueError("Evidence classification requires an LLM service")
        self.agent = AgentLoopService(services.llm)

    def classify(
        self,
        state: ResearchState,
        *,
        claim: Claim,
        candidate_hypothesis: str,
        target_hypothesis_id: UUID | None = None,
    ) -> tuple[Evidence, ResearchState]:
        prompt = (
            f"Research goal: {state.research_goal}\n"
            f"Candidate hypothesis: {candidate_hypothesis}\n"
            f"Validated claim: {compact_json(claim)}"
        )
        result, state = self.agent._invoke(
            state,
            operation="evidence_classification",
            template="evidence_classification",
            user_prompt=prompt,
            response_model=EvidenceClassificationDraft,
        )
        return (
            Evidence(
                id=uuid5(claim.id, f"evidence:{target_hypothesis_id or 'candidate'}"),
                claim_id=claim.id,
                paper_id=claim.paper_id,
                target_hypothesis_id=target_hypothesis_id,
                source_span=claim.source_span,
                **result.output.model_dump(),
            ),
            state,
        )


class LiteratureAgentService:
    def __init__(self, services: ResearchServices) -> None:
        if services.llm is None:
            raise ValueError("Literature grounding requires an LLM service")
        self.services = services
        self.agent = AgentLoopService(services.llm)

    def plan_queries(self, state: ResearchState) -> ResearchState:
        if state.repository_inspection is None:
            raise ValueError("Literature planning requires repository inspection")
        limit = state.budget.max_literature_queries - state.budget.literature_queries
        if limit <= 0:
            return state.evolve(next_step=Step.RETRIEVE_PAPERS)
        prompt = (
            f"Research goal: {state.research_goal}\n"
            f"Maximum queries: {min(3, limit)}\n"
            f"Repository inspection: {compact_json(state.repository_inspection)}\n"
            f"Previous experiment history: {compact_json(self.agent._history(state))}"
        )
        result, state = self.agent._invoke(
            state,
            operation="literature_query_planning",
            template="literature_query_planning",
            user_prompt=prompt,
            response_model=LiteratureQueryPlanDraft,
        )
        drafts = result.output.queries[:limit]
        plan = LiteratureQueryPlan(
            queries=tuple(
                LiteratureQuery(
                    id=uuid5(state.research_id, f"literature-query:{index}"),
                    **draft.model_dump(),
                )
                for index, draft in enumerate(drafts)
            )
        )
        return state.evolve(
            literature_query_plan=plan,
            budget=state.budget.consume(literature_queries=len(plan.queries)),
            next_step=Step.RETRIEVE_PAPERS,
        )

    def retrieve_papers(self, state: ResearchState) -> ResearchState:
        if state.literature_query_plan is None:
            return state.evolve(next_step=Step.EXTRACT_CLAIMS)
        remaining = state.budget.max_papers - state.budget.papers
        service = LiteratureRetrievalService(
            self.services.literature_providers,
            state.execution.runtime_root / "literature-cache",
        )
        retrieved, failures = service.retrieve(
            state.research_id, state.literature_query_plan, max(0, remaining)
        )
        papers = (*state.papers, *retrieved)
        return state.evolve(
            papers=papers,
            literature_failures=failures,
            budget=state.budget.consume(papers=len(retrieved)),
            next_step=Step.EXTRACT_CLAIMS,
        )

    def extract_claims(self, state: ResearchState) -> ResearchState:
        index = state.claim_extraction_index
        if index >= len(state.papers) or state.budget.claims >= state.budget.max_claims:
            return state.evolve(next_step=Step.SYNTHESIZE_EVIDENCE)
        paper = state.papers[index]
        source_text = paper.full_text_excerpt or paper.abstract
        if not source_text:
            return state.evolve(claim_extraction_index=index + 1, next_step=Step.EXTRACT_CLAIMS)
        remaining = state.budget.max_claims - state.budget.claims
        limit = min(state.literature_settings.max_claims_per_paper, remaining)
        prompt = (
            f"Research goal: {state.research_goal}\nMaximum relevant claims: {limit}\n"
            "Paper metadata: "
            f"{compact_json(paper.model_dump(mode='json', exclude={'full_text_excerpt'}))}\n"
            f"Available source text (choose exact source spans and label its scope): {source_text}"
        )
        result, state = self.agent._invoke(
            state,
            operation="claim_extraction",
            template="claim_extraction",
            user_prompt=prompt,
            response_model=ClaimBatch,
        )
        claims: list[Claim] = []
        expected_scope = (
            SourceScope.PAPER_EXCERPT if paper.full_text_excerpt else SourceScope.ABSTRACT
        )
        normalized_source = " ".join(source_text.split()).casefold()
        for offset, draft in enumerate(result.output.claims[:limit]):
            if draft.source_scope != expected_scope or (
                " ".join(draft.source_span.split()).casefold() not in normalized_source
            ):
                continue
            claims.append(
                Claim(
                    id=uuid5(paper.id, f"claim:{offset}"),
                    paper_id=paper.id,
                    **draft.model_dump(),
                )
            )
        return state.evolve(
            claims=(*state.claims, *claims),
            claim_extraction_index=index + 1,
            budget=state.budget.consume(claims=len(claims)),
            next_step=Step.EXTRACT_CLAIMS,
        )

    def synthesize_evidence(self, state: ResearchState) -> ResearchState:
        if not state.claims:
            return state.evolve(evidence_synthesis=EvidenceSynthesis(), next_step=Step.BASELINE)
        prompt = (
            f"Research goal: {state.research_goal}\n"
            f"Repository inspection: {compact_json(state.repository_inspection)}\n"
            f"Validated claims: {compact_json(state.claims)}"
        )
        result, state = self.agent._invoke(
            state,
            operation="evidence_synthesis",
            template="evidence_synthesis",
            user_prompt=prompt,
            response_model=EvidenceSynthesisDraft,
        )
        claims = {claim.id: claim for claim in state.claims}
        evidence: list[Evidence] = []
        seen: set[object] = set()
        for draft in result.output.evidence:
            claim = claims.get(draft.claim_id)
            if claim is None or claim.id in seen:
                continue
            seen.add(claim.id)
            evidence.append(
                Evidence(
                    id=uuid5(claim.id, "evidence:0"),
                    paper_id=claim.paper_id,
                    source_span=claim.source_span,
                    **draft.model_dump(),
                )
            )
        synthesis = EvidenceSynthesis.model_validate(result.output.model_dump(exclude={"evidence"}))
        return state.evolve(
            evidence=tuple(evidence),
            evidence_synthesis=synthesis,
            next_step=Step.BASELINE,
        )
