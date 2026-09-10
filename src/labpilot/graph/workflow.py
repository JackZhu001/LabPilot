"""Thin LangGraph nodes checkpoint each successful domain transition."""

import logging
from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from labpilot.hpo.reporting import export_studies
from labpilot.llm.errors import (
    LLMAuthenticationError,
    LLMBudgetError,
    LLMConfigurationError,
    LLMError,
    LLMTransientError,
)
from labpilot.models.common import RunStatus, Step
from labpilot.models.state import ResearchState
from labpilot.persistence.repository import ResearchRepository
from labpilot.services.interfaces import ResearchServices
from labpilot.services.real import services_for
from labpilot.services.workflow import ResearchWorkflow

logger = logging.getLogger(__name__)


class GraphState(TypedDict):
    research: ResearchState
    completed_steps: int


def route_next(state: GraphState) -> str:
    """Route from the durable cursor; paused/completed runs end this invocation."""
    research = state["research"]
    if research.status in {
        RunStatus.PAUSED,
        RunStatus.COMPLETED,
        RunStatus.BLOCKED,
        RunStatus.FAILED,
    }:
        return END
    return research.next_step.value


def execute(
    repository: ResearchRepository,
    research_id: UUID,
    *,
    stop_after: int | None = None,
    services: ResearchServices | None = None,
) -> ResearchState:
    """Execute or resume a stored run, optionally stopping after N committed steps.

    A step exception leaves the last committed cursor unchanged. Call again to retry.
    Completed runs are idempotent no-ops. Budgets, scenario and cursor survive restart;
    completed_steps is deliberately invocation-local.
    """
    if stop_after is not None and stop_after < 1:
        raise ValueError("stop_after must be positive")
    research = repository.load(research_id)
    if research.status in {RunStatus.COMPLETED, RunStatus.FAILED}:
        return research
    research = research.evolve(status=RunStatus.RUNNING, termination_reason=None)
    try:
        resolved_services = services or services_for(research)
    except LLMError as exc:
        return repository.save(
            research.evolve(status=RunStatus.BLOCKED, termination_reason=str(exc))
        )
    workflow = ResearchWorkflow(resolved_services)

    graph = StateGraph(GraphState)

    def add_node(step: Step) -> None:
        def run(state: GraphState) -> GraphState:
            try:
                updated = workflow.advance(state["research"], step)
            except LLMError as exc:
                current = state["research"]
                if exc.usages:
                    calls = len(exc.usages)
                    tokens = sum(item.total_tokens for item in exc.usages)
                    current = current.evolve(
                        llm_usage=(*current.llm_usage, *exc.usages),
                        budget=current.budget.consume(llm_calls=calls, llm_tokens=tokens),
                    )
                retryable = isinstance(
                    exc,
                    (
                        LLMAuthenticationError,
                        LLMBudgetError,
                        LLMConfigurationError,
                        LLMTransientError,
                    ),
                )
                updated = current.evolve(
                    status=RunStatus.BLOCKED if retryable else RunStatus.FAILED,
                    next_step=current.next_step if retryable else Step.END,
                    termination_reason=str(exc),
                )
            count = state["completed_steps"] + 1
            if (
                stop_after is not None
                and count >= stop_after
                and updated.next_step != Step.END
                and updated.status == RunStatus.RUNNING
            ):
                updated = updated.evolve(status=RunStatus.PAUSED)
            updated = repository.save(updated)
            if updated.studies:
                export_studies(updated)
            logger.info(
                "checkpoint research_id=%s step=%s next_step=%s revision=%s",
                updated.research_id,
                step.value,
                updated.next_step.value,
                updated.revision,
            )
            return {"research": updated, "completed_steps": count}

        graph.add_node(step.value, run)

    routes = [step.value for step in Step if step != Step.END] + [END]
    graph.add_conditional_edges(START, route_next, routes)
    for step in Step:
        if step == Step.END:
            continue
        add_node(step)
        graph.add_conditional_edges(step.value, route_next, routes)
    compiled = graph.compile()
    # Two source steps plus at most four steps per iteration; allow a final budget guard.
    result = compiled.invoke(
        {"research": research, "completed_steps": 0},
        config={
            "recursion_limit": 4 * research.budget.max_iterations
            + 3 * research.budget.max_experiments
            + 3 * research.budget.max_hpo_trials
            + research.budget.max_papers
            + research.budget.max_literature_queries
            + 10
        },
    )
    return ResearchState.model_validate(result["research"])
