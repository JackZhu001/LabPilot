"""Deterministic reports and observational benchmarks from durable snapshots."""

import hashlib
import json
from collections import defaultdict
from collections.abc import Sequence
from statistics import mean, stdev
from typing import Any

from labpilot.models.common import ExperimentStatus, MetricDirection, RunStatus
from labpilot.models.execution import ExecutionEnvironment, ExperimentPurpose
from labpilot.models.experiments import Experiment
from labpilot.models.state import ResearchState


def fingerprint(state: ResearchState) -> str:
    content = json.dumps(state.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode()).hexdigest()


def measured_value(state: ResearchState, experiment: Experiment) -> float | None:
    if experiment.status != ExperimentStatus.SUCCEEDED:
        return None
    if experiment.result:
        return experiment.result.value
    # Older Phase 1 snapshots kept measurements in the metric collection only.
    return next(
        (
            m.value
            for m in reversed(state.metrics)
            if m.experiment_id == experiment.id and m.name == state.baseline.metric_name
        ),
        None,
    )


def evaluate_run(state: ResearchState) -> dict[str, Any]:
    fake = state.execution.environment == ExecutionEnvironment.FAKE
    values = [
        value
        for e in state.experiments
        if e.purpose == ExperimentPurpose.CANDIDATE
        and (value := measured_value(state, e)) is not None
    ]
    best = (
        (max(values) if state.baseline.direction == MetricDirection.MAXIMIZE else min(values))
        if values
        else None
    )
    baseline = state.baseline.value if fake or state.baseline_experiment_id else None
    improvement = (
        ((best - baseline) * (1 if state.baseline.direction == MetricDirection.MAXIMIZE else -1))
        if best is not None and baseline is not None
        else None
    )
    terminal = [
        e
        for e in state.experiments
        if e.status in {ExperimentStatus.SUCCEEDED, ExperimentStatus.FAILED}
    ]
    tested = {e.hypothesis_id for e in terminal if e.hypothesis_id}
    accepted = {d.hypothesis_id for d in state.decisions if d.decision.value == "KEEP"}
    attempted_patches = {e.patch_id for e in terminal if e.patch_id}
    successful_patches = {
        e.patch_id for e in terminal if e.patch_id and e.status == ExperimentStatus.SUCCEEDED
    }
    runtime = sum(
        e.result.execution.runtime_seconds
        for e in state.experiments
        if e.result and e.result.execution
    )
    strategy = (
        "simulation"
        if fake
        else (
            "literature"
            if state.literature_settings.enabled
            else "proposed-config"
            if state.proposal_source_run_id
            else "repository"
            if state.llm
            else "predefined"
        )
    )
    return {
        "research_id": str(state.research_id),
        "seed": state.simulation.seed,
        "goal": state.research_goal,
        "revision": state.revision,
        "snapshot_sha256": fingerprint(state),
        "updated_at": state.updated_at.isoformat(),
        "status": state.status.value,
        "decision": state.decision.value if state.decision else None,
        "executor": state.execution.environment.value,
        "strategy": strategy,
        "proposal_source_run_id": str(state.proposal_source_run_id)
        if state.proposal_source_run_id
        else None,
        "proposal_source_hypothesis_id": str(state.proposal_source_hypothesis_id)
        if state.proposal_source_hypothesis_id
        else None,
        "proposal_source_plan_id": str(state.proposal_source_plan_id)
        if state.proposal_source_plan_id
        else None,
        "training_overrides": state.execution.training_overrides.model_dump(
            mode="json", exclude_none=True
        )
        if state.execution.training_overrides
        else None,
        "dataset": state.execution.dataset.model_dump(mode="json")
        if state.execution.dataset
        else None,
        "metric_name": state.baseline.metric_name,
        "direction": state.baseline.direction.value,
        "baseline": baseline,
        "best": best,
        "improvement": improvement,
        "experiments": len(state.experiments),
        "finished_experiments": len(terminal),
        "successful_experiments": sum(e.status == ExperimentStatus.SUCCEEDED for e in terminal),
        "tested_hypotheses": len(tested),
        "accepted_hypotheses": len(tested & accepted),
        "attempted_patches": len(attempted_patches),
        "successful_patches": len(successful_patches),
        "runtime_seconds": runtime
        if not fake and any(e.result and e.result.execution for e in state.experiments)
        else None,
        "elapsed_seconds": (state.updated_at - state.created_at).total_seconds(),
        "llm_calls": state.budget.llm_calls,
        "llm_tokens": state.budget.llm_tokens,
        "cost_usd": None,
        "papers": len(state.papers),
        "claims": len(state.claims),
        "evidence": len(state.evidence),
        "grounded_hypotheses": sum(
            h.grounding_status.value != "REPOSITORY_ONLY" for h in state.hypotheses
        ),
    }


