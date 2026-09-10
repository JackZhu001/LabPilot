"""Research transitions independent of LangGraph, SQLAlchemy, and the CLI."""

import logging
from collections.abc import Callable
from uuid import uuid5

from labpilot.agent.service import AgentLoopService
from labpilot.decisions.engine import DecisionEngine
from labpilot.hpo.models import TrialStatus
from labpilot.hpo.selection import select_best
from labpilot.hpo.service import HPOService, active_study, study_trials
from labpilot.literature.agent import LiteratureAgentService
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
        hpo = HPOService(self.services.experiment)
        agent = AgentLoopService(self.services.llm) if self.services.llm is not None else None
        literature_agent = (
            LiteratureAgentService(self.services)
            if self.services.llm is not None and state.literature_settings.enabled
            else None
        )

        def agent_handler(name: str) -> Callable[[ResearchState], ResearchState]:
            def run(current: ResearchState) -> ResearchState:
                if agent is None:
                    raise ValueError(f"{name} requires an LLM service")
                handler: Callable[[ResearchState], ResearchState] = getattr(agent, name)
                return handler(current)

            return run

        handlers = {
            Step.INSPECT_REPOSITORY: agent_handler("inspect_repository"),
            Step.PLAN_LITERATURE_QUERIES: literature_agent.plan_queries
            if literature_agent
            else self._missing_literature,
            Step.RETRIEVE_PAPERS: literature_agent.retrieve_papers
            if literature_agent
            else self._missing_literature,
            Step.EXTRACT_CLAIMS: literature_agent.extract_claims
            if literature_agent
            else self._missing_literature,
            Step.SYNTHESIZE_EVIDENCE: literature_agent.synthesize_evidence
            if literature_agent
            else self._missing_literature,
            Step.GENERATE_HYPOTHESES: agent_handler("generate_hypotheses"),
            Step.PLAN_EXPERIMENT: agent_handler("plan_experiment"),
            Step.GENERATE_PATCH: agent_handler("generate_patch"),
            Step.CRITIQUE: agent_handler("critique"),
            Step.HPO_PLAN: hpo.plan,
            Step.HPO_SUGGEST: hpo.suggest,
            Step.HPO_EXECUTE: hpo.execute_trial,
            Step.HPO_SYNC: hpo.synchronize,
            Step.LITERATURE: self.literature,
            Step.EVIDENCE: self.evidence,
            Step.BASELINE: self.baseline,
            Step.HYPOTHESIS: self.hypothesis,
            Step.EXPERIMENT: self.experiment,
            Step.ANALYZE: self.analyze,
            Step.DECISION: self.decision,
        }
        return handlers[step](state)

    @staticmethod
    def _missing_literature(state: ResearchState) -> ResearchState:
        del state
        raise ValueError("Literature steps require enabled settings and an LLM service")

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
            next_step=Step.HPO_PLAN if state.hpo else Step.EXPERIMENT,
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
            status=TrialStatus(result.status.value),
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
        if state.hpo and state.active_study_id is not None:
            return self.analyze_study(state)
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
            decision=record.decision,
            decisions=(*state.decisions, record),
            next_step=(
                Step.CRITIQUE
                if state.llm and state.active_hypothesis_id is not None
                else Step.DECISION
            ),
        )

    def analyze_study(self, state: ResearchState) -> ResearchState:
        study = active_study(state)
        trials = study_trials(state)
        best = select_best(trials, study.direction)
        if best is None:
            result = ExperimentResult(
                status=ExperimentStatus.FAILED,
                error=study.failure_reason or "Study has no successful trials",
            )
        else:
            result = ExperimentResult(
                status=ExperimentStatus.SUCCEEDED, value=best.primary_metric_value
            )
        budget = state.budget
        if not budget.can_run_hpo_trial():
            # Disable retries only; numerical comparison remains entirely in DecisionEngine.
            budget = budget.model_copy(update={"max_replans": budget.replans})
        assessment = self.engine.decide(result, state.baseline, budget)
        selected = best or (trials[-1] if trials else None)
        record = DecisionRecord(
            experiment_id=selected.experiment_id if selected else None,
            hypothesis_id=study.hypothesis_id,
            study_id=study.id,
            **assessment.model_dump(),
        )
        return state.evolve(
            decision=record.decision,
            decisions=(*state.decisions, record),
            next_step=Step.CRITIQUE if state.llm else Step.DECISION,
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
                if state.decisions[-1].study_id is None
                and state.experiments[-1].purpose == ExperimentPurpose.BASELINE
                else Step.GENERATE_HYPOTHESES
                if state.llm
                else Step.HYPOTHESIS
            )
            return state.evolve(budget=state.budget.consume(replans=1), next_step=next_step)
        return self.finish(state, state.decisions[-1].reason)

    @staticmethod
    def finish(state: ResearchState, reason: str) -> ResearchState:
        return state.evolve(
            status=RunStatus.COMPLETED, next_step=Step.END, termination_reason=reason
        )
