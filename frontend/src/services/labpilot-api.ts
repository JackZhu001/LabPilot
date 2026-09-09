import type {
  ActivityEvent,
  Experiment,
  RawState,
  ResearchRun,
  RunSummary,
  StudyDetail,
} from "@/types/domain";
import { activityEvents, runs, summarize, toRawState } from "@/mocks";

/**
 * Data-access boundary. Components consume only this module; when the real
 * backend exists, these functions switch to HTTP fetches without touching UI.
 * Fixture data is imported here and nowhere else.
 */

export class NotFoundError extends Error {
  constructor(what: string) {
    super(`${what} not found`);
    this.name = "NotFoundError";
  }
}

const latency = (ms = 240) => new Promise((r) => setTimeout(r, ms));

export async function getRuns(): Promise<RunSummary[]> {
  await latency();
  return runs.map(summarize).sort((a, b) => b.updated_at.localeCompare(a.updated_at));
}

/** Full run objects (for views that need literature or study detail). */
export async function getAllRuns(): Promise<ResearchRun[]> {
  await latency();
  return [...runs].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
}

export async function getFeaturedRun(): Promise<ResearchRun> {
  await latency();
  // Fixture order defines the featured demo run (real Phase 2 KEEP run).
  return runs[0];
}

export async function getRun(researchId: string): Promise<ResearchRun> {
  await latency();
  const run = runs.find((r) => r.research_id === researchId);
  if (!run) throw new NotFoundError(`Research run ${researchId}`);
  return run;
}

export async function getExperiments(researchId?: string): Promise<Experiment[]> {
  await latency(180);
  const source = researchId
    ? runs.filter((r) => r.research_id === researchId)
    : runs;
  return source.flatMap((r) => r.experiments);
}

export async function getExperiment(experimentId: string): Promise<{ run: ResearchRun; experiment: Experiment }> {
  await latency();
  for (const run of runs) {
    const experiment = run.experiments.find((e) => e.id === experimentId);
    if (experiment) return { run, experiment };
  }
  throw new NotFoundError(`Experiment ${experimentId}`);
}

export async function getStudy(studyId: string): Promise<StudyDetail> {
  await latency();
  for (const run of runs) {
    const study = run.studies.find((s) => s.id === studyId);
    if (study) {
      return { run, study, trials: run.trials.filter((t) => t.study_id === study.id) };
    }
  }
  throw new NotFoundError(`Study ${studyId}`);
}

export async function getRawState(researchId: string): Promise<RawState> {
  await latency(160);
  const run = runs.find((r) => r.research_id === researchId);
  if (!run) throw new NotFoundError(`Research run ${researchId}`);
  return toRawState(run);
}

export async function getActivity(limit = 12): Promise<ActivityEvent[]> {
  await latency(160);
  return [...activityEvents].sort((a, b) => b.at.localeCompare(a.at)).slice(0, limit);
}
