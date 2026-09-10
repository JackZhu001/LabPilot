"""Semantic Scholar Graph API search adapter."""

import os
from collections.abc import Mapping
from datetime import date

import httpx

from labpilot.literature.providers import LiteratureProviderError
from labpilot.models.literature import PaperCandidate


class SemanticScholarProvider:
    name = "semantic_scholar"

    def __init__(
        self, *, env: Mapping[str, str] | None = None, timeout_seconds: float = 20
    ) -> None:
        values = os.environ if env is None else env
        self.api_key = values.get("SEMANTIC_SCHOLAR_API_KEY")
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, max_results: int) -> tuple[PaperCandidate, ...]:
        headers = {"User-Agent": "LabPilot/0.1 literature-grounding"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        try:
            with httpx.Client(trust_env=False) as client:
                response = client.get(
                    "https://api.semanticscholar.org/graph/v1/paper/search",
                    params={
                        "query": query,
                        "limit": max_results,
                        "fields": (
                            "paperId,title,authors,abstract,publicationDate,url,externalIds,venue"
                        ),
                    },
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            response.raise_for_status()
            payload = response.json()
            records = payload["data"]
            if not isinstance(records, list):
                raise ValueError("data is not a list")
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise LiteratureProviderError(
                f"Semantic Scholar search failed: {type(exc).__name__}"
            ) from exc
        papers: list[PaperCandidate] = []
        try:
            for item in records:
                external = item.get("externalIds") or {}
                title = item.get("title")
                if not title:
                    continue
                papers.append(
                    PaperCandidate(
                        title=title,
                        authors=tuple(
                            a["name"] for a in item.get("authors") or [] if a.get("name")
                        ),
                        abstract=item.get("abstract"),
                        published_at=date.fromisoformat(item["publicationDate"])
                        if item.get("publicationDate")
                        else None,
                        url=item.get("url"),
                        doi=external.get("DOI"),
                        arxiv_id=external.get("ArXiv"),
                        external_id=item.get("paperId"),
                        provider=self.name,
                        venue=item.get("venue"),
                    )
                )
        except (TypeError, ValueError, KeyError) as exc:
            raise LiteratureProviderError("Semantic Scholar returned malformed metadata") from exc
        return tuple(papers)
