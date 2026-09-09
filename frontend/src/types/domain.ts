/**
 * Frontend domain types, modeled after LabPilot's Python models
 * (src/labpilot/models/*.py and src/labpilot/hpo/models.py).
 * Mirrors: RunStatus, Step, ResearchDecision, ExperimentStatus, ExperimentPurpose,
 * ExecutionEnvironment, ExecutionProvenance, Baseline, ResearchBudget, Trial,
 * OptimizationStudy, SearchSpace, Paper/Claim/Evidence/Hypothesis.
 */

export type RunStatus = "READY" | "RUNNING" | "PAUSED" | "COMPLETED";
export type ResearchDecision = "KEEP" | "REJECT" | "REPLAN";
export type ExperimentStatus = "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED";
export type TrialStatus = "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED" | "PRUNED";
export type StudyStatus = "RUNNING" | "SUCCEEDED" | "FAILED";
export type ExperimentPurpose = "BASELINE" | "CANDIDATE";
export type ExecutionEnvironment = "fake" | "docker";
export type EvidenceRelation = "SUPPORT" | "CONTRADICT" | "NEUTRAL";
export type MetricDirection = "MAXIMIZE" | "MINIMIZE";

/** Graph steps, in loop order (Step enum in models/common.py). */
export type Step =
  | "literature"
  | "evidence"
  | "baseline"
  | "hypothesis"
  | "experiment"
  | "hpo_plan"
  | "hpo_suggest"
  | "hpo_execute"
  | "hpo_sync"
  | "analyze"
  | "decision"
  | "end";

export interface Baseline {
  metric_name: string;
  value: number;
  direction: MetricDirection;
  min_delta: number;
  regression_delta: number;
}

export interface ResearchBudget {
  max_iterations: number;
  max_experiments: number;
  max_failed_experiments: number;
  max_replans: number;
  max_hpo_trials: number;
  iterations: number;
  experiments: number;
  failed_experiments: number;
  replans: number;
  hpo_trials: number;
}

export interface DecisionRecord {
  experiment_id: string | null;
  study_id: string | null;
  hypothesis_id: string | null;
  decision: ResearchDecision;
  reason: string;
  improvement: number | null;
}

export interface GitMetadata {
  baseline_repo_path: string;
  base_commit_sha: string;
  baseline_sha_after: string | null;
  baseline_clean_after: boolean | null;
  worktree_path: string;
  worktree_identity: string;
  actual_git_diff: string;
}

export interface DockerMetadata {
  image: string;
  image_id: string | null;
  container_id: string | null;
  network: "none";
  cpus: number;
  memory_mb: number;
}

export interface ExperimentArtifact {
  stdout_path: string;
  stderr_path: string;
  metrics_path: string;
  provenance_path: string;
  patch_path: string;
  actual_diff_path: string;
  source_path: string;
}

export interface MetricReport {
  schema_version: 1;
  metrics: Record<string, number>;
  metadata: { seed: number; epochs: number } | null;
}

export interface ExecutionProvenance {
  research_id: string;
  experiment_id: string;
  hypothesis_id: string | null;
  git: GitMetadata;
  docker: DockerMetadata;
  artifacts: ExperimentArtifact;
  training_command: string[];
  configuration_text: string | null;
  source_sha256: string | null;
  random_seed: number;
  started_at: string;
  finished_at: string;
  runtime_seconds: number;
  exit_code: number | null;
  status: "SUCCEEDED" | "FAILED" | "TIMED_OUT";
  failure_reason: string | null;
  report: MetricReport | null;
}

export interface ExperimentConfig {
  seed: number;
  direction: MetricDirection;
  metric_name: string;
  parameters: Record<string, string | number | boolean>;
}

export interface Experiment {
  id: string;
  research_id: string;
  purpose: ExperimentPurpose;
  hypothesis_id: string | null;
  sequence: number;
  status: ExperimentStatus;
  config: ExperimentConfig;
  metric_value: number | null;
  delta: number | null;
  runtime_seconds: number | null;
  executor: ExecutionEnvironment;
  error: string | null;
  provenance: ExecutionProvenance | null;
  decision: ResearchDecision | null;
}

export type SearchParameter =
  | { name: string; type: "float"; low: number; high: number; step: number | null; log: boolean }
  | { name: string; type: "int"; low: number; high: number; step: number; log: boolean }
  | { name: string; type: "categorical"; choices: (string | number | boolean)[] };

export interface OptimizationStudy {
  id: string;
  research_id: string;
  hypothesis_id: string;
  study_name: string;
  sampler_name: "TPESampler";
  sampler_seed: number;
  primary_metric: string;
  direction: MetricDirection;
  max_trials: number;
  completed_trials: number;
  failed_trials: number;
  pruned_trials: number;
  best_trial_id: string | null;
  status: StudyStatus;
  created_at: string;
  search_space: SearchParameter[];
}

export interface Trial {
  id: string;
  study_id: string;
  optuna_trial_number: number;
  status: TrialStatus;
  parameters: Record<string, string | number | boolean>;
  primary_metric_value: number | null;
  runtime_seconds: number;
  failure_reason: string | null;
}

export interface Paper {
  id: string;
  title: string;
  authors: string[];
  url: string | null;
  published_at: string | null;
  source_provider: string;
}

export interface Claim {
  id: string;
  paper_id: string;
  statement: string;
  confidence: number;
}

export interface Evidence {
  id: string;
  claim_id: string;
  relation: EvidenceRelation;
  summary: string;
  confidence: number;
}

export interface Hypothesis {
  id: string;
  statement: string;
  motivation: string;
  expected_effect: string;
  confidence: number;
  falsification_criteria: string;
  status: "PROPOSED" | "ACCEPTED" | "REJECTED" | "REPLANNED";
}

export interface CodePatch {
  id: string;
  hypothesis_id: string;
  description: string;
  diff: string;
}

export type ActivityKind =
  | "baseline_completed"
  | "patch_applied"
  | "docker_run"
  | "metric_collected"
  | "decision"
  | "checkpoint"
  | "hpo_trial"
  | "replan";

export interface ActivityEvent {
  id: string;
  research_id: string;
  at: string;
  kind: ActivityKind;
  title: string;
  detail?: string;
  experiment_id?: string;
}

/** Summary used by list views (dashboard, /runs, /experiments). */
export interface RunSummary {
  research_id: string;
  goal: string;
  status: RunStatus;
  decision: ResearchDecision | null;
  iteration: number;
  executor: ExecutionEnvironment;
  baseline_metric: number | null;
  best_metric: number | null;
  delta: number | null;
  experiment_count: number;
  failed_experiments: number;
  created_at: string;
  updated_at: string;
}

/** Full run, mirroring ResearchState. */
export interface ResearchRun {
  research_id: string;
  goal: string;
  status: RunStatus;
  next_step: Step;
  revision: number;
  iteration: number;
  termination_reason: string | null;
  executor: ExecutionEnvironment;
  baseline: Baseline;
  budget: ResearchBudget;
  decision: ResearchDecision | null;
  decisions: DecisionRecord[];
  experiments: Experiment[];
  studies: OptimizationStudy[];
  trials: Trial[];
  papers: Paper[];
  claims: Claim[];
  evidence: Evidence[];
  hypotheses: Hypothesis[];
  patches: CodePatch[];
  created_at: string;
  updated_at: string;
}

/** The full ResearchState JSON, for the raw-state inspector. */
export type RawState = Record<string, unknown>;

export interface StudyDetail {
  run: ResearchRun;
  study: OptimizationStudy;
  trials: Trial[];
}
