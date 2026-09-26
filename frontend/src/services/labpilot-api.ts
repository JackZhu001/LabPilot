import type {
  ActivityEvent,
  Experiment,
  RawState,
  ResearchRun,
  RunSummary,
  StudyDetail,
} from "@/types/domain";
import { activityEvents, runs, summarize, toRawState } from "@/mocks";

const API = (import.meta.env.VITE_LABPILOT_API_URL ?? "/api").replace(/\/$/, "");
const USE_MOCKS = import.meta.env.VITE_LABPILOT_USE_MOCKS === "true";

export class NotFoundError extends Error {
  constructor(what: string) {
    super(`${what} not found`);
    this.name = "NotFoundError";
  }
}

export function artifactUrl(experimentId: string, name: string): string | null {
  return USE_MOCKS
    ? null
    : `${API}/experiments/${encodeURIComponent(experimentId)}/artifacts/${encodeURIComponent(name)}`;
}

async function request<T>(path: string, label: string): Promise<T> {
  const response = await fetch(`${API}${path}`);
  if (response.status === 404) throw new NotFoundError(label);
  if (!response.ok) throw new Error(`${label} request failed (${response.status})`);
  return response.json() as Promise<T>;
}

export function getRuns(): Promise<RunSummary[]> {
  return USE_MOCKS
    ? Promise.resolve(runs.map(summarize).sort((a, b) => b.updated_at.localeCompare(a.updated_at)))
    : request("/runs", "Runs");
}

export async function createResearchRun(input: {
  goal: string;
  baseline_path: string;
  papers: { name: string; data: string }[];
  max_iterations: number;
  max_literature_queries: number;
  max_retrieved_papers: number;
  seed: number;
  constraints: string;
  change_type: "CONFIG_ONLY" | "CODE_CHANGE" | null;
  metric_name: string;
  direction: "MAXIMIZE" | "MINIMIZE";
}): Promise<{ research_id: string; status: string }> {
  if (USE_MOCKS) throw new Error("Creating research requires the live API.");
  const response = await fetch(`${API}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  const result = await response.json() as { research_id?: string; status?: string; error?: string };
  if (!response.ok) throw new Error(result.error ?? `Could not start research (${response.status})`);
  return { research_id: result.research_id!, status: result.status! };
}

export interface ResearchPlanPreview {
  goal: string;
  baseline: { name: string; commit_sha: string; file_count: number; important_files: string[] };
  objective: { metric_name: string; direction: "MAXIMIZE" | "MINIMIZE" };
  papers: string[];
  literature: { providers: string[]; max_queries: number; max_papers: number };
  seed: number;
  constraints: string;
  max_iterations: number;
  max_experiments: number;
  change_type: string | null;
  warnings: string[];
}

export async function getResearchPreview(input: {
  goal: string;
  baseline_path: string;
  papers: string[];
  max_iterations: number;
  max_literature_queries: number;
  max_retrieved_papers: number;
  seed: number;
  constraints: string;
  change_type: "CONFIG_ONLY" | "CODE_CHANGE" | null;
  metric_name: string;
  direction: "MAXIMIZE" | "MINIMIZE";
}): Promise<ResearchPlanPreview> {
  if (USE_MOCKS) throw new Error("Research preview requires the live API.");
  const response = await fetch(`${API}/research-preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  const result = await response.json() as ResearchPlanPreview & { error?: string };
  if (!response.ok) throw new Error(result.error ?? `Could not prepare research preview (${response.status})`);
  return result;
}

export function getAllRuns(): Promise<ResearchRun[]> {
  return USE_MOCKS
    ? Promise.resolve([...runs].sort((a, b) => b.updated_at.localeCompare(a.updated_at)))
    : request("/runs?full=1", "Runs");
}

export async function getFeaturedRun(): Promise<ResearchRun> {
  if (USE_MOCKS) return runs[0];
  const [featured] = await getRuns();
  if (!featured) throw new NotFoundError("Featured run");
  return getRun(featured.research_id);
}

export function getRun(researchId: string): Promise<ResearchRun> {
  if (!USE_MOCKS) return request(`/runs/${encodeURIComponent(researchId)}`, `Research run ${researchId}`);
  const run = runs.find((item) => item.research_id === researchId);
  return run ? Promise.resolve(run) : Promise.reject(new NotFoundError(`Research run ${researchId}`));
}

export async function getExperiments(researchId?: string): Promise<Experiment[]> {
  if (USE_MOCKS) {
    const source = researchId ? runs.filter((item) => item.research_id === researchId) : runs;
    return source.flatMap((item) => item.experiments);
  }
  const query = researchId ? `?research_id=${encodeURIComponent(researchId)}` : "";
  return request(`/experiments${query}`, "Experiments");
}

export function getExperiment(experimentId: string): Promise<{ run: ResearchRun; experiment: Experiment }> {
  if (!USE_MOCKS) return request(`/experiments/${encodeURIComponent(experimentId)}`, `Experiment ${experimentId}`);
  for (const run of runs) {
    const experiment = run.experiments.find((item) => item.id === experimentId);
    if (experiment) return Promise.resolve({ run, experiment });
  }
  return Promise.reject(new NotFoundError(`Experiment ${experimentId}`));
}

export function getStudy(studyId: string): Promise<StudyDetail> {
  if (!USE_MOCKS) return request(`/studies/${encodeURIComponent(studyId)}`, `Study ${studyId}`);
  for (const run of runs) {
    const study = run.studies.find((item) => item.id === studyId);
    if (study) return Promise.resolve({ run, study, trials: run.trials.filter((item) => item.study_id === study.id) });
  }
  return Promise.reject(new NotFoundError(`Study ${studyId}`));
}

export function getRawState(researchId: string): Promise<RawState> {
  return USE_MOCKS
    ? getRun(researchId).then(toRawState)
    : request(`/runs/${encodeURIComponent(researchId)}/state`, `Research state ${researchId}`);
}

export function getActivity(limit = 12): Promise<ActivityEvent[]> {
  return USE_MOCKS
    ? Promise.resolve([...activityEvents].sort((a, b) => b.at.localeCompare(a.at)).slice(0, limit))
    : request(`/activity?limit=${limit}`, "Activity");
}

export function getReports(): Promise<import("@/types/domain").RunEvaluation[]> {
  if (USE_MOCKS) return Promise.reject(new Error("Reports require the live API. Disable fixture mode to inspect saved runs."));
  return request("/reports", "Reports");
}
export function getReport(id: string): Promise<import("@/types/domain").ResearchReport> {
  if (USE_MOCKS) return Promise.reject(new Error("Reports require the live API."));
  return request(`/reports/${encodeURIComponent(id)}`, "Report");
}
export function reportUrl(id: string, format: "markdown" | "json"): string {
  return `${API}/reports/${encodeURIComponent(id)}?format=${format}`;
}
export function benchmarkUrl(ids: string[], format = "json"): string {
  const params = new URLSearchParams({ format });
  ids.forEach((id) => params.append("run_id", id));
  return `${API}/benchmark?${params}`;
}
export function getBenchmark(ids: string[]): Promise<import("@/types/domain").BenchmarkReport> {
  if (USE_MOCKS) return Promise.reject(new Error("Benchmarks require the live API."));
  const params = new URLSearchParams();
  ids.forEach((id) => params.append("run_id", id));
  return request(`/benchmark?${params}`, "Benchmark");
}
