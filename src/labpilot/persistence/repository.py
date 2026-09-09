"""Atomic versioned snapshots in SQLite; no separate graph checkpoint store."""

from pathlib import Path
from typing import Protocol
from uuid import UUID

from pydantic import AwareDatetime
from sqlalchemy import JSON, Integer, String, create_engine, select, update
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from labpilot.models.common import DomainModel, ResearchDecision, RunStatus, utc_now
from labpilot.models.state import ResearchState


class RunNotFoundError(LookupError):
    pass


class StateConflictError(RuntimeError):
    """A duplicate create or stale writer cannot overwrite a durable run."""


class RunMetadata(DomainModel):
    research_id: UUID
    research_goal: str
    status: RunStatus
    decision: ResearchDecision | None
    iteration: int
    revision: int
    created_at: AwareDatetime
    updated_at: AwareDatetime


class ResearchRepository(Protocol):
    def create(self, state: ResearchState) -> ResearchState: ...
    def save(self, state: ResearchState) -> ResearchState: ...
    def load(self, research_id: UUID) -> ResearchState: ...
    def list_runs(self) -> tuple[RunMetadata, ...]: ...


class Base(DeclarativeBase):
    pass


class RunRow(Base):
    __tablename__ = "research_runs"

    research_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    research_goal: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    decision: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    iteration: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String, index=True)
    updated_at: Mapped[str] = mapped_column(String, index=True)
    snapshot: Mapped[dict[str, object]] = mapped_column(JSON)


def row_values(state: ResearchState) -> dict[str, object]:
    return {
        "research_id": str(state.research_id),
        "research_goal": state.research_goal,
        "status": state.status.value,
        "decision": state.decision.value if state.decision else None,
        "iteration": state.iteration,
        "revision": state.revision,
        "created_at": state.created_at.isoformat(),
        "updated_at": state.updated_at.isoformat(),
        "snapshot": state.model_dump(mode="json"),
    }


class SQLiteResearchRepository:
    """One JSON snapshot plus queryable metadata, updated in the same transaction.

    Optimistic revisions prevent lost updates. This is not a distributed execution
    lease: simultaneous callers may both run a service before one save is rejected.
    """

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(URL.create("sqlite", database=str(path)))
        Base.metadata.create_all(self.engine)

    def close(self) -> None:
        self.engine.dispose()

    def create(self, state: ResearchState) -> ResearchState:
        state = ResearchState.model_validate(state.model_dump())
        if state.revision != 0:
            raise ValueError("New runs must start at revision zero")
        try:
            with Session(self.engine) as session, session.begin():
                session.add(RunRow(**row_values(state)))
        except IntegrityError as exc:
            raise StateConflictError(f"Run {state.research_id} already exists") from exc
        return state

    def save(self, state: ResearchState) -> ResearchState:
        saved = state.evolve(revision=state.revision + 1, updated_at=utc_now())
        with Session(self.engine) as session, session.begin():
            current = session.get(RunRow, str(state.research_id))
            if current is None:
                raise RunNotFoundError(f"Run {state.research_id} does not exist")
            if current.created_at != state.created_at.isoformat():
                raise StateConflictError("Run creation timestamp is immutable")
            result = session.connection().execute(
                update(RunRow)
                .where(
                    RunRow.research_id == str(state.research_id), RunRow.revision == state.revision
                )
                .values(**row_values(saved))
            )
            if result.rowcount != 1:
                raise StateConflictError(f"Run {state.research_id} was updated by another writer")
        return saved

    def load(self, research_id: UUID) -> ResearchState:
        with Session(self.engine) as session:
            row = session.get(RunRow, str(research_id))
            if row is None:
                raise RunNotFoundError(f"Run {research_id} does not exist")
            return ResearchState.model_validate(row.snapshot)

    def list_runs(self) -> tuple[RunMetadata, ...]:
        # Select only metadata, not the potentially large nested JSON snapshots.
        columns = [getattr(RunRow, name) for name in RunMetadata.model_fields]
        with Session(self.engine) as session:
            rows = session.execute(select(*columns).order_by(RunRow.created_at, RunRow.research_id))
            return tuple(RunMetadata.model_validate(dict(row._mapping)) for row in rows)
