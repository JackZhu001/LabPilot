"""Minimal arXiv Atom API adapter; abstracts and metadata only."""

from datetime import datetime
from xml.etree import ElementTree

import httpx
from pydantic import HttpUrl, ValidationError

from labpilot.literature.providers import LiteratureProviderError
from labpilot.models.literature import PaperCandidate

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"


def _text(node: ElementTree.Element, name: str) -> str | None:
    child = node.find(f"{ATOM}{name}")
    if child is None or child.text is None:
        return None
    return " ".join(child.text.split()) or None


class ArxivProvider:
    name = "arxiv"

    def __init__(self, *, timeout_seconds: float = 20) -> None:
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, max_results: int) -> tuple[PaperCandidate, ...]:
        try:
            with httpx.Client(trust_env=False) as client:
                response = client.get(
                    "https://export.arxiv.org/api/query",
                    params={
                        "search_query": f"all:{query}",
                        "start": 0,
                        "max_results": max_results,
                    },
                    timeout=self.timeout_seconds,
                    headers={"User-Agent": "LabPilot/0.1 literature-grounding"},
                )
            response.raise_for_status()
            root = ElementTree.fromstring(response.content)
        except (httpx.HTTPError, ElementTree.ParseError) as exc:
            raise LiteratureProviderError(f"arXiv search failed: {type(exc).__name__}") from exc
        papers: list[PaperCandidate] = []
        for entry in root.findall(f"{ATOM}entry"):
            try:
                title, abstract, identifier = (
                    _text(entry, "title"),
                    _text(entry, "summary"),
                    _text(entry, "id"),
                )
                if not title:
                    continue
                arxiv_id = identifier.rstrip("/").rsplit("/", 1)[-1] if identifier else None
                published = _text(entry, "published")
                doi_node = entry.find(f"{ARXIV}doi")
                doi = doi_node.text.strip() if doi_node is not None and doi_node.text else None
                papers.append(
                    PaperCandidate(
                        title=title,
                        authors=tuple(
                            value
                            for author in entry.findall(f"{ATOM}author")
                            if (value := _text(author, "name"))
                        ),
                        abstract=abstract,
                        published_at=datetime.fromisoformat(published.replace("Z", "+00:00")).date()
                        if published
                        else None,
                        url=HttpUrl(identifier) if identifier else None,
                        doi=doi,
                        arxiv_id=arxiv_id,
                        external_id=arxiv_id,
                        provider=self.name,
                    )
                )
            except (ValueError, ValidationError):
                continue
        return tuple(papers)
