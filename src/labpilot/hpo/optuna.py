"""Persistent ask/tell adapter with explicit ownership and idempotent synchronization."""

from types import TracebackType
from typing import Self

import optuna
from optuna.samplers import TPESampler
from optuna.storages import RDBStorage
from optuna.trial import TrialState
from sqlalchemy.engine import URL

from labpilot.hpo.mapper import OptunaParameterMapper
from labpilot.hpo.models import OptimizationStudy, TrialStatus
from labpilot.hpo.search_space import SampledParameters
from labpilot.models.experiments import Trial


class StudyConflictError(RuntimeError):
    """The two linked stores disagree; refuse to invent or overwrite outcomes."""


class PersistentStudy:
    """Optuna owns suggestions; LabPilot owns execution results and budget charges.

    A fresh deterministic sampler is constructed for each trial number. This avoids
    relying on an in-memory RNG state that RDBStorage does not persist.
    """

    def __init__(self, metadata: OptimizationStudy, next_number: int = 0) -> None:
        metadata.storage_path.parent.mkdir(parents=True, exist_ok=True)
        url = URL.create("sqlite", database=str(metadata.storage_path)).render_as_string(
            hide_password=False
        )
        self.storage = RDBStorage(url)
        self.metadata = metadata
        self.study = optuna.create_study(
            study_name=metadata.study_name,
            storage=self.storage,
            load_if_exists=True,
            direction=metadata.direction.value.lower(),
            sampler=TPESampler(
                seed=(metadata.sampler_seed + next_number) % 2**32,
                n_startup_trials=metadata.startup_trials,
            ),
            pruner=optuna.pruners.NopPruner(),
        )
        if self.study.direction.name != metadata.direction.value:
            self.close()
            raise StudyConflictError("Optuna study direction changed")
        identity = self.study.user_attrs.get("labpilot_study_id")
        if identity is not None and identity != str(metadata.id):
            self.close()
            raise StudyConflictError("Optuna study identity does not match LabPilot")
        self.study.set_user_attr("labpilot_study_id", str(metadata.id))

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self.storage.remove_session()
        self.storage.engine.dispose()

    def suggest(self, expected_number: int) -> tuple[int, SampledParameters]:
        trials = self.study.get_trials(deepcopy=False)
        if len(trials) == expected_number:
            trial = self.study.ask()
        elif len(trials) == expected_number + 1 and trials[-1].state == TrialState.RUNNING:
            # Adopt an ask that committed before the LabPilot reservation checkpoint.
            study_id = self.storage.get_study_id_from_name(self.metadata.study_name)
            identity = self.storage.get_trial_id_from_study_id_trial_number(
                study_id, expected_number
            )
            trial = optuna.trial.Trial(self.study, identity)
        else:
            raise StudyConflictError("Unexpected Optuna trials; reconcile the linked study")
        if trial.number != expected_number:
            raise StudyConflictError("Optuna trial numbering changed")
        return trial.number, OptunaParameterMapper().sample(self.metadata.search_space, trial)

    def synchronize(self, record: Trial) -> None:
        if record.optuna_trial_number is None:
            raise StudyConflictError("Missing Optuna trial number")
        trials = self.study.get_trials(deepcopy=False)
        if record.optuna_trial_number >= len(trials):
            raise StudyConflictError("Persisted Optuna suggestion is missing")
        frozen = trials[record.optuna_trial_number]
        if frozen.params != record.parameters.as_dict():
            raise StudyConflictError("Optuna parameters differ from the persisted trial")
        target = {
            TrialStatus.SUCCEEDED: TrialState.COMPLETE,
            TrialStatus.FAILED: TrialState.FAIL,
            TrialStatus.PRUNED: TrialState.PRUNED,
        }.get(record.status)
        if target is None:
            raise StudyConflictError("Cannot synchronize a nonterminal trial")
        if frozen.state.is_finished():
            if frozen.state != target or frozen.value != record.primary_metric_value:
                raise StudyConflictError("Optuna outcome differs from the authoritative result")
            return
        self.study.tell(
            record.optuna_trial_number,
            record.primary_metric_value if target == TrialState.COMPLETE else None,
            state=target,
        )
