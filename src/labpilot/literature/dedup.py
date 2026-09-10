"""Conservative deterministic cross-provider paper deduplication."""

import re
from collections.abc import Iterable

from labpilot.models.literature import PaperCandidate, ProviderReference


def normalize_identifier(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower().removeprefix("https://doi.org/").removeprefix("doi:")


def normalize_title(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def identity_keys(paper: PaperCandidate) -> tuple[str, ...]:
    keys: list[str] = []
    if doi := normalize_identifier(paper.doi):
        keys.append(f"doi:{doi}")
    if arxiv := normalize_identifier(paper.arxiv_id):
        keys.append(f"arxiv:{re.sub(r'v[0-9]+$', '', arxiv)}")
    if external := normalize_identifier(paper.external_id):
        keys.append(f"external:{paper.provider.lower()}:{external}")
    keys.append(f"title:{normalize_title(paper.title)}")
    return tuple(keys)


def deduplicate_papers(
    candidates: Iterable[PaperCandidate],
) -> tuple[tuple[PaperCandidate, tuple[ProviderReference, ...]], ...]:
    accepted: list[PaperCandidate] = []
    references: list[list[ProviderReference]] = []
    indexes: dict[str, int] = {}
    for candidate in candidates:
        keys = identity_keys(candidate)
        matches = {indexes[key] for key in keys if key in indexes}
        reference = ProviderReference(
            provider=candidate.provider,
            external_id=candidate.external_id,
            url=candidate.url,
        )
        if matches:
            index = min(matches)
            if reference not in references[index]:
                references[index].append(reference)
            for key in keys:
                indexes[key] = index
            continue
        index = len(accepted)
        accepted.append(candidate)
        references.append([reference])
        for key in keys:
            indexes[key] = index
    return tuple((paper, tuple(refs)) for paper, refs in zip(accepted, references, strict=True))
