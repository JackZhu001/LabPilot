import type { ResearchRun } from "@/types/domain";

/**
 * FIXTURE — HPO preview run for the Phase 3 study UI.
 *
 * The baseline metric (0.9255) is the real Phase 2 measurement. The study,
 * trials, and their metrics are ILLUSTRATIVE ONLY: the Phase 3 Optuna backend
 * is still in development, so trial numbers are design fixtures, not reported
 * experimental results.
 */

const RESEARCH_ID = "c4e2a90f-1b3d-4a5c-8e6f-2d4b6a8c0e2f";
const STUDY_ID = "2b8d4f6a-9c1e-4a3b-8d5f-7a9c1e3b5d7f";
const HYPOTHESIS_ID = "6d2f8a4c-0b1e-4c3a-9f5d-3a7c1e9b5d3f";
const BASELINE_EXPERIMENT_ID = "0f4b8d2e-7c3a-4e1f-9a6d-5b8f2c4e0a6d";
const BASE_COMMIT_SHA = "c3a91f024e7b5d68a2f4c0e1b9d7358a6f2c4e08";

const TRIALS: {
  n: number
  status: "SUCCEEDED" | "FAILED" | "PRUNED"
  params: Record<string, string | number | boolean>
  metric: number | null
  runtime: number
  failure: string | null
}[] = [
  { n: 0, status: "SUCCEEDED", params: { learning_rate: 0.0032, dropout: 0.1, hidden_dim: 256, batch_size: 128 }, metric: 0.931, runtime: 4.9, failure: null },
  { n: 1, status: "SUCCEEDED", params: { learning_rate: 0.0008, dropout: 0.25, hidden_dim: 64, batch_size: 32 }, metric: 0.9205, runtime: 8.7, failure: null },
  { n: 2, status: "SUCCEEDED", params: { learning_rate: 0.0021, dropout: 0.0, hidden_dim: 128, batch_size: 64 }, metric: 0.9285, runtime: 6.2, failure: null },
  { n: 3, status: "FAILED", params: { learning_rate: 0.0049, dropout: 0.45, hidden_dim: 256, batch_size: 64 }, metric: null, runtime: 9.4, failure: "Container exited with code 137 (memory limit)" },
  { n: 4, status: "SUCCEEDED", params: { learning_rate: 0.0016, dropout: 0.35, hidden_dim: 256, batch_size: 32 }, metric: 0.9332, runtime: 7.1, failure: null },
  { n: 5, status: "SUCCEEDED", params: { learning_rate: 0.0028, dropout: 0.15, hidden_dim: 64, batch_size: 128 }, metric: 0.926, runtime: 4.5, failure: null },
  { n: 6, status: "PRUNED", params: { learning_rate: 0.0004, dropout: 0.05, hidden_dim: 128, batch_size: 64 }, metric: null, runtime: 3.8, failure: null },
  { n: 7, status: "SUCCEEDED", params: { learning_rate: 0.0024, dropout: 0.2, hidden_dim: 128, batch_size: 128 }, metric: 0.9301, runtime: 5.3, failure: null },
];

const trialId = (n: number) => `a1b2c3d${n}-4e5f-4a6b-8c9d-${n}e0f2a4b6c8d${n}`;

