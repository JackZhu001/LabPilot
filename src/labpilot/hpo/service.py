"""Small checkpointable HPO transitions; execution stays behind ExperimentRunner."""

import logging
import time
from uuid import uuid5

from pydantic import ValidationError

from labpilot.hpo.mapper import experiment_config
from labpilot.hpo.models import ExperimentPlan, OptimizationStudy, StudyStatus, TrialStatus
from labpilot.hpo.optuna import PersistentStudy
from labpilot.hpo.selection import select_best
from labpilot.models.common import ExperimentStatus, Step, utc_now
from labpilot.models.experiments import (
    CodePatch,
    Experiment,
    ExperimentConfig,
    ExperimentResult,
    Metric,
    Trial,
)
from labpilot.models.state import ResearchState
from labpilot.services.interfaces import ExperimentRunner

logger = logging.getLogger(__name__)


def active_study(state: ResearchState) -> OptimizationStudy:
    return next(study for study in state.studies if study.id == state.active_study_id)


def study_trials(state: ResearchState) -> tuple[Trial, ...]:
    return tuple(t for t in state.trials if t.study_id == state.active_study_id)


def replace_study(
    state: ResearchState, study: OptimizationStudy, **changes: object
) -> ResearchState:
    return state.evolve(
        studies=tuple(study if s.id == study.id else s for s in state.studies), **changes
    )