def _cell(value: object) -> str:
    return str(value if value is not None else "n/a").replace("|", "\\|").replace("\n", " ")


def _table(headers: list[str], rows: Sequence[Sequence[object]]) -> str:
    return "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
            *("| " + " | ".join(_cell(v) for v in row) + " |" for row in rows),
        ]
    )


def _code(text: str, language: str = "") -> str:
    fence = "```"
    while fence in text:
        fence += "`"
    return f"{fence}{language}\n{text}\n{fence}"


def report_markdown(state: ResearchState) -> str:
    summary = evaluate_run(state)
    sections = [
        f"# LabPilot research report\n\n{state.research_goal}",
        f"Run: `{state.research_id}` · Revision: {state.revision}\n\n"
        f"Snapshot SHA-256: `{summary['snapshot_sha256']}`\n\n"
        f"Recorded at: {state.updated_at.isoformat()}",
        "## Outcome\n\n"
        + _table(
            ["Status", "Decision", "Executor", "Strategy", "Metric", "Direction"],
            [
                [
                    summary[k]
                    for k in (
                        "status",
                        "decision",
                        "executor",
                        "strategy",
                        "metric_name",
                        "direction",
                    )
                ]
            ],
        ),
        _table(
            ["Baseline", "Best candidate", "Oriented improvement", "KEEP threshold"],
            [
                [
                    summary["baseline"],
                    summary["best"],
                    summary["improvement"],
                    state.baseline.min_delta,
                ]
            ],
        ),
        state.termination_reason or "This is an in-progress snapshot, not a final conclusion.",
        "Positive improvement means better for either metric direction. Best candidate is not "
        "necessarily the final decision. Simulated runs are not scientific measurements.",
        "## Experiments\n\n"
        + _table(
            ["ID", "Purpose", "Hypothesis", "Status", "Metric", "Seed", "Error"],
            [
                [
                    e.id,
                    e.purpose.value,
                    e.hypothesis_id,
                    e.status.value,
                    measured_value(state, e),
                    e.config.seed,
                    e.error,
                ]
                for e in state.experiments
            ],
        ),
        "## Hypotheses and evidence links",
    ]
    for h in state.hypotheses:
        sections.append(
            f"### {h.id}\n\n{h.statement}\n\n{h.motivation}\n\n"
            f"Grounding: {h.grounding_status.value}. Status: {h.status.value}.\n\n"
            f"Expected effect: {h.expected_effect}\n\n"
            f"Falsification: {h.falsification_criteria}\n\n"
            f"Evidence IDs: {', '.join(map(str, h.evidence_ids)) or 'none'}"
        )
    sections.append("## Literature and source fidelity")
    for p in state.papers:
        sections.append(
            f"### {p.title}\n\nPaper ID: {p.id}\n\n"
            f"Authors: {', '.join(p.authors)}\n\n"
            f"Source: {p.source_provider}; URL: {p.url or 'unavailable'}; "
            f"DOI: {p.doi or 'unavailable'}; arXiv: {p.arxiv_id or 'unavailable'}"
        )
    for c in state.claims:
        sections.append(
            f"Claim {c.id} (paper {c.paper_id}): {c.statement}\n\n"
            f"Source scope: {c.source_scope or 'unspecified'}\n\n"
            + _code(c.source_span or "No source span recorded.")
        )
    for e in state.evidence:
        sections.append(
            f"Evidence {e.id} → claim {e.claim_id}: **{e.relation.value}**\n\n"
            f"{e.summary}\n\nApplicability: {e.applicability_notes or 'unspecified'}"
        )
    if state.evidence_synthesis:
        sections.append(_code(state.evidence_synthesis.model_dump_json(indent=2), "json"))
    if state.literature_failures:
        sections.append("Provider failures:\n\n" + "\n".join(state.literature_failures))
    sections.append(
        "## HPO trials\n\n"
        + _table(
            ["Study", "Trial", "Status", "Parameters", "Metric", "Runtime (s)"],
            [
                [
                    t.study_id,
                    t.optuna_trial_number,
                    t.status.value,
                    json.dumps(t.parameters.as_dict(), sort_keys=True),
                    t.primary_metric_value,
                    t.runtime_seconds,
                ]
                for t in state.trials
                if t.study_id
            ],
        )
    )
    for study in state.studies:
        sections.append(
            f"Study {study.id}: {study.study_name}. Best trial: {study.best_trial_id}. "
            f"Sampler: {study.sampler_name}, seed {study.sampler_seed}.\n\n"
            + _code(study.search_space.model_dump_json(indent=2), "json")
        )
    sections.append("## Patches and execution provenance")
    for patch in state.patches:
        sections.append(
            f"Patch {patch.id} → hypothesis {patch.hypothesis_id}\n\n"
            f"{patch.description}\n\n" + _code(patch.diff, "diff")
        )
    for exp in state.experiments:
        sections.append(
            f"Experiment {exp.id} configuration\n\n"
            + _code(exp.config.model_dump_json(indent=2), "json")
        )
        if exp.result and exp.result.execution:
            sections.append(_code(exp.result.execution.model_dump_json(indent=2), "json"))
    sections.append(
        "## Decisions\n\n"
        + _table(
            ["Hypothesis", "Experiment / study", "Decision", "Improvement", "Reason"],
            [
                [
                    d.hypothesis_id,
                    d.experiment_id or d.study_id,
                    d.decision.value,
                    d.improvement,
                    d.reason,
                ]
                for d in state.decisions
            ],
        )
    )
    sections.append(
        "## Resources and evaluation\n\n"
        + _table(
            ["Measure", "Value"],
            [
                [key, summary[key]]
                for key in (
                    "finished_experiments",
                    "successful_experiments",
                    "tested_hypotheses",
                    "accepted_hypotheses",
                    "attempted_patches",
                    "successful_patches",
                    "runtime_seconds",
                    "elapsed_seconds",
                    "llm_calls",
                    "llm_tokens",
                    "cost_usd",
                )
            ],
        )
    )
    sections.extend(
        [
            "Execution runtime sums recorded experiments once, including baseline. Elapsed time "
            "includes pauses. Dollar cost is unknown because billing rates are not recorded. "
            "Patch success means execution succeeded, not that scientific quality improved.",
            "## Reproduction record\n\nThe JSON export includes the complete versioned snapshot, "
            "execution settings, seeds, budgets, source hashes, commands, and artifact paths. "
            "Artifact files and the original dataset/image must be retained separately. "
            "This report is derived without re-running training or calling an LLM. "
            "A matching snapshot produces an identical report. Resume continues unfinished work; "
            "it does not replay completed experiments.",
        ]
    )
    return "\n\n".join(sections) + "\n"