export const hpoPreviewRun: ResearchRun = {
  research_id: RESEARCH_ID,
  goal: "Can a search over learning rate, dropout, hidden size, and batch size improve MNIST validation accuracy?",
  status: "COMPLETED",
  next_step: "end",
  revision: 18,
  iteration: 1,
  termination_reason: "Best trial kept after measured improvement over baseline",
  executor: "docker",
  baseline: {
    metric_name: "validation_accuracy",
    value: 0.9255,
    direction: "MAXIMIZE",
    min_delta: 0.001,
    regression_delta: 0.01,
  },
  budget: {
    max_iterations: 3,
    max_experiments: 2,
    max_failed_experiments: 2,
    max_replans: 0,
    max_hpo_trials: 8,
    iterations: 1,
    experiments: 1,
    failed_experiments: 0,
    replans: 0,
    hpo_trials: 8,
  },
  decision: "KEEP",
  decisions: [
    {
      experiment_id: null,
      study_id: STUDY_ID,
      hypothesis_id: HYPOTHESIS_ID,
      decision: "KEEP",
      reason:
        "Best completed trial improved validation accuracy by 0.0077 over the measured baseline, exceeding the minimum delta of 0.001.",
      improvement: 0.0077,
    },
  ],
  experiments: [
    {
      id: BASELINE_EXPERIMENT_ID,
      research_id: RESEARCH_ID,
      purpose: "BASELINE",
      hypothesis_id: null,
      sequence: 1,
      status: "SUCCEEDED",
      config: {
        seed: 42,
        direction: "MAXIMIZE",
        metric_name: "validation_accuracy",
        parameters: {
          seed: 42,
          epochs: 2,
          batch_size: 64,
          learning_rate: 0.001,
          hidden_dim: 128,
          dropout: 0.0,
        },
      },
      metric_value: 0.9255,
      delta: null,
      runtime_seconds: 7.6,
      executor: "docker",
      error: null,
      decision: null,
      provenance: {
        research_id: RESEARCH_ID,
        experiment_id: BASELINE_EXPERIMENT_ID,
        hypothesis_id: null,
        git: {
          baseline_repo_path: "/workspace/labpilot/.labpilot/baselines/mnist",
          base_commit_sha: BASE_COMMIT_SHA,
          baseline_sha_after: BASE_COMMIT_SHA,
          baseline_clean_after: true,
          worktree_path: `/workspace/labpilot/.labpilot/worktrees/${BASELINE_EXPERIMENT_ID}`,
          worktree_identity: BASELINE_EXPERIMENT_ID,
          actual_git_diff: "",
        },
        docker: {
          image: "labpilot-mnist:phase3",
          image_id:
            "sha256:5f1d8a3c6e9b2d4f7a0c5e8b1d3f6a9c2e5b8d1f4a7c0e3b6d9f2a5c8e1b4d7f",
          container_id:
            "d4a7f1c8b2e59036d8a1c4f7b0e3d6a9c2f5b8e1d4a7c0f3b6e9d2a5c8b1f4e7a",
          network: "none",
          cpus: 2,
          memory_mb: 2048,
        },
        artifacts: {
          stdout_path: `/workspace/labpilot/.labpilot/runs/${RESEARCH_ID}/${BASELINE_EXPERIMENT_ID}/stdout.log`,
          stderr_path: `/workspace/labpilot/.labpilot/runs/${RESEARCH_ID}/${BASELINE_EXPERIMENT_ID}/stderr.log`,
          metrics_path: `/workspace/labpilot/.labpilot/runs/${RESEARCH_ID}/${BASELINE_EXPERIMENT_ID}/outputs/metrics.json`,
          provenance_path: `/workspace/labpilot/.labpilot/runs/${RESEARCH_ID}/${BASELINE_EXPERIMENT_ID}/provenance.json`,
          patch_path: `/workspace/labpilot/.labpilot/runs/${RESEARCH_ID}/${BASELINE_EXPERIMENT_ID}/patch.diff`,
          actual_diff_path: `/workspace/labpilot/.labpilot/runs/${RESEARCH_ID}/${BASELINE_EXPERIMENT_ID}/actual.diff`,
          source_path: `/workspace/labpilot/.labpilot/runs/${RESEARCH_ID}/${BASELINE_EXPERIMENT_ID}/source`,
        },
        training_command: ["python", "train.py"],
        configuration_text: null,
        source_sha256:
          "f4a8c2e6b1d59730a6c2e8f5b1d4a7c3e9b2f6d5a8c1e4b7d2f5a8c3e6b1d9f4",
        random_seed: 42,
        started_at: "2026-09-09T15:12:03Z",
        finished_at: "2026-09-09T15:12:11Z",
        runtime_seconds: 7.6,
        exit_code: 0,
        status: "SUCCEEDED",
        failure_reason: null,
        report: {
          schema_version: 1,
          metrics: { validation_accuracy: 0.9255, validation_loss: 0.2393279272 },
          metadata: { seed: 42, epochs: 2 },
        },
      },
    },
  ],
  studies: [
    {
      id: STUDY_ID,
      research_id: RESEARCH_ID,
      hypothesis_id: HYPOTHESIS_ID,
      study_name: "mnist-mlp-dropout-lr-search",
      sampler_name: "TPESampler",
      sampler_seed: 42,
      primary_metric: "validation_accuracy",
      direction: "MAXIMIZE",
      max_trials: 8,
      completed_trials: 6,
      failed_trials: 1,
      pruned_trials: 1,
      best_trial_id: trialId(4),
      status: "SUCCEEDED",
      created_at: "2026-09-09T15:13:20Z",
      search_space: [
        { name: "learning_rate", type: "float", low: 0.0001, high: 0.005, step: null, log: true },
        { name: "dropout", type: "float", low: 0.0, high: 0.5, step: null, log: false },
        { name: "hidden_dim", type: "categorical", choices: [64, 128, 256] },
        { name: "batch_size", type: "categorical", choices: [32, 64, 128] },
      ],
    },
  ],
  trials: TRIALS.map((t) => ({
    id: trialId(t.n),
    study_id: STUDY_ID,
    optuna_trial_number: t.n,
    status: t.status,
    parameters: t.params,
    primary_metric_value: t.metric,
    runtime_seconds: t.runtime,
    failure_reason: t.failure,
  })),
  papers: [
    {
      id: "8c1e3a5b-7d2f-4b6a-9e0c-4f6a8c2e0b4d",
      title: "Algorithms for Hyper-Parameter Optimization",
      authors: ["Bergstra, J.", "Bardenet, R.", "Bengio, Y.", "Kégl, B."],
      url: null,
      published_at: "2011-12-01",
      source_provider: "fixture",
    },
  ],
  claims: [
    {
      id: "1e4a7c2b-8f3d-4b9e-5a1c-3f7b9d1e5a3c",
      paper_id: "8c1e3a5b-7d2f-4b6a-9e0c-4f6a8c2e0b4d",
      statement:
        "TPE-style sequential model-based optimization finds better hyperparameters than random search given the same trial budget.",
      confidence: 0.8,
    },
  ],
  evidence: [
    {
      id: "4b9e5a1c-2f7d-4c3e-8a6b-9d1e5a3c7f4b",
      claim_id: "1e4a7c2b-8f3d-4b9e-5a1c-3f7b9d1e5a3c",
      relation: "SUPPORT",
      summary:
        "On MNIST-scale objectives, TPE matched or beat random search within 25 trials in the reported experiments.",
      confidence: 0.75,
    },
  ],
  hypotheses: [
    {
      id: HYPOTHESIS_ID,
      statement:
        "A seeded TPE search over learning rate, dropout, hidden dimension, and batch size will find a configuration beating the measured baseline by at least 0.001 validation accuracy.",
      motivation:
        "Supporting evidence indicates model-based search outperforms the hand-picked baseline configuration at this model scale.",
      expected_effect: "validation_accuracy improves by >= 0.001 over baseline 0.9255",
      confidence: 0.65,
      falsification_criteria:
        "No completed trial exceeds the baseline by the minimum delta, or the study exhausts its trial budget first.",
      status: "ACCEPTED",
    },
  ],
  patches: [],
  created_at: "2026-09-09T15:10:02Z",
  updated_at: "2026-09-09T15:24:45Z",
};
