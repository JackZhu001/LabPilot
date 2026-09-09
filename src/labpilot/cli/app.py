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

from labpilot.execution.git import GitError
from labpilot.graph.workflow import execute
from labpilot.models.budget import ResearchBudget
from labpilot.models.common import FakeOutcome
from labpilot.models.execution import ExecutionConfig, ExecutionEnvironment
from labpilot.models.experiments import Baseline
from labpilot.models.state import ResearchState, SimulationConfig
from labpilot.persistence.repository import (
    RunNotFoundError,
    SQLiteResearchRepository,
    StateConflictError,
)
from labpilot.services.real import configure_docker, prepare_example

app = typer.Typer(
    no_args_is_help=True, help="LabPilot research state machine with fake and Docker execution."
)
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
    except (
        RunNotFoundError,
        StateConflictError,
        ValidationError,
        SQLAlchemyError,
        OSError,
        GitError,
    ) as exc:
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
    typer.echo(f"Executor: {state.execution.environment.value}")
    if state.execution.environment == ExecutionEnvironment.FAKE:
        typer.echo("Mode: simulated (no real training or literature retrieval)")
    else:
        baseline_value = state.baseline.value if state.baseline_experiment_id else "pending"
        typer.echo(f"Baseline metric: {baseline_value}")
        current = state.experiments[-1] if state.experiments else None
        if current and current.result:
            typer.echo(f"Current metric: {current.result.value}")
            if current.result.execution:
                detail = current.result.execution
                typer.echo(f"Runtime: {detail.runtime_seconds:.3f}s")
                typer.echo(f"Provenance: {detail.artifacts.provenance_path}")
                for error in detail.cleanup_errors:
                    typer.echo(f"Cleanup warning: {error}")


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
    executor: Annotated[ExecutionEnvironment, typer.Option()] = ExecutionEnvironment.FAKE,
    repo: Annotated[Path | None, typer.Option(help="Clean dedicated baseline repository.")] = None,
    patch: Annotated[
        Path | None, typer.Option(help="Unified diff; default is predefined dropout patch.")
    ] = None,
    runtime_root: Annotated[Path, typer.Option()] = Path(".labpilot"),
    image: Annotated[str, typer.Option()] = "labpilot-mnist:phase2",
    build_image: Annotated[bool, typer.Option("--build-image/--reuse-image")] = True,
    timeout: Annotated[float, typer.Option(min=0.01)] = 180,
    min_delta: Annotated[float, typer.Option(min=0.000000001)] = 0.01,
) -> None:
    """Create and execute a research run; optionally pause at a checkpoint."""
    try:
        scenario = SimulationConfig(
            outcomes=tuple(FakeOutcome(x.strip()) for x in outcomes.split(","))
        )
    except ValueError as exc:
        raise typer.BadParameter(
            "Use improve, regress, inconclusive, or fail", param_hint="--outcomes"
        ) from exc
    if executor == ExecutionEnvironment.DOCKER and repo is None:
        raise typer.BadParameter("--repo is required for Docker execution")
    if repo is not None and executor != ExecutionEnvironment.DOCKER:
        raise typer.BadParameter("--repo requires --executor docker")
    with repository_at(db) as repository:
        execution = (
            configure_docker(
                repo,
                runtime_root,
                patch=patch,
                image=image,
                build_image=build_image,
                timeout_seconds=timeout,
            )
            if repo
            else None
        )
        state = repository.create(
            ResearchState(
                research_goal=goal,
                simulation=scenario,
                baseline=Baseline(min_delta=min_delta),
                execution=execution or ExecutionConfig(),
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


@app.command("prepare-example")
def prepare_example_command(
    destination: Annotated[Path, typer.Argument(help="New dedicated baseline Git repository.")],
    source: Annotated[Path, typer.Option()] = Path("examples/mnist_baseline"),
) -> None:
    """Copy the MNIST example into a new committed baseline repository."""
    try:
        typer.echo(f"Baseline repository: {prepare_example(source, destination)}")
    except (OSError, ValueError, GitError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
