"""Atomic best-effort cache for normalized provider responses."""

import hashlib
import json
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from labpilot.models.literature import PaperCandidate

PAPERS = TypeAdapter(tuple[PaperCandidate, ...])


def normalize_query(query: str) -> str:
    return " ".join(query.lower().split())


class LiteratureCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, provider: str, query: str, max_results: int) -> Path:
        payload = json.dumps(
            {"provider": provider, "query": normalize_query(query), "max_results": max_results},
            sort_keys=True,
            separators=(",", ":"),
        )
        return self.root / f"{hashlib.sha256(payload.encode()).hexdigest()}.json"

    def get(self, provider: str, query: str, max_results: int) -> tuple[PaperCandidate, ...] | None:
        path = self._path(provider, query, max_results)
        if not path.exists():
            return None
        try:
            return PAPERS.validate_json(path.read_text())
        except (OSError, ValidationError):
            return None

    def put(
        self, provider: str, query: str, max_results: int, papers: tuple[PaperCandidate, ...]
    ) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(provider, query, max_results)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(PAPERS.dump_json(papers, indent=2).decode())
        temporary.replace(path)
