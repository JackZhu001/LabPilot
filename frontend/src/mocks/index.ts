/**
 * Mock data index. All fixture data lives here; only the API service
 * (src/services/labpilot-api.ts) imports from this module. Components
 * must never import fixtures directly.
 */
import type { RawState, ResearchRun, RunSummary } from "@/types/domain";
import { activityEvents } from "./activity";
import { fakeReplanRun, fakeRunningRun } from "./run-fake";
import { hpoPreviewRun } from "./run-hpo";
import { dropoutKeepRun } from "./run-dropout-keep";

export const runs: ResearchRun[] = [dropoutKeepRun, hpoPreviewRun, fakeReplanRun, fakeRunningRun];

export function summarize(run: ResearchRun): RunSummary {
  const succeeded = run.experiments.filter((e) => e.status === "SUCCEEDED");
  const candidateValues = succeeded
    .filter((e) => e.purpose === "CANDIDATE")
    .map((e) => e.metric_value ?? 0);
  const best =
    run.baseline.direction === "MAXIMIZE"
      ? Math.max(run.baseline.value, ...candidateValues)
      : Math.min(run.baseline.value, ...candidateValues);
  const bestIsBaseline = !candidateValues.some((v) =>
    run.baseline.direction === "MAXIMIZE" ? v >= best : v <= best,
  );
  return {
    research_id: run.research_id,
    goal: run.goal,
    status: run.status,
    decision: run.decision,
    iteration: run.iteration,
    executor: run.executor,
    baseline_metric: run.baseline.value,
    best_metric: run.status === "READY" || run.experiments.length === 0 ? null : bestIsBaseline ? run.baseline.value : best,
    delta:
      run.experiments.length === 0 || bestIsBaseline ? null : best - run.baseline.value,
    experiment_count: run.experiments.length,
    failed_experiments: run.budget.failed_experiments,
    created_at: run.created_at,
    updated_at: run.updated_at,
  };
}

export function toRawState(run: ResearchRun): RawState {
  return {
    schema_version: 1,
    research_id: run.research_id,
    research_goal: run.goal,
    status: run.status,
    next_step: run.next_step,
    revision: run.revision,
    iteration: run.iteration,
    baseline: run.baseline,
    budget: run.budget,
    decision: run.decision,
    decisions: run.decisions,
    baseline_experiment_id: run.experiments.find((e) => e.purpose === "BASELINE")?.id ?? null,
    papers: run.papers,
    claims: run.claims,
    evidence: run.evidence,
    hypotheses: run.hypotheses,
    patches: run.patches,
    experiments: run.experiments,
    studies: run.studies,
    trials: run.trials,
    termination_reason: run.termination_reason,
    created_at: run.created_at,
    updated_at: run.updated_at,
  };
}

export { activityEvents };