def research_report(state: ResearchState) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "summary": evaluate_run(state),
        "markdown": report_markdown(state),
        "state": state.model_dump(mode="json"),
    }


def benchmark(states: Sequence[ResearchState]) -> dict[str, Any]:
    unique: dict[str, ResearchState] = {}
    for state in states:
        key = str(state.research_id)
        if key in unique and fingerprint(unique[key]) != fingerprint(state):
            raise ValueError(f"Conflicting snapshots for run {key}; select one revision")
        unique[key] = state
    ordered = sorted(unique.values(), key=lambda s: str(s.research_id))
    rows = [evaluate_run(s) for s in ordered]
    cohorts: dict[str, list[dict[str, Any]]] = defaultdict(list)
    contexts: dict[str, dict[str, Any]] = {}
    baselines: dict[str, list[float]] = defaultdict(list)
    for state, row in zip(ordered, rows, strict=True):
        image_id = next(
            (
                experiment.result.execution.docker.image_id
                for experiment in state.experiments
                if experiment.result
                and experiment.result.execution
                and experiment.result.execution.docker.image_id
            ),
            None,
        )
        interventions = sorted(
            {
                json.dumps(
                    {
                        "patch_sha256": hashlib.sha256(e.config.patch_diff.encode()).hexdigest()
                        if e.config.patch_diff
                        else None,
                        "overrides": e.config.overrides.model_dump(mode="json", exclude_none=True)
                        if e.config.overrides
                        else None,
                    },
                    sort_keys=True,
                )
            for e in state.experiments
            if e.purpose == ExperimentPurpose.CANDIDATE
            }
        )
        context = {
            "executor": row["executor"],
            "dataset": row["dataset"],
            "metric_name": row["metric_name"],
            "direction": row["direction"],
            "base_commit": state.execution.base_commit_sha,
            "repository": str(state.execution.baseline_repo_path),
            "image": image_id or state.execution.image,
            "command": list(state.execution.training_command),
            "intervention_sha256": hashlib.sha256(json.dumps(interventions).encode()).hexdigest(),
            "min_delta": state.baseline.min_delta,
            "regression_delta": state.baseline.regression_delta,
            "max_experiments": state.budget.max_experiments,
            "max_hpo_trials": state.budget.max_hpo_trials,
        }
        key = hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()[:16]
        cohorts[key].append(row)
        contexts[key] = context
        if row["baseline"] is not None:
            baselines[key].append(row["baseline"])
    groups = []
    for key, cohort in sorted(cohorts.items()):
        strategies = []
        for strategy in sorted({row["strategy"] for row in cohort}):
            selected = [r for r in cohort if r["strategy"] == strategy]
            completed = [r for r in selected if r["status"] == RunStatus.COMPLETED.value]
            improvements = [r["improvement"] for r in completed if r["improvement"] is not None]
            terminal = sum(r["finished_experiments"] for r in selected)
            hypotheses = sum(r["tested_hypotheses"] for r in selected)
            patches = sum(r["attempted_patches"] for r in selected)
            strategies.append(
                {
                    "strategy": strategy,
                    "runs": len(selected),
                    "completed": len(completed),
                    "measured_runs": len(improvements),
                    "keep_rate": sum(r["decision"] == "KEEP" for r in completed) / len(completed)
                    if completed
                    else None,
                    "mean_improvement": mean(improvements) if improvements else None,
                    "std_improvement": stdev(improvements) if len(improvements) > 1 else None,
                    "experiment_success_rate": sum(r["successful_experiments"] for r in selected)
                    / terminal
                    if terminal
                    else None,
                    "hypothesis_acceptance_rate": sum(r["accepted_hypotheses"] for r in selected)
                    / hypotheses
                    if hypotheses
                    else None,
                    "patch_execution_success_rate": sum(r["successful_patches"] for r in selected)
                    / patches
                    if patches
                    else None,
                    "llm_tokens": sum(r["llm_tokens"] for r in selected),
                    "runtime_seconds": sum(r["runtime_seconds"] or 0 for r in selected)
                    if all(r["runtime_seconds"] is not None for r in selected)
                    else None,
                }
            )
        baseline_values = baselines[key]
        group_context = {
            **contexts[key],
            "baseline": mean(baseline_values) if baseline_values else None,
            "baseline_min": min(baseline_values) if baseline_values else None,
            "baseline_max": max(baseline_values) if baseline_values else None,
        }
        groups.append({"id": key, "context": group_context, "strategies": strategies})
    return {
        "schema_version": 1,
        "runs": rows,
        "groups": groups,
        "limitations": [
            "Observational comparison, not a causal estimate of literature grounding "
            "or model quality.",
            "Cohorts match executor, repository, commit, image digest/reference, command, "
            "intervention, objective, baseline, thresholds and experiment/HPO budgets. "
            "Baseline values may vary across seeds; "
            "improvement is paired against each run’s own baseline. "
            "Verify dataset versions and image digests manually.",
            "Only completed runs with measured candidates enter improvement statistics. "
            "Missing measurements are not zero. Simulations are separate from real execution.",
            "Token counts and execution seconds are resource measures; "
            "dollar cost is not recorded.",
        ],
    }


def benchmark_markdown(data: dict[str, Any]) -> str:
    sections = ["# LabPilot benchmark", "\n\n".join(data["limitations"])]
    for group in data["groups"]:
        sections.append(
            f"## Cohort {group['id']}\n\n" + _code(json.dumps(group["context"], indent=2), "json")
        )
        columns = [
            "strategy",
            "runs",
            "completed",
            "measured_runs",
            "keep_rate",
            "mean_improvement",
            "std_improvement",
            "experiment_success_rate",
            "hypothesis_acceptance_rate",
            "patch_execution_success_rate",
            "llm_tokens",
            "runtime_seconds",
        ]
        sections.append(_table(columns, [[r[k] for k in columns] for r in group["strategies"]]))
    sections.append(
        "## Source snapshots\n\n"
        + _table(
            ["Run", "Seed", "Revision", "SHA-256"],
            [
                [r["research_id"], r["seed"], r["revision"], r["snapshot_sha256"]]
                for r in data["runs"]
            ],
        )
    )
    return "\n\n".join(sections) + "\n"
