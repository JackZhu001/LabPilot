"""Human-readable and JSON study views derived from the authoritative snapshot."""

import json
from pathlib import Path

from labpilot.hpo.models import OptimizationStudy
from labpilot.models.state import ResearchState


def study_summary(state: ResearchState, study: OptimizationStudy) -> dict[str, object]:
    trials = tuple(t for t in state.trials if t.study_id == study.id)
    best = next((t for t in trials if t.id == study.best_trial_id), None)
    decision = next((d for d in reversed(state.decisions) if d.study_id == study.id), None)
    return {
        "study": study.model_dump(mode="json"),
        "trials": [t.model_dump(mode="json") for t in trials],
        "best": best.model_dump(mode="json") if best else None,
        "baseline": state.baseline.model_dump(mode="json"),
        "decision": decision.model_dump(mode="json") if decision else None,
        "total_trial_runtime_seconds": sum(t.runtime_seconds for t in trials),
    }


def export_studies(state: ResearchState) -> tuple[Path, ...]:
    """Reports are regenerable views, never a second resume source of truth."""
    paths = []
    for study in state.studies:
        path = study.storage_path.parent / "study.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(study_summary(state, study), indent=2, allow_nan=False) + "\n"
        )
        temporary.replace(path)
        paths.append(path)
    return tuple(paths)


def format_studies(state: ResearchState) -> str:
    lines: list[str] = []
    for study in state.studies:
        lines.extend(
            (
                f"Study ID: {study.id}",
                f"Hypothesis: {study.hypothesis_id}",
                f"Objective: {study.primary_metric} ({study.direction.value})",
                f"Study status: {study.status.value}",
                "Trial | Status | Parameters | Metric | Runtime",
            )
        )
        trials = [t for t in state.trials if t.study_id == study.id]
        for trial in trials:
            params = json.dumps(trial.parameters.as_dict(), sort_keys=True)
            lines.append(
                f"{trial.optuna_trial_number} | {trial.status.value} | {params} | "
                f"{trial.primary_metric_value} | {trial.runtime_seconds:.3f}s"
            )
        best = next((t for t in trials if t.id == study.best_trial_id), None)
        lines.append(f"Best trial: {best.optuna_trial_number if best else 'none'}")
        lines.append(f"Baseline: {state.baseline.value}")
        if best and best.primary_metric_value is not None:
            lines.append(f"Best metric: {best.primary_metric_value}")
            lines.append(f"Raw delta: {best.primary_metric_value - state.baseline.value:+.6f}")
        lines.append(f"Total trial runtime: {sum(t.runtime_seconds for t in trials):.3f}s")
    return "\n".join(lines)
