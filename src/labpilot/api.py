"""Local HTTP API for persisted research runs and their creation."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

from labpilot.agent.repository import RepositoryInspector
from labpilot.execution.git import GitError, WorktreeManager
from labpilot.graph.workflow import execute
from labpilot.llm.models import LLMSettings
from labpilot.models.budget import ResearchBudget
from labpilot.models.common import ChangeType, MetricDirection, RunStatus, Step
from labpilot.models.experiments import Baseline, Experiment
from labpilot.models.literature import LiteratureSettings, Paper
from labpilot.models.state import ResearchState, SimulationConfig
from labpilot.persistence.repository import RunNotFoundError, SQLiteResearchRepository
from labpilot.reporting import (
    benchmark,
    benchmark_markdown,
    evaluate_run,
    measured_value,
    report_markdown,
    research_report,
)
from labpilot.services.real import configure_docker, prepare_example


def _experiment(state: ResearchState, item: Experiment) -> dict[str, Any]:
    result = item.result
    decision = next((d for d in reversed(state.decisions) if d.experiment_id == item.id), None)
    value = measured_value(state, item)
    direction = 1 if state.baseline.direction.value == "MAXIMIZE" else -1
    return {
        "id": str(item.id),
        "research_id": str(state.research_id),
        "purpose": item.purpose.value,
        "hypothesis_id": str(item.hypothesis_id) if item.hypothesis_id else None,
        "sequence": item.sequence,
        "status": item.status.value,
        "config": {
            "seed": item.config.seed,
            "direction": item.config.direction.value,
            "metric_name": item.config.metric_name,
            "parameters": item.config.overrides.model_dump(exclude_none=True)
            if item.config.overrides
            else {},
        },
        "metric_value": value,
        "delta": (value - state.baseline.value) * direction
        if value is not None and item.purpose.value != "BASELINE"
        else None,
        "runtime_seconds": result.execution.runtime_seconds
        if result and result.execution
        else None,
        "executor": state.execution.environment.value,
        "error": item.error,
        "provenance": result.execution.model_dump(mode="json")
        if result and result.execution
        else None,
        "decision": decision.decision.value if decision else None,
    }


def _trial(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "study_id": str(item.study_id) if item.study_id else None,
        "optuna_trial_number": item.optuna_trial_number,
        "status": item.status.value,
        "parameters": item.parameters.as_dict(),
        "primary_metric_value": item.primary_metric_value,
        "runtime_seconds": item.runtime_seconds,
        "failure_reason": item.failure_reason,
    }


def _study(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "research_id": str(item.research_id),
        "hypothesis_id": str(item.hypothesis_id),
        "study_name": item.study_name,
        "sampler_name": item.sampler_name,
        "sampler_seed": item.sampler_seed,
        "primary_metric": item.primary_metric,
        "direction": item.direction.value,
        "max_trials": item.max_trials,
        "completed_trials": item.completed_trials,
        "failed_trials": item.failed_trials,
        "pruned_trials": item.pruned_trials,
        "best_trial_id": str(item.best_trial_id) if item.best_trial_id else None,
        "status": item.status.value,
        "created_at": item.created_at.isoformat(),
        "search_space": [part.model_dump(mode="json") for part in item.search_space.parameters],
    }


def uploaded_paper(name: str, encoded: str) -> Paper:
    filename = Path(name).name
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".txt", ".md"}:
        raise ValueError("Upload a PDF, Markdown, or text paper")
    raw = base64.b64decode(encoded, validate=True)
    if not raw or len(raw) > 5 * 1024 * 1024:
        raise ValueError("Paper must be between 1 byte and 5 MB")
    if suffix == ".pdf":
        result = subprocess.run(
            ["pdftotext", "-layout", "-", "-"],
            input=raw,
            capture_output=True,
            timeout=20,
            check=False,
        )
        if result.returncode:
            raise ValueError("Could not read PDF; install Poppler's pdftotext")
        text = result.stdout.decode("utf-8", errors="replace")
    else:
        text = raw.decode("utf-8-sig")
    excerpt = " ".join(text.split())[:12_000]
    if len(excerpt) < 40:
        raise ValueError("Uploaded paper contains too little readable text")
    return Paper(
        title=Path(filename).stem,
        full_text_excerpt=excerpt,
        source_provider="user_upload",
    )


def research_preview(payload: dict[str, Any]) -> dict[str, Any]:
    goal = str(payload.get("goal", "")).strip()
    if not goal or len(goal) > 1000:
        raise ValueError("Research topic must contain 1–1000 characters")
    metric_name = str(payload.get("metric_name", "validation_accuracy")).strip()
    if not metric_name or len(metric_name) > 80:
        raise ValueError("Metric name must contain 1–80 characters")
    direction = MetricDirection(payload.get("direction", MetricDirection.MAXIMIZE.value))
    seed = payload.get("seed", 42)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**32 - 1:
        raise ValueError("Random seed must be an integer from 0 to 4294967295")
    constraints = str(payload.get("constraints", "")).strip()
    if len(constraints) > 3000:
        raise ValueError("Additional research instructions must be 3000 characters or fewer")
    max_queries = payload.get("max_literature_queries", 2)
    if (
        isinstance(max_queries, bool)
        or not isinstance(max_queries, int)
        or not 1 <= max_queries <= 3
    ):
        raise ValueError("Literature query count must be between one and three")
    max_papers = payload.get("max_retrieved_papers", 6)
    if isinstance(max_papers, bool) or not isinstance(max_papers, int) or not 1 <= max_papers <= 10:
        raise ValueError("Retrieved paper limit must be between one and ten")
    evidence_judge = payload.get("evidence_judge", "deepseek")
    if evidence_judge not in {"deepseek", "jev"}:
        raise ValueError("Evidence judge must be deepseek or jev")
    iterations = payload.get("max_iterations", 3)
    if isinstance(iterations, bool) or not isinstance(iterations, int) or not 1 <= iterations <= 3:
        raise ValueError("Research depth must be between one and three iterations")
    change_type = payload.get("change_type")
    if change_type not in (
        None,
        ChangeType.CONFIG_ONLY.value,
        ChangeType.CODE_CHANGE.value,
    ):
        raise ValueError("Change scope must be automatic, configuration, or code")
    papers = payload.get("papers", [])
    if not isinstance(papers, list) or len(papers) > 5:
        raise ValueError("Upload at most five papers")
    paper_names = [Path(str(item)).name for item in papers]

    project_root = Path(__file__).resolve().parents[2]
    repo_value = str(payload.get("baseline_path", "")).strip()
    if not repo_value and (metric_name, direction.value) not in {
        ("validation_accuracy", "MAXIMIZE"),
        ("validation_loss", "MINIMIZE"),
    }:
        raise ValueError(
            "The included MNIST baseline supports validation_accuracy (maximize) "
            "or validation_loss (minimize)"
        )
    if repo_value:
        repo = Path(repo_value).expanduser().resolve()
        manager = WorktreeManager(repo, project_root / ".labpilot" / "worktrees")
        sha = manager.validate_clean_baseline()
        context = RepositoryInspector().inspect(repo, sha)
        baseline_name = repo.name
    else:
        with tempfile.TemporaryDirectory(prefix="labpilot-preview-") as temporary:
            repo = prepare_example(
                project_root / "examples" / "mnist_baseline", Path(temporary) / "baseline"
            )
            sha = WorktreeManager(repo, Path(temporary) / "worktrees").validate_clean_baseline()
            context = RepositoryInspector().inspect(repo, sha)
        baseline_name = "MNIST baseline"

    files = context.file_tree
    warnings = []
    if "Dockerfile" not in files:
        warnings.append("Dockerfile is missing; container execution may not work.")
    if not any(Path(name).name == "train.py" for name in files):
        warnings.append("No train.py entry point was found; verify the repository runner contract.")
    if not any(Path(name).name == "dataset.json" for name in files):
        warnings.append(
            "No dataset.json was found; the baseline must handle its data setup itself."
        )
    if repo_value and metric_name not in {"validation_accuracy", "validation_loss"}:
        warnings.append("The custom runner must write this metric to outputs/metrics.json.")
    if evidence_judge == "jev" and not os.getenv("OPENROUTER_API_KEY"):
        warnings.append("Jev selected, but OPENROUTER_API_KEY is not configured; run cannot start.")
    return {
        "goal": goal,
        "constraints": constraints,
        "baseline": {
            "name": baseline_name,
            "commit_sha": sha,
            "file_count": len(files),
            "important_files": [item.path for item in context.important_files],
        },
        "objective": {"metric_name": metric_name, "direction": direction.value},
        "papers": paper_names,
        "literature": {
            "providers": ["arxiv", "semantic_scholar"],
            "max_queries": max_queries,
            "max_papers": max_papers,
            "evidence_judge": evidence_judge,
        },
        "evidence_judge_ready": evidence_judge != "jev" or bool(os.getenv("OPENROUTER_API_KEY")),
        "seed": seed,
        "max_iterations": iterations,
        "max_experiments": iterations + 1,
        "change_type": change_type,
        "warnings": warnings,
    }


def _run(state: ResearchState) -> dict[str, Any]:
    experiments = [_experiment(state, item) for item in state.experiments]
    trials = [_trial(item) for item in state.trials]
    studies = [_study(item) for item in state.studies]
    evaluation = evaluate_run(state)
    summary = {
        "research_id": str(state.research_id),
        "goal": state.research_goal,
        "status": state.status.value,
        "decision": state.decision.value if state.decision else None,
        "iteration": state.iteration,
        "executor": state.execution.environment.value,
        "baseline_metric": evaluation["baseline"],
        "best_metric": evaluation["best"],
        "delta": evaluation["improvement"],
        "experiment_count": len(experiments),
        "failed_experiments": state.budget.failed_experiments,
        "created_at": state.created_at.isoformat(),
        "updated_at": state.updated_at.isoformat(),
    }
    return {
        **summary,
        "next_step": state.next_step.value,
        "revision": state.revision,
        "termination_reason": state.termination_reason,
        "baseline": state.baseline.model_dump(mode="json"),
        "budget": state.budget.model_dump(mode="json"),
        "decisions": [item.model_dump(mode="json") for item in state.decisions],
        "experiments": experiments,
        "studies": studies,
        "trials": trials,
        "papers": [item.model_dump(mode="json") for item in state.papers],
        "claims": [item.model_dump(mode="json") for item in state.claims],
        "evidence": [item.model_dump(mode="json") for item in state.evidence],
        "hypotheses": [item.model_dump(mode="json") for item in state.hypotheses],
        "patches": [item.model_dump(mode="json") for item in state.patches],
    }


def handler_for(
    repository: SQLiteResearchRepository, database_path: Path | None = None
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def respond(self, status: HTTPStatus, payload: object) -> None:
            body = json.dumps(payload, default=str, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_POST(self) -> None:
            route = urlparse(self.path).path
            if route == "/api/research-preview":
                origin = self.headers.get("Origin", "")
                if origin and urlparse(origin).hostname not in {"localhost", "127.0.0.1"}:
                    return self.respond(HTTPStatus.FORBIDDEN, {"error": "Local origin required"})
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length < 1 or length > 64 * 1024:
                        raise ValueError("Preview request must be under 64 KB")
                    payload = json.loads(self.rfile.read(length))
                    if not isinstance(payload, dict):
                        raise ValueError("Request body must be a JSON object")
                    return self.respond(HTTPStatus.OK, research_preview(payload))
                except (ValueError, KeyError, json.JSONDecodeError, OSError, GitError) as exc:
                    return self.respond(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            if route != "/api/runs":
                return self.respond(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            if database_path is None:
                return self.respond(
                    HTTPStatus.NOT_IMPLEMENTED, {"error": "Run creation unavailable"}
                )
            origin = self.headers.get("Origin", "")
            if origin and urlparse(origin).hostname not in {"localhost", "127.0.0.1"}:
                return self.respond(HTTPStatus.FORBIDDEN, {"error": "Local origin required"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 8 * 1024 * 1024:
                    raise ValueError("Request must be under 8 MB")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("Request body must be a JSON object")
                goal = str(payload.get("goal", "")).strip()
                if not goal or len(goal) > 1000:
                    raise ValueError("Research topic must contain 1–1000 characters")
                evidence_judge = payload.get("evidence_judge", "deepseek")
                if evidence_judge not in {"deepseek", "jev"}:
                    raise ValueError("Evidence judge must be deepseek or jev")
                if evidence_judge == "jev" and not os.getenv("OPENROUTER_API_KEY"):
                    raise ValueError("Set OPENROUTER_API_KEY before starting a run with Jev")
                iterations = payload.get("max_iterations", 3)
                if (
                    isinstance(iterations, bool)
                    or not isinstance(iterations, int)
                    or not 1 <= iterations <= 3
                ):
                    raise ValueError("Research depth must be between one and three iterations")
                change_type = payload.get("change_type")
                if change_type not in (
                    None,
                    ChangeType.CONFIG_ONLY.value,
                    ChangeType.CODE_CHANGE.value,
                ):
                    raise ValueError("Change scope must be automatic, configuration, or code")
                metric_name = str(payload.get("metric_name", "validation_accuracy")).strip()
                if not metric_name or len(metric_name) > 80:
                    raise ValueError("Metric name must contain 1–80 characters")
                direction = MetricDirection(payload.get("direction", "MAXIMIZE"))
                seed = payload.get("seed", 42)
                if (
                    isinstance(seed, bool)
                    or not isinstance(seed, int)
                    or not 0 <= seed <= 2**32 - 1
                ):
                    raise ValueError("Random seed must be an integer from 0 to 4294967295")
                constraints = str(payload.get("constraints", "")).strip()
                if len(constraints) > 3000:
                    raise ValueError(
                        "Additional research instructions must be 3000 characters or fewer"
                    )
                max_queries = payload.get("max_literature_queries", 2)
                if (
                    isinstance(max_queries, bool)
                    or not isinstance(max_queries, int)
                    or not 1 <= max_queries <= 3
                ):
                    raise ValueError("Literature query count must be between one and three")
                max_retrieved_papers = payload.get("max_retrieved_papers", 6)
                if (
                    isinstance(max_retrieved_papers, bool)
                    or not isinstance(max_retrieved_papers, int)
                    or not 1 <= max_retrieved_papers <= 10
                ):
                    raise ValueError("Retrieved paper limit must be between one and ten")
                research_id = uuid4()
                repo_value = str(payload.get("baseline_path", "")).strip()
                if not repo_value and (metric_name, direction.value) not in {
                    ("validation_accuracy", "MAXIMIZE"),
                    ("validation_loss", "MINIMIZE"),
                }:
                    raise ValueError(
                        "The included MNIST baseline supports validation_accuracy (maximize) "
                        "or validation_loss (minimize)"
                    )
                repo = Path(repo_value).expanduser().resolve() if repo_value else None
                project_root = Path(__file__).resolve().parents[2]
                runtime_root = project_root / ".labpilot"
                if repo is None:
                    repo = prepare_example(
                        project_root / "examples" / "mnist_baseline",
                        runtime_root / "baselines" / str(research_id),
                    )
                execution = configure_docker(
                    repo,
                    runtime_root,
                    use_predefined_patch=repo_value == "",
                )
                if execution.dataset is not None:
                    execution = execution.model_copy(
                        update={
                            "dataset": execution.dataset.model_copy(
                                update={
                                    "metric_name": metric_name,
                                    "direction": direction.value.lower(),
                                }
                            )
                        }
                    )
                uploaded = payload.get("papers", [])
                if not isinstance(uploaded, list) or len(uploaded) > 5:
                    raise ValueError("Upload at most five papers")
                encoded_files = [
                    item.get("data", "") for item in uploaded if isinstance(item, dict)
                ]
                encoded_limit = ((5 * 1024 * 1024 + 2) // 3) * 4
                if len(encoded_files) != len(uploaded) or any(
                    not isinstance(data, str) for data in encoded_files
                ):
                    raise ValueError("Each paper must include a file and contents")
                if sum(map(len, encoded_files)) > encoded_limit:
                    raise ValueError("Uploaded papers must total 5 MB or less")
                papers: tuple[Paper, ...] = ()
                accepted: list[Paper] = []
                for item in uploaded:
                    if not isinstance(item, dict):
                        raise ValueError("Each paper must include a file and contents")
                    accepted.append(
                        uploaded_paper(str(item.get("name", "paper")), str(item.get("data", "")))
                    )
                if accepted:
                    papers = tuple(accepted)
                if sum(len(item.full_text_excerpt or "") for item in papers) > 60_000:
                    raise ValueError("Uploaded papers exceed the total text limit")
                state = repository.create(
                    ResearchState(
                        research_id=research_id,
                        research_goal=(
                            f"{goal}\n\nAdditional user constraints:\n{constraints}"
                            if constraints
                            else goal
                        ),
                        next_step=Step.INSPECT_REPOSITORY,
                        required_change_type=ChangeType(change_type) if change_type else None,
                        papers=papers,
                        literature_settings=LiteratureSettings(
                            enabled=True, evidence_judge=evidence_judge
                        ),
                        execution=execution,
                        llm=LLMSettings.from_environment(),
                        baseline=Baseline(metric_name=metric_name, direction=direction),
                        simulation=SimulationConfig(seed=seed),
                        budget=ResearchBudget(
                            max_literature_queries=max_queries,
                            max_papers=max_retrieved_papers + len(papers),
                            papers=len(papers),
                            max_claims=12,
                            max_llm_calls=40,
                            max_llm_tokens=200_000,
                            max_iterations=iterations,
                            max_experiments=iterations + 1,
                            max_failed_experiments=2,
                            max_replans=2,
                        ),
                    )
                )

                def run_in_background() -> None:
                    worker = SQLiteResearchRepository(database_path)
                    try:
                        execute(worker, state.research_id)
                    except Exception as exc:
                        current = worker.load(state.research_id)
                        if current.status not in {RunStatus.FAILED, RunStatus.COMPLETED}:
                            worker.save(
                                current.evolve(status=RunStatus.FAILED, termination_reason=str(exc))
                            )
                    finally:
                        worker.close()

                threading.Thread(target=run_in_background, daemon=True).start()
                return self.respond(
                    HTTPStatus.ACCEPTED,
                    {"research_id": str(state.research_id), "status": "RUNNING"},
                )
            except (
                ValueError,
                KeyError,
                UnicodeDecodeError,
                json.JSONDecodeError,
                OSError,
                GitError,
                subprocess.TimeoutExpired,
            ) as exc:
                return self.respond(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            parts = [part for part in parsed.path.split("/") if part]
            try:
                if parts == ["api", "reports"]:
                    states = sorted(
                        (repository.load(row.research_id) for row in repository.list_runs()),
                        key=lambda state: state.updated_at,
                        reverse=True,
                    )
                    return self.respond(HTTPStatus.OK, [evaluate_run(s) for s in states])
                if parts == ["api", "benchmark"]:
                    ids = parse_qs(parsed.query).get("run_id", [])
                    states = (
                        [repository.load(UUID(value)) for value in ids]
                        if ids
                        else [repository.load(row.research_id) for row in repository.list_runs()]
                    )
                    data = benchmark(states)
                    if parse_qs(parsed.query).get("format") == ["markdown"]:
                        return self.document(benchmark_markdown(data), "benchmark.md")
                    return self.respond(HTTPStatus.OK, data)
                if len(parts) == 3 and parts[:2] == ["api", "reports"]:
                    state = repository.load(UUID(parts[2]))
                    format = parse_qs(parsed.query).get("format", [None])[0]
                    if format == "markdown":
                        return self.document(report_markdown(state), f"{state.research_id}.md")
                    if format == "json":
                        return self.document(
                            json.dumps(research_report(state), indent=2),
                            f"{state.research_id}.json",
                        )
                    return self.respond(
                        HTTPStatus.OK, {**research_report(state), "run": _run(state)}
                    )
                if parts == ["api", "health"]:
                    return self.respond(HTTPStatus.OK, {"status": "ok"})
                if parts == ["api", "runs"]:
                    states = sorted(
                        (repository.load(row.research_id) for row in repository.list_runs()),
                        key=lambda state: state.updated_at,
                        reverse=True,
                    )
                    if parse_qs(parsed.query).get("full") == ["1"]:
                        return self.respond(HTTPStatus.OK, [_run(state) for state in states])
                    return self.respond(
                        HTTPStatus.OK,
                        [
                            {
                                k: v
                                for k, v in _run(s).items()
                                if k
                                in {
                                    "research_id",
                                    "goal",
                                    "status",
                                    "decision",
                                    "iteration",
                                    "executor",
                                    "baseline_metric",
                                    "best_metric",
                                    "delta",
                                    "experiment_count",
                                    "failed_experiments",
                                    "created_at",
                                    "updated_at",
                                }
                            }
                            for s in states
                        ],
                    )
                if parts == ["api", "experiments"]:
                    research_id = parse_qs(parsed.query).get("research_id", [None])[0]
                    states = (
                        [repository.load(UUID(research_id))]
                        if research_id
                        else [repository.load(row.research_id) for row in repository.list_runs()]
                    )
                    return self.respond(
                        HTTPStatus.OK,
                        [exp for state in states for exp in _run(state)["experiments"]],
                    )
                if parts == ["api", "activity"]:
                    limit = max(0, min(100, int(parse_qs(parsed.query).get("limit", [12])[0])))
                    events = [
                        event
                        for row in repository.list_runs()
                        for event in activity(repository.load(row.research_id), limit)
                    ]
                    return self.respond(
                        HTTPStatus.OK,
                        sorted(events, key=lambda x: x["at"], reverse=True)[:limit],
                    )
                if len(parts) == 3 and parts[:2] == ["api", "experiments"]:
                    for row in repository.list_runs():
                        state = repository.load(row.research_id)
                        match = next(
                            (x for x in _run(state)["experiments"] if x["id"] == parts[2]),
                            None,
                        )
                        if match:
                            return self.respond(
                                HTTPStatus.OK, {"run": _run(state), "experiment": match}
                            )
                    return self.respond(HTTPStatus.NOT_FOUND, {"error": "Experiment not found"})
                if (
                    len(parts) == 5
                    and parts[:2] == ["api", "experiments"]
                    and parts[3] == "artifacts"
                ):
                    return self.artifact(parts[2], parts[4])
                if len(parts) == 3 and parts[:2] == ["api", "studies"]:
                    for row in repository.list_runs():
                        state = repository.load(row.research_id)
                        data = _run(state)
                        study = next((x for x in data["studies"] if x["id"] == parts[2]), None)
                        if study:
                            return self.respond(
                                HTTPStatus.OK,
                                {
                                    "run": data,
                                    "study": study,
                                    "trials": [
                                        x for x in data["trials"] if x["study_id"] == parts[2]
                                    ],
                                },
                            )
                    return self.respond(HTTPStatus.NOT_FOUND, {"error": "Study not found"})
                if len(parts) >= 3 and parts[:2] == ["api", "runs"]:
                    state = repository.load(UUID(parts[2]))
                    if len(parts) == 3:
                        return self.respond(HTTPStatus.OK, _run(state))
                    if parts[3] == "state" and len(parts) == 4:
                        return self.respond(HTTPStatus.OK, state.model_dump(mode="json"))
                    if parts[3] == "activity" and len(parts) == 4:
                        limit = max(0, min(100, int(parse_qs(parsed.query).get("limit", [12])[0])))
                        return self.respond(HTTPStatus.OK, activity(state, limit))
            except (RunNotFoundError, ValueError):
                return self.respond(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return self.respond(HTTPStatus.NOT_FOUND, {"error": "Not found"})

        def document(self, content: str, filename: str) -> None:
            body = content.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def artifact(self, experiment_id: str, name: str) -> None:
            names = {
                "stdout.log": "stdout_path",
                "stderr.log": "stderr_path",
                "metrics.json": "metrics_path",
                "provenance.json": "provenance_path",
                "patch.diff": "patch_path",
                "actual.diff": "actual_diff_path",
            }
            if name not in names:
                return self.respond(HTTPStatus.NOT_FOUND, {"error": "Artifact not found"})
            for row in repository.list_runs():
                state = repository.load(row.research_id)
                item = next((x for x in state.experiments if str(x.id) == experiment_id), None)
                if item is None or item.result is None or item.result.execution is None:
                    continue
                provenance = item.result.execution
                root = (
                    state.execution.runtime_root.resolve()
                    / "runs"
                    / str(state.research_id)
                    / str(item.id)
                )
                path = getattr(provenance.artifacts, names[name]).resolve()
                if not path.is_relative_to(root) or not path.is_file():
                    return self.respond(HTTPStatus.NOT_FOUND, {"error": "Artifact not found"})
                size = path.stat().st_size
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{name}"')
                self.send_header("Content-Length", str(size))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                with path.open("rb") as artifact:
                    shutil.copyfileobj(artifact, self.wfile)
                return
            self.respond(HTTPStatus.NOT_FOUND, {"error": "Artifact not found"})

    return Handler


def activity(state: ResearchState, limit: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for exp in state.experiments:
        provenance = exp.result.execution if exp.result else None
        items.append(
            {
                "id": f"experiment-{exp.id}",
                "research_id": str(state.research_id),
                "at": (
                    provenance.finished_at.isoformat()
                    if provenance
                    else state.updated_at.isoformat()
                ),
                "kind": "baseline_completed" if exp.purpose.value == "BASELINE" else "docker_run",
                "title": f"{exp.purpose.value.title()} experiment {exp.status.value.lower()}",
                "detail": exp.error,
                "experiment_id": str(exp.id),
            }
        )
    for decision in state.decisions:
        items.append(
            {
                "id": f"decision-{decision.experiment_id or decision.study_id}",
                "research_id": str(state.research_id),
                "at": state.updated_at.isoformat(),
                "kind": "decision",
                "title": f"Decision: {decision.decision.value}",
                "detail": decision.reason,
            }
        )
    return sorted(items, key=lambda x: x["at"], reverse=True)[:limit]


def serve(path: Path, host: str = "127.0.0.1", port: int = 8000) -> None:
    repository = SQLiteResearchRepository(path)
    server = ThreadingHTTPServer((host, port), handler_for(repository, path))
    try:
        print(f"LabPilot API listening on http://{host}:{port}")
        server.serve_forever()
    finally:
        server.server_close()
        repository.close()
