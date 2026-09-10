"""Provider boundary and normalized retrieval errors."""

from typing import Protocol

from labpilot.models.literature import PaperCandidate


class LiteratureProviderError(RuntimeError):
    pass


class LiteratureProvider(Protocol):
    name: str

    def search(self, query: str, max_results: int) -> tuple[PaperCandidate, ...]: ...
