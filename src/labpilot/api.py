"""Read-only HTTP API for the frontend, backed by existing SQLite snapshots."""

from __future__ import annotations

import json
import shutil
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from labpilot.models.experiments import Experiment
from labpilot.models.state import ResearchState
from labpilot.persistence.repository import RunNotFoundError, SQLiteResearchRepository
from labpilot.reporting import (
    benchmark,
    benchmark_markdown,
    evaluate_run,
    measured_value,
    report_markdown,
    research_report,
)


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


def handler_for(repository: SQLiteResearchRepository) -> type[BaseHTTPRequestHandler]:
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
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

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
    server = ThreadingHTTPServer((host, port), handler_for(repository))
    try:
        print(f"LabPilot API listening on http://{host}:{port}")
        server.serve_forever()
    finally:
        server.server_close()
        repository.close()
