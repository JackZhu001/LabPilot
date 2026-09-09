from uuid import uuid4

import pytest

from labpilot.models.common import RunStatus
from labpilot.models.state import ResearchState
from labpilot.persistence.repository import (
    RunNotFoundError,
    SQLiteResearchRepository,
    StateConflictError,
)


def test_create_load_update_list(repository: SQLiteResearchRepository) -> None:
    initial = repository.create(ResearchState(research_goal="Goal"))
    assert repository.load(initial.research_id) == initial
    updated = repository.save(initial.evolve(status=RunStatus.PAUSED))
    assert updated.revision == 1
    assert repository.load(initial.research_id) == updated
    (metadata,) = repository.list_runs()
    assert metadata.research_id == initial.research_id
    assert metadata.status == RunStatus.PAUSED
    assert metadata.updated_at == updated.updated_at


def test_duplicate_create(repository: SQLiteResearchRepository) -> None:
    initial = repository.create(ResearchState(research_goal="Goal"))
    with pytest.raises(StateConflictError, match="already exists"):
        repository.create(initial)
    assert repository.load(initial.research_id) == initial


def test_stale_update_rejected(repository: SQLiteResearchRepository) -> None:
    initial = repository.create(ResearchState(research_goal="Goal"))
    updated = repository.save(initial.evolve(status=RunStatus.PAUSED))
    with pytest.raises(StateConflictError, match="another writer"):
        repository.save(initial.evolve(research_goal="Stale update"))
    assert repository.load(initial.research_id) == updated


def test_missing_run(repository: SQLiteResearchRepository) -> None:
    with pytest.raises(RunNotFoundError):
        repository.load(uuid4())
    with pytest.raises(RunNotFoundError):
        repository.save(ResearchState(research_goal="Missing"))
