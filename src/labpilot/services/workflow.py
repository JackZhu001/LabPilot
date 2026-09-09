"""Research transitions independent of LangGraph, SQLAlchemy, and the CLI."""

import logging
from uuid import uuid5

from labpilot.decisions.engine import DecisionEngine
from labpilot.models.common import (
    ExperimentStatus,
    HypothesisStatus,
    ResearchDecision,
    RunStatus,
    Step,
)
from labpilot.models.execution import ExecutionEnvironment, ExperimentPurpose
from labpilot.models.experiments import (
    Experiment,
    ExperimentConfig,
    ExperimentResult,
    Metric,
    Trial,
)
from labpilot.models.state import DecisionRecord, ResearchState
from labpilot.services.interfaces import ResearchServices
from labpilot.services.real import execute_real_experiment

logger = logging.getLogger(__name__)


class ResearchWorkflow:
    """One cohesive transition per step; callers handle storage and orchestration."""

    def __init__(self, services: ResearchServices, engine: DecisionEngine | None = None) -> None:
        self.services = services
        self.engine = engine or DecisionEngine()

    def advance(self, state: ResearchState, step: Step) -> ResearchState:
        if state.next_step != step or step == Step.END:
            raise ValueError(f"Cannot execute {step} from cursor {state.next_step}")
        handlers = {
            Step.LITERATURE: self.literature,
            Step.EVIDENCE: self.evidence,
            Step.BASELINE: self.baseline,
            Step.HYPOTHESIS: self.hypothesis,
            Step.EXPERIMENT: self.experiment,
            Step.ANALYZE: self.analyze,
            Step.DECISION: self.decision,
        }
        return handlers[step](state)

    def literature(self, state: ResearchState) -> ResearchState:
        papers = self.services.literature.retrieve(state.research_id, state.research_goal)
        return state.evolve(papers=papers, next_step=Step.EVIDENCE)

    def evidence(self, state: ResearchState) -> ResearchState:
        claims, evidence = self.services.evidence.extract(state.papers)
        return state.evolve(
            claims=claims,
            evidence=evidence,
            next_step=(
                Step.BASELINE
                if state.execution.environment == ExecutionEnvironment.DOCKER
                else Step.HYPOTHESIS
            ),
        )

    def baseline(self, state: ResearchState) -> ResearchState:
        if not state.budget.can_continue():
            return self.finish(state, "Budget exhausted before baseline execution")
        return execute_real_experiment(state, self.services, purpose=ExperimentPurpose.BASELINE)

    def hypothesis(self, state: ResearchState) -> ResearchState:
        if not state.budget.can_continue():
            return self.finish(state, "Research budget exhausted before a new iteration")
        hypothesis = self.services.hypothesis.generate(
            state.research_id, state.research_goal, state.evidence, state.iteration + 1
        )
        logger.info(
            "hypothesis_generated research_id=%s hypothesis_id=%s", state.research_id, hypothesis.id
        )
        return state.evolve(
            hypotheses=(*state.hypotheses, hypothesis),
            active_hypothesis_id=hypothesis.id,
            iteration=state.iteration + 1,
            budget=state.budget.consume(iterations=1),
            next_step=Step.EXPERIMENT,
        )

    def experiment(self, state: ResearchState) -> ResearchState:
        if not state.budget.can_run_experiment():
            return self.finish(state, "Experiment budget exhausted")
        if state.active_hypothesis_id is None:
            raise ValueError("Experiment requires an active hypothesis")
        if state.execution.environment == ExecutionEnvironment.DOCKER:
            return execute_real_experiment(
                state, self.services, purpose=ExperimentPurpose.CANDIDATE
            )
        experiment = Experiment(
            id=uuid5(state.research_id, f"experiment:{state.iteration}"),
            hypothesis_id=state.active_hypothesis_id,
            sequence=state.budget.experiments + 1,
            config=ExperimentConfig(
                seed=state.simulation.seed, metric_name=state.baseline.metric_name
            ),
            status=ExperimentStatus.RUNNING,
        )
        # Unexpected provider exceptions propagate. The last durable cursor remains retryable.
        result = self.services.experiment.run(experiment, state.baseline)
        experiment = Experiment.model_validate(
            {
                **experiment.model_dump(),
                "status": result.status,
                "error": result.error,
            }
        )
        trial = Trial(
            id=uuid5(experiment.id, "trial:0"),
            experiment_id=experiment.id,
            seed=experiment.config.seed,
            status=result.status,
        )
        metrics = state.metrics
        if result.value is not None:
            metrics = (
                *metrics,
                Metric(
                    id=uuid5(trial.id, "metric:0"),
                    experiment_id=experiment.id,
                    trial_id=trial.id,
                    name=state.baseline.metric_name,
                    value=result.value,
                ),
            )
        logger.info(
            "experiment_finished research_id=%s hypothesis_id=%s experiment_id=%s status=%s",
            state.research_id,
            experiment.hypothesis_id,
            experiment.id,
            result.status,
        )
        return state.evolve(
            experiments=(*state.experiments, experiment),
            trials=(*state.trials, trial),
            metrics=metrics,
            budget=state.budget.consume(
                experiments=1, failed_experiments=int(result.status == ExperimentStatus.FAILED)
            ),
            next_step=Step.ANALYZE,
        )

    def analyze(self, state: ResearchState) -> ResearchState:
        if not state.experiments:
            raise ValueError("Analysis requires an experiment")
        experiment = state.experiments[-1]
        metric = next(
            (
                item
                for item in state.metrics
                if item.experiment_id == experiment.id and item.name == state.baseline.metric_name
            ),
            None,
        )
        result = ExperimentResult(
            status=experiment.status, error=experiment.error, value=metric.value if metric else None
        )
        assessment = self.engine.decide(result, state.baseline, state.budget)
        record = DecisionRecord(
            experiment_id=experiment.id,
            hypothesis_id=experiment.hypothesis_id,
            **assessment.model_dump(),
        )
        return state.evolve(
            decision=record.decision, decisions=(*state.decisions, record), next_step=Step.DECISION
        )

    def decision(self, state: ResearchState) -> ResearchState:
        if state.decision is None:
            raise ValueError("Decision step requires analysis")
        status = {
            ResearchDecision.KEEP: HypothesisStatus.ACCEPTED,
            ResearchDecision.REJECT: HypothesisStatus.REJECTED,
            ResearchDecision.REPLAN: HypothesisStatus.REPLANNED,
        }[state.decision]
        hypotheses = tuple(
            type(item).model_validate({**item.model_dump(), "status": status})
            if item.id == state.active_hypothesis_id
            else item
            for item in state.hypotheses
        )
        state = state.evolve(hypotheses=hypotheses)
        if state.decision == ResearchDecision.REPLAN and state.budget.can_replan():
            next_step = (
                Step.BASELINE
                if state.experiments[-1].purpose == ExperimentPurpose.BASELINE
                else Step.HYPOTHESIS
            )
            return state.evolve(budget=state.budget.consume(replans=1), next_step=next_step)
        return self.finish(state, state.decisions[-1].reason)

    @staticmethod
    def finish(state: ResearchState, reason: str) -> ResearchState:
        return state.evolve(
            status=RunStatus.COMPLETED, next_step=Step.END, termination_reason=reason
        )
