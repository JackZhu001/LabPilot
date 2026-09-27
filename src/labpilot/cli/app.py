"""CLI adapters for local, simulated research runs."""

import hashlib
import json
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4, uuid5

import typer
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient, TypeSafeError

from labpilot.api import serve
from labpilot.execution.git import GitError
from labpilot.graph.workflow import execute
from labpilot.hpo.models import HPOConfig
from labpilot.hpo.optuna import StudyConflictError
from labpilot.hpo.reporting import format_studies
from labpilot.llm.errors import LLMError
from labpilot.llm.models import LLMSettings
from labpilot.models.budget import ResearchBudget
from labpilot.models.common import ChangeType, FakeOutcome, RunStatus, Step
from labpilot.models.execution import ExecutionConfig, ExecutionEnvironment
from labpilot.models.experiments import Baseline
from labpilot.models.literature import LiteratureSettings
from labpilot.models.state import ResearchState, SimulationConfig
from labpilot.persistence.repository import (
    RunNotFoundError,
    SQLiteResearchRepository,
    StateConflictError,
)
from labpilot.reporting import benchmark, benchmark_markdown, report_markdown, research_report
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
        StudyConflictError,
        LLMError,
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
            typer.echo(f"Latest metric: {current.result.value}")
            if current.result.execution:
                detail = current.result.execution
                typer.echo(f"Runtime: {detail.runtime_seconds:.3f}s")
                typer.echo(f"Provenance: {detail.artifacts.provenance_path}")
                for error in detail.cleanup_errors:
                    typer.echo(f"Cleanup warning: {error}")

    if state.studies:
        typer.echo(format_studies(state))
    if state.llm is not None:
        typer.echo(f"LLM: {state.llm.provider}/{state.llm.model}")
        typer.echo(
            f"LLM usage: {state.budget.llm_calls}/{state.budget.max_llm_calls} calls, "
            f"{state.budget.llm_tokens}/{state.budget.max_llm_tokens} tokens"
        )
    if state.literature_settings.enabled:
        typer.echo(
            f"Literature: {state.budget.literature_queries}/"
            f"{state.budget.max_literature_queries} queries, "
            f"{len(state.papers)} papers, {len(state.claims)} claims, "
            f"{len(state.evidence)} evidence records"
        )


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
    max_experiments: Annotated[int | None, typer.Option(min=0)] = None,
    max_failed_experiments: Annotated[int, typer.Option(min=0)] = 2,
    max_replans: Annotated[int, typer.Option(min=0)] = 2,
    hpo: Annotated[bool, typer.Option(help="Run a persistent inner-loop Optuna study.")] = False,
    trials: Annotated[
        int, typer.Option(min=1, help="Trials per study and total HPO trial limit.")
    ] = 6,
    sampler_seed: Annotated[int, typer.Option(min=0, max=2**32 - 1)] = 42,
    agent: Annotated[bool, typer.Option(help="Use the DeepSeek outer research loop.")] = False,
    literature: Annotated[
        bool, typer.Option(help="Ground the DeepSeek agent in arXiv and Semantic Scholar.")
    ] = False,
    max_literature_queries: Annotated[int, typer.Option(min=1, max=3)] = 2,
    max_papers: Annotated[int, typer.Option(min=1)] = 6,
    max_claims: Annotated[int, typer.Option(min=1)] = 12,
    max_claims_per_paper: Annotated[int, typer.Option(min=1, max=3)] = 2,
    max_llm_calls: Annotated[int, typer.Option(min=1)] = 10,
    max_llm_tokens: Annotated[int, typer.Option(min=256)] = 100_000,
    max_patch_repairs: Annotated[int, typer.Option(min=0, max=2)] = 1,
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
    if hpo and executor != ExecutionEnvironment.DOCKER:
        raise typer.BadParameter("--hpo requires --executor docker")
    if agent and executor != ExecutionEnvironment.DOCKER:
        raise typer.BadParameter("--agent requires --executor docker")
    if literature and not agent:
        raise typer.BadParameter("--literature requires --agent")
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
        settings = (
            LLMSettings.from_environment().model_copy(
                update={"max_patch_repairs": max_patch_repairs}
            )
            if agent
            else None
        )
        state = repository.create(
            ResearchState(
                research_goal=goal,
                next_step=Step.INSPECT_REPOSITORY if agent else Step.LITERATURE,
                simulation=scenario,
                baseline=Baseline(min_delta=min_delta),
                execution=execution or ExecutionConfig(runtime_root=runtime_root.resolve()),
                hpo=HPOConfig(max_trials=trials, sampler_seed=sampler_seed) if hpo else None,
                llm=settings,
                literature_settings=LiteratureSettings(
                    enabled=literature, max_claims_per_paper=max_claims_per_paper
                ),
                budget=ResearchBudget(
                    max_literature_queries=max_literature_queries if literature else 0,
                    max_papers=max_papers if literature else 0,
                    max_claims=max_claims if literature else 0,
                    max_iterations=max_iterations,
                    max_experiments=(
                        max_experiments
                        if max_experiments is not None
                        else trials + 1
                        if hpo or agent
                        else 3
                    ),
                    max_hpo_trials=trials if hpo or agent else 0,
                    max_llm_calls=max_llm_calls if agent else 0,
                    max_llm_tokens=max_llm_tokens if agent else 0,
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


@app.command("judge-evidence")
def judge_evidence(
    hypothesis: Annotated[str, typer.Option(help="Research hypothesis to assess.")],
    claim: Annotated[str, typer.Option(help="A claim or excerpt from a paper.")],
    model: Annotated[str, typer.Option(help="Pinned TypeSafe model version.")] = "jev-latest",
) -> None:
    """Use Jev to classify literature evidence; this does not decide experiment outcomes."""
    state = {"hypothesis": hypothesis, "paper_claim": claim}
    if len(json.dumps(state, ensure_ascii=False)) > 7_500:
        raise typer.BadParameter(
            "Combined hypothesis and claim must be under 7,500 JSON characters"
        )
    try:
        with TypeSafeClient() as client:
            response = client.system_one(
                state=state,
                model=model,
                questions={
                    "relation": Choice(
                        instructions="How does this paper claim relate to the hypothesis?",
                        criteria={
                            "supports": "Provides evidence in favor of the hypothesis",
                            "contradicts": "Provides evidence against the hypothesis",
                            "mixed": "Contains both supporting and contradicting evidence",
                            "unclear": "The claim does not establish a clear relation",
                        },
                    ),
                    "strength": Score(
                        instructions=(
                            "Rate this claim's evidence strength, considering specificity and"
                            " directness."
                        ),
                        criteria=["very weak", "weak", "moderate", "strong", "very strong"],
                    ),
                    "relevant": Noul(
                        instructions=(
                            "Does the paper claim materially address the stated hypothesis?"
                        )
                    ),
                },
            )
    except TypeSafeError as exc:
        typer.echo(f"Jev request failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(
        json.dumps(
            {
                "model": response.model,
                "relation": response.choices["relation"].choice,
                "relation_confidence": response.choices["relation"].confidence,
                "strength": response.scores["strength"].score,
                "strength_confidence": response.scores["strength"].confidence,
                "relevance_probability": response.nouls["relevant"].noul,
                "usage": response.usage.model_dump(),
                "note": "Advisory literature triage only; verify against the cited source.",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@app.command()
def serve_api(
    db: DatabaseOption = DEFAULT_DB,
    host: Annotated[str, typer.Option()] = "127.0.0.1",
    port: Annotated[int, typer.Option(min=1, max=65535)] = 8000,
) -> None:
    """Serve the read-only API consumed by the frontend."""
    serve(db, host, port)


class ReportFormat(StrEnum):
    MARKDOWN = "markdown"
    JSON = "json"


@app.command("report")
def report_command(
    research_id: UUID,
    db: DatabaseOption = DEFAULT_DB,
    format: Annotated[ReportFormat, typer.Option()] = ReportFormat.MARKDOWN,
) -> None:
    """Export a reproducible report to stdout without running experiments."""
    with repository_at(db) as repository:
        state = repository.load(research_id)
        typer.echo(
            report_markdown(state)
            if format == ReportFormat.MARKDOWN
            else json.dumps(research_report(state), indent=2, allow_nan=False)
        )


@app.command("evaluate")
def evaluate_command(
    seeds: Annotated[str, typer.Option(help="Comma-separated random seeds, for example 42,43,44.")],
    goal: Annotated[
        str | None, typer.Option(help="Research question; inherited from --from-run if omitted.")
    ] = None,
    db: DatabaseOption = DEFAULT_DB,
    evaluation_id: Annotated[UUID | None, typer.Option()] = None,
    from_run: Annotated[
        UUID | None, typer.Option(help="Reuse a completed CONFIG_ONLY proposal.")
    ] = None,
    executor: Annotated[ExecutionEnvironment, typer.Option()] = ExecutionEnvironment.FAKE,
    repo: Annotated[
        Path | None, typer.Option(help="Clean dedicated repository for Docker runs.")
    ] = None,
    patch: Annotated[
        Path | None, typer.Option(help="Patch diff; Docker defaults to dropout intervention.")
    ] = None,
    runtime_root: Annotated[Path, typer.Option()] = Path(".labpilot"),
    image: Annotated[str, typer.Option()] = "labpilot-mnist:phase2",
    build_image: Annotated[bool, typer.Option("--build-image/--reuse-image")] = True,
    timeout: Annotated[float, typer.Option(min=0.01)] = 180,
    min_delta: Annotated[float, typer.Option(min=0.000000001)] = 0.01,
    outcomes: Annotated[
        str,
        typer.Option(help="Fake mode only: comma-separated improve, regress, inconclusive, fail."),
    ] = "improve",
    format: Annotated[ReportFormat, typer.Option()] = ReportFormat.JSON,
) -> None:
    """Run or resume a durable multi-seed evaluation; seeds execute sequentially."""
    try:
        seed_values = tuple(int(value.strip()) for value in seeds.split(","))
        if (
            not seed_values
            or any(seed < 0 for seed in seed_values)
            or len(set(seed_values)) != len(seed_values)
        ):
            raise ValueError
    except ValueError as exc:
        raise typer.BadParameter(
            "Provide unique non-negative integer seeds", param_hint="--seeds"
        ) from exc
    try:
        scenario = SimulationConfig(
            outcomes=tuple(FakeOutcome(value.strip()) for value in outcomes.split(","))
        )
    except ValueError as exc:
        raise typer.BadParameter(
            "Use improve, regress, inconclusive, or fail", param_hint="--outcomes"
        ) from exc
    if executor == ExecutionEnvironment.DOCKER and repo is None:
        raise typer.BadParameter("--repo is required for Docker execution")
    if executor == ExecutionEnvironment.FAKE and repo is not None:
        raise typer.BadParameter("--repo requires --executor docker")
    if from_run is None and goal is None:
        raise typer.BadParameter("--goal is required unless --from-run is provided")
    evaluation_id = evaluation_id or uuid4()
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
        else ExecutionConfig(runtime_root=runtime_root.resolve())
    )
    source = None
    source_plan = None
    if from_run is not None:
        if executor != ExecutionEnvironment.DOCKER or patch is not None:
            raise typer.BadParameter(
                "--from-run requires Docker and cannot be combined with --patch"
            )
        with repository_at(db) as source_repository:
            source = source_repository.load(from_run)
        source_plan = next(
            (item for item in source.plans if item.id == source.active_plan_id), None
        )
        if (
            source.status != RunStatus.COMPLETED
            or source_plan is None
            or source_plan.change_type != ChangeType.CONFIG_ONLY
            or source_plan.configuration_overrides is None
            or source.active_hypothesis_id != source_plan.hypothesis_id
            or not source.baseline_experiment_id
            or source.execution.baseline_repo_path != execution.baseline_repo_path
            or source.execution.base_commit_sha != execution.base_commit_sha
            or source.execution.image != execution.image
            or source.execution.training_command != execution.training_command
            or source.execution.dataset != execution.dataset
        ):
            raise typer.BadParameter(
                "Source must be completed CONFIG_ONLY run matching the goal, repository, "
                "commit, image, and command"
            )
        execution = execution.model_copy(
            update={"training_overrides": source_plan.configuration_overrides, "patch_diff": ""}
        )
        if goal is not None and goal != source.research_goal:
            raise typer.BadParameter("--goal must match the source research goal")
        goal = source.research_goal
    assert goal is not None
    manifest_path = runtime_root / "evaluations" / f"{evaluation_id}.json"
    config = {
        "id": str(evaluation_id),
        "goal": goal,
        "seeds": list(seed_values),
        "executor": executor.value,
        "outcomes": [item.value for item in scenario.outcomes]
        if executor == ExecutionEnvironment.FAKE
        else None,
        "database": str(db.resolve()),
        "runtime_root": str(runtime_root.resolve()),
        "repo": str(repo.resolve()) if repo else None,
        "patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest()
        if patch
        else None,
        "image": image,
        "build_image": build_image,
        "base_commit_sha": execution.base_commit_sha,
        "timeout": timeout,
        "min_delta": min_delta,
        "source_run_id": str(source.research_id) if source else None,
        "source_hypothesis_id": str(source.active_hypothesis_id) if source else None,
        "source_plan_id": str(source_plan.id) if source_plan else None,
        "training_overrides": execution.training_overrides.model_dump(
            mode="json", exclude_none=True
        )
        if execution.training_overrides
        else None,
        **(
            {"dataset": execution.dataset.model_dump(mode="json")}
            if execution.dataset
            else {}
        ),
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if manifest["config"] != config:
            raise typer.BadParameter("Evaluation ID already belongs to a different configuration")
    else:
        manifest = {"config": config}
        temporary = manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(manifest, indent=2) + "\n")
        os.replace(temporary, manifest_path)
    typer.echo(f"Evaluation ID: {evaluation_id}", err=True)
    research_ids = [uuid5(evaluation_id, f"seed:{seed}") for seed in seed_values]
    with repository_at(db) as repository:
        for seed, research_id in zip(seed_values, research_ids, strict=True):
            try:
                state = repository.load(research_id)
                if (
                    state.research_goal != goal
                    or state.simulation.seed != seed
                    or state.proposal_source_run_id != (source.research_id if source else None)
                    or state.proposal_source_hypothesis_id
                    != (source.active_hypothesis_id if source else None)
                    or state.proposal_source_plan_id != (source_plan.id if source_plan else None)
                    or state.execution.training_overrides != execution.training_overrides
                ):
                    raise typer.BadParameter(
                        f"Seed run {research_id} conflicts with its evaluation"
                    )
            except RunNotFoundError:
                state = repository.create(
                    ResearchState(
                        research_id=research_id,
                        research_goal=goal,
                        simulation=scenario.model_copy(update={"seed": seed}),
                        baseline=Baseline(min_delta=min_delta),
                        execution=execution,
                        proposal_source_run_id=source.research_id if source else None,
                        proposal_source_hypothesis_id=(
                            source.active_hypothesis_id if source else None
                        ),
                        proposal_source_plan_id=source_plan.id if source_plan else None,
                    )
                )
            if state.status not in {RunStatus.COMPLETED, RunStatus.FAILED}:
                state = execute(repository, research_id)
            decision = state.decision.value if state.decision else "NONE"
            typer.echo(
                f"seed={seed} run={research_id} status={state.status.value} decision={decision}",
                err=True,
            )
        states = [repository.load(research_id) for research_id in research_ids]
    result = benchmark(states)
    result["evaluation_id"] = str(evaluation_id)
    result["seeds"] = list(seed_values)
    result["seed_runs"] = [str(item) for item in research_ids]
    result["source_run_id"] = str(source.research_id) if source else None
    result["source_hypothesis_id"] = str(source.active_hypothesis_id) if source else None
    result["source_plan_id"] = str(source_plan.id) if source_plan else None
    result["training_overrides"] = config["training_overrides"]
    if executor == ExecutionEnvironment.FAKE:
        result["interpretation"] = (
            "Simulated control-flow check only; fake outcomes do not vary "
            "with seed and are not scientific measurements."
        )
    typer.echo(
        benchmark_markdown(result)
        if format == ReportFormat.MARKDOWN
        else json.dumps(result, indent=2)
    )


@app.command("benchmark")
def benchmark_command(
    db: Annotated[list[Path] | None, typer.Option("--db")] = None,
    run_id: Annotated[list[UUID] | None, typer.Option("--run-id")] = None,
    format: Annotated[ReportFormat, typer.Option()] = ReportFormat.JSON,
) -> None:
    """Compare saved runs across one or more databases; never launch training."""
    states: list[ResearchState] = []
    for path in db or [DEFAULT_DB]:
        with repository_at(path) as repository:
            states.extend(
                repository.load(row.research_id)
                for row in repository.list_runs()
                if not run_id or row.research_id in run_id
            )
    if run_id and set(run_id) - {state.research_id for state in states}:
        raise typer.BadParameter("Some requested run IDs were not found")
    try:
        data = benchmark(states)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(
        benchmark_markdown(data)
        if format == ReportFormat.MARKDOWN
        else json.dumps(data, indent=2, allow_nan=False)
    )
