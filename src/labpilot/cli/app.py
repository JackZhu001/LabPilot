"""CLI adapters for local, simulated research runs."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from labpilot.graph.workflow import execute
from labpilot.models.budget import ResearchBudget
from labpilot.models.common import FakeOutcome
from labpilot.models.state import ResearchState, SimulationConfig
from labpilot.persistence.repository import (
    RunNotFoundError,
    SQLiteResearchRepository,
    StateConflictError,
)

app = typer.Typer(no_args_is_help=True, help="LabPilot Phase 1: offline research state machine.")
DatabaseOption = Annotated[Path, typer.Option("--db", help="SQLite database file.")]
StopOption = Annotated[
    int | None, typer.Option(min=1, help="Pause after N committed workflow steps.")
]
DEFAULT_DB = Path(".labpilot/labpilot.sqlite3")


@contextmanager
def repository_at(path: Path) -> Iterator[SQLiteResearchRepository]:
    repository: SQLiteResearchRepository | None = None
    try:
        repository = SQLiteResearchRepository(path)
        yield repository
    except (RunNotFoundError, StateConflictError, ValidationError, SQLAlchemyError, OSError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    finally:
        if repository is not None:
            repository.close()


def print_summary(state: ResearchState) -> None:
    typer.echo(f"Research ID: {state.research_id}")
    typer.echo(f"Goal: {state.research_goal}")
    typer.echo(f"Status: {state.status.value}")
    typer.echo(f"Decision: {state.decision.value if state.decision else 'NONE'}")
    typer.echo(f"Iteration: {state.iteration}/{state.budget.max_iterations}")
    typer.echo(f"Experiments: {state.budget.experiments}/{state.budget.max_experiments}")
    typer.echo(f"Failures: {state.budget.failed_experiments}/{state.budget.max_failed_experiments}")
    typer.echo(f"Replans: {state.budget.replans}/{state.budget.max_replans}")
    typer.echo(f"Next step: {state.next_step.value}")
    typer.echo(f"Revision: {state.revision}")
    typer.echo(f"Summary: {state.termination_reason or 'Checkpoint saved; resume to continue.'}")
    typer.echo("Mode: simulated (no real training or literature retrieval)")


@app.callback()
def main(
    verbose: Annotated[bool, typer.Option("--verbose", help="Show workflow logs.")] = False,
) -> None:
    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING, format="%(message)s")


@app.command()
def init(db: DatabaseOption = DEFAULT_DB) -> None:
    """Initialize local SQLite storage (safe to repeat)."""
    with repository_at(db):
        typer.echo(f"Initialized: {db}")


@app.command()
def run(
    goal: Annotated[str, typer.Option(help="Research question to explore.")],
    db: DatabaseOption = DEFAULT_DB,
    stop_after: StopOption = None,
    outcomes: Annotated[
        str, typer.Option(help="Comma-separated fake outcomes; last repeats.")
    ] = "improve",
    max_iterations: Annotated[int, typer.Option(min=0)] = 3,
    max_experiments: Annotated[int, typer.Option(min=0)] = 3,
    max_failed_experiments: Annotated[int, typer.Option(min=0)] = 2,
    max_replans: Annotated[int, typer.Option(min=0)] = 2,
) -> None:
    """Create and execute a fake research run; optionally pause at a checkpoint."""
    try:
        scenario = SimulationConfig(
            outcomes=tuple(FakeOutcome(x.strip()) for x in outcomes.split(","))
        )
    except ValueError as exc:
        raise typer.BadParameter(
            "Use improve, regress, inconclusive, or fail", param_hint="--outcomes"
        ) from exc
    with repository_at(db) as repository:
        state = repository.create(
            ResearchState(
                research_goal=goal,
                simulation=scenario,
                budget=ResearchBudget(
                    max_iterations=max_iterations,
                    max_experiments=max_experiments,
                    max_failed_experiments=max_failed_experiments,
                    max_replans=max_replans,
                ),
            )
        )
        print_summary(execute(repository, state.research_id, stop_after=stop_after))


@app.command()
def status(
    research_id: UUID,
    db: DatabaseOption = DEFAULT_DB,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print the complete validated snapshot.")
    ] = False,
) -> None:
    """Inspect a persisted research run."""
    with repository_at(db) as repository:
        state = repository.load(research_id)
        if as_json:
            typer.echo(state.model_dump_json(indent=2))
        else:
            print_summary(state)


@app.command()
def resume(
    research_id: UUID, db: DatabaseOption = DEFAULT_DB, stop_after: StopOption = None
) -> None:
    """Continue from the next durable step; completed runs are unchanged."""
    with repository_at(db) as repository:
        print_summary(execute(repository, research_id, stop_after=stop_after))


@app.command()
def runs(db: DatabaseOption = DEFAULT_DB) -> None:
    """List saved run metadata."""
    with repository_at(db) as repository:
        for run in repository.list_runs():
            typer.echo(
                f"{run.research_id}  {run.status.value}  {run.decision or '-'}  {run.research_goal}"
            )
