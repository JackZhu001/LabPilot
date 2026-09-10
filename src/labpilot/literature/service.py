"""Provider orchestration with cache, failure isolation, and deterministic acceptance."""

from collections.abc import Iterable
from pathlib import Path
from uuid import UUID, uuid5

from labpilot.literature.cache import LiteratureCache
from labpilot.literature.dedup import deduplicate_papers
from labpilot.literature.providers import LiteratureProvider, LiteratureProviderError
from labpilot.models.literature import LiteratureQueryPlan, Paper, PaperCandidate


class LiteratureRetrievalService:
    def __init__(self, providers: Iterable[LiteratureProvider], cache_root: Path) -> None:
        self.providers = tuple(providers)
        self.cache = LiteratureCache(cache_root)

    def retrieve(
        self, research_id: UUID, plan: LiteratureQueryPlan, max_papers: int
    ) -> tuple[tuple[Paper, ...], tuple[str, ...]]:
        candidates: list[tuple[PaperCandidate, UUID]] = []
        failures: list[str] = []
        for query in plan.queries:
            for provider in self.providers:
                cached = self.cache.get(provider.name, query.query, query.max_results)
                if cached is None:
                    try:
                        cached = provider.search(query.query, query.max_results)
                        self.cache.put(provider.name, query.query, query.max_results, cached)
                    except LiteratureProviderError as exc:
                        failures.append(f"{provider.name}: {exc}")
                        continue
                candidates.extend((paper, query.id) for paper in cached)
        query_ids: dict[tuple[str, str], UUID] = {}
        for paper, query_id in candidates:
            query_ids.setdefault((paper.provider, paper.external_id or paper.title), query_id)
        merged = deduplicate_papers(paper for paper, _ in candidates)
        papers: list[Paper] = []
        for index, (candidate, references) in enumerate(merged[:max_papers]):
            selected_query_id = query_ids.get(
                (candidate.provider, candidate.external_id or candidate.title)
            )
            papers.append(
                Paper(
                    id=uuid5(research_id, f"paper:{index}"),
                    source_provider=candidate.provider,
                    query_id=selected_query_id,
                    provider_references=references,
                    **candidate.model_dump(exclude={"provider"}),
                )
            )
        return tuple(papers), tuple(failures)