class HPOService:
    def __init__(self, runner: ExperimentRunner) -> None:
        self.runner = runner

    def plan(self, state: ResearchState) -> ResearchState:
        if state.hpo is None or state.active_hypothesis_id is None:
            raise ValueError("HPO requires a hypothesis and search configuration")
        identity = uuid5(state.active_hypothesis_id, "study")
        patch = CodePatch(
            id=uuid5(identity, "patch"),
            hypothesis_id=state.active_hypothesis_id,
            base_commit_sha=state.execution.base_commit_sha,
            description="Fixed outer-loop patch shared by all study trials",
            diff=state.execution.patch_diff,
        )
        plan = ExperimentPlan(
            id=uuid5(identity, "plan"),
            hypothesis_id=state.active_hypothesis_id,
            patch_id=patch.id,
            search_space=state.hpo.search_space,
            primary_metric=state.baseline.metric_name,
            direction=state.baseline.direction,
            max_trials=state.hpo.max_trials,
        )
        study = OptimizationStudy(
            id=identity,
            research_id=state.research_id,
            hypothesis_id=state.active_hypothesis_id,
            plan_id=plan.id,
            study_name=f"labpilot-{identity}",
            search_space=plan.search_space,
            storage_path=state.execution.runtime_root.resolve()
            / "runs"
            / str(state.research_id)
            / "studies"
            / str(identity)
            / "optuna.sqlite3",
            primary_metric=plan.primary_metric,
            direction=plan.direction,
            max_trials=plan.max_trials,
            sampler_seed=state.hpo.sampler_seed,
        )
        with PersistentStudy(study):
            pass
        return state.evolve(
            plans=(*state.plans, plan),
            studies=(*state.studies, study),
            patches=(*state.patches, patch),
            active_study_id=identity,
            next_step=Step.HPO_SUGGEST,
        )

    def suggest(self, state: ResearchState) -> ResearchState:
        study = active_study(state)
        existing = study_trials(state)
        if len(existing) >= study.max_trials or not state.budget.can_run_hpo_trial():
            return self.finish(state)
        with PersistentStudy(study, len(existing)) as adapter:
            number, parameters = adapter.suggest(len(existing))
        trial_id = uuid5(study.id, f"trial:{number}")
        experiment_id = uuid5(trial_id, "experiment")
        plan = next(plan for plan in state.plans if plan.id == study.plan_id)
        experiment = Experiment(
            id=experiment_id,
            research_id=state.research_id,
            hypothesis_id=study.hypothesis_id,
            patch_id=plan.patch_id,
            sequence=state.budget.experiments + 1,
            config=ExperimentConfig(
                seed=state.simulation.seed,
                metric_name=study.primary_metric,
                direction=study.direction,
            ),
        )
        trial = Trial(
            id=trial_id,
            experiment_id=experiment_id,
            study_id=study.id,
            research_id=state.research_id,
            hypothesis_id=study.hypothesis_id,
            optuna_trial_number=number,
            parameters=parameters,
            seed=experiment.config.seed,
            primary_metric_name=study.primary_metric,
            status=TrialStatus.PENDING,
            created_at=utc_now(),
        )
        return state.evolve(
            trials=(*state.trials, trial),
            experiments=(*state.experiments, experiment),
            budget=state.budget.consume(experiments=1, hpo_trials=1),
            next_step=Step.HPO_EXECUTE,
        )

    def execute_trial(self, state: ResearchState) -> ResearchState:
        trial = study_trials(state)[-1]
        experiment = next(e for e in state.experiments if e.id == trial.experiment_id)
        if experiment.result is not None:
            return state.evolve(next_step=Step.HPO_SYNC)
        started, timer = utc_now(), time.monotonic()
        context = (
            state.research_id,
            trial.study_id,
            trial.id,
            experiment.id,
            trial.optuna_trial_number,
        )
        logger.info(
            "trial_started research_id=%s study_id=%s trial_id=%s "
            "experiment_id=%s optuna_trial_number=%s",
            *context,
        )
        try:
            config = experiment_config(experiment.config, trial.parameters)
        except ValidationError as exc:
            result = ExperimentResult(
                status=ExperimentStatus.FAILED, error=f"Invalid trial configuration: {exc}"
            )
        else:
            experiment = Experiment.model_validate(
                {**experiment.model_dump(), "config": config, "status": ExperimentStatus.RUNNING}
            )
            result = self.runner.run(experiment, state.baseline)
        ended = utc_now()
        experiment = Experiment.model_validate(
            {
                **experiment.model_dump(),
                "result": result,
                "status": result.status,
                "error": result.error,
            }
        )
        trial = Trial.model_validate(
            {
                **trial.model_dump(),
                "status": result.status.value,
                "primary_metric_value": result.value,
                "failure_reason": result.error,
                "started_at": started,
                "finished_at": ended,
                "runtime_seconds": time.monotonic() - timer,
            }
        )
        metrics = state.metrics
        if result.value is not None:
            values = (
                result.execution.report.metrics
                if result.execution and result.execution.report
                else {state.baseline.metric_name: result.value}
            )
            metrics = (
                *metrics,
                *(
                    Metric(
                        id=uuid5(trial.id, name),
                        trial_id=trial.id,
                        experiment_id=experiment.id,
                        name=name,
                        value=value,
                    )
                    for name, value in values.items()
                ),
            )
        trials = tuple(trial if t.id == trial.id else t for t in state.trials)
        members = tuple(t for t in trials if t.study_id == trial.study_id)
        study = active_study(state)
        best = select_best(members, study.direction)
        if best is not None and best.id != study.best_trial_id:
            logger.info(
                "best_trial_updated research_id=%s study_id=%s trial_id=%s",
                state.research_id,
                study.id,
                best.id,
            )
        updated_study = OptimizationStudy.model_validate(
            {
                **study.model_dump(),
                "completed_trials": sum(t.status == TrialStatus.SUCCEEDED for t in members),
                "failed_trials": sum(t.status == TrialStatus.FAILED for t in members),
                "pruned_trials": sum(t.status == TrialStatus.PRUNED for t in members),
                "best_trial_id": best.id if best else None,
                "updated_at": utc_now(),
            }
        )
        state = state.evolve(
            experiments=tuple(
                experiment if e.id == experiment.id else e for e in state.experiments
            ),
            trials=trials,
            studies=tuple(
                updated_study if item.id == updated_study.id else item for item in state.studies
            ),
            metrics=metrics,
            budget=state.budget.consume(
                failed_experiments=int(result.status == ExperimentStatus.FAILED)
            ),
            next_step=Step.HPO_SYNC,
        )
        logger.info(
            "trial_%s research_id=%s study_id=%s trial_id=%s "
            "experiment_id=%s optuna_trial_number=%s",
            "completed" if result.status == ExperimentStatus.SUCCEEDED else "failed",
            *context,
        )
        return state

    def refresh(self, state: ResearchState) -> ResearchState:
        study, trials = active_study(state), study_trials(state)
        best = select_best(trials, study.direction)
        if best is not None and best.id != study.best_trial_id:
            logger.info(
                "best_trial_updated research_id=%s study_id=%s trial_id=%s",
                state.research_id,
                study.id,
                best.id,
            )
        updated = OptimizationStudy.model_validate(
            {
                **study.model_dump(),
                "completed_trials": sum(t.status == TrialStatus.SUCCEEDED for t in trials),
                "failed_trials": sum(t.status == TrialStatus.FAILED for t in trials),
                "pruned_trials": sum(t.status == TrialStatus.PRUNED for t in trials),
                "best_trial_id": best.id if best else None,
                "updated_at": utc_now(),
            }
        )
        return replace_study(state, updated)

    def synchronize(self, state: ResearchState) -> ResearchState:
        study = active_study(state)
        logger.info("study_resumed research_id=%s study_id=%s", state.research_id, study.id)
        with PersistentStudy(study) as adapter:
            adapter.synchronize(study_trials(state)[-1])
        if len(study_trials(state)) >= study.max_trials or not state.budget.can_run_hpo_trial():
            return self.finish(state)
        return state.evolve(next_step=Step.HPO_SUGGEST)

    def finish(self, state: ResearchState) -> ResearchState:
        state = self.refresh(state)
        study = active_study(state)
        if not state.budget.can_run_hpo_trial():
            logger.info("budget_exhausted research_id=%s study_id=%s", state.research_id, study.id)
        updated = OptimizationStudy.model_validate(
            {
                **study.model_dump(),
                "status": StudyStatus.SUCCEEDED if study.best_trial_id else StudyStatus.FAILED,
                "failure_reason": None
                if study.best_trial_id
                else "No successful trial within available budget",
            }
        )
        return replace_study(state, updated, next_step=Step.ANALYZE)
