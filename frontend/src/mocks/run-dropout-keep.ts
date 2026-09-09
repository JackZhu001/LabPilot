import type { ResearchRun } from "@/types/domain";

/**
 * PRIMARY FIXTURE — real Phase 2 measured data.
 *
 * Every metric, SHA, image ID, runtime, and decision below is taken from
 * docs/phase2-report.md (research 7ba5ca38-1d49-4901-bc98-a108a11942ea,
 * run date 2026-09-09). Literature/evidence/hypothesis chain mirrors the
 * explicit Phase 1 fixture pattern. Only container IDs and source hashes
 * are synthetic (not recorded in the report).
 */

export const DROPOUT_PATCH_DIFF = `--- a/config.yaml
+++ b/config.yaml
@@ -3,7 +3,7 @@
 batch_size: 64
 learning_rate: 0.001
 hidden_dim: 128
-dropout: 0.0
+dropout: 0.3
 train_samples: 10000
 validation_samples: 2000
 primary_metric: validation_accuracy
`;

const CONFIG_TEXT = `seed: 42
epochs: 2
batch_size: 64
learning_rate: 0.001
hidden_dim: 128
dropout: 0.0
train_samples: 10000
validation_samples: 2000
primary_metric: validation_accuracy
direction: maximize
`;

const RESEARCH_ID = "7ba5ca38-1d49-4901-bc98-a108a11942ea";
const BASELINE_EXPERIMENT_ID = "24b67028-0f27-5d74-91c3-9e4385aa6b49";
const CANDIDATE_EXPERIMENT_ID = "d2f65154-f321-5e64-b044-c166e87eaf68";
const HYPOTHESIS_ID = "1f0a3c55-92b1-4d47-8e5b-0a3c6d9f1b2e";
const BASE_COMMIT_SHA = "74481d37a3e6085d1fd1e6d017a781f895cde78c";

const runDir = (experimentId: string) =>
  `/workspace/labpilot/.labpilot/runs/${RESEARCH_ID}/${experimentId}`;

export const dropoutKeepRun: ResearchRun = {
  research_id: RESEARCH_ID,
  goal: "Does dropout improve validation accuracy?",
  status: "COMPLETED",
  next_step: "end",
  revision: 7,
  iteration: 1,
  termination_reason: "Candidate kept after measured improvement over baseline",
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
    max_hpo_trials: 0,
    iterations: 1,
    experiments: 2,
    failed_experiments: 0,
    replans: 0,
    hpo_trials: 0,
  },
  decision: "KEEP",
  decisions: [
    {
      experiment_id: CANDIDATE_EXPERIMENT_ID,
      study_id: null,
      hypothesis_id: HYPOTHESIS_ID,
      decision: "KEEP",
      reason:
        "Candidate validation accuracy improved by 0.0015, exceeding the configured minimum delta of 0.001.",
      improvement: 0.0015,
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
      runtime_seconds: 7.615615,
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
          image: "labpilot-mnist:phase2",
          image_id:
            "sha256:2b3c9b05e806fc0e98c45d0edf5a3107404c1f268b4ac37b52f3a3425c05fc99",
          container_id:
            "5a3f9c1e7b24d8045ef3c9a1b6d207e8f4c3d512ab9e0f7c2d14e5b3a9c8f6d1",
          network: "none",
          cpus: 2,
          memory_mb: 2048,
        },
        artifacts: {
          stdout_path: `${runDir(BASELINE_EXPERIMENT_ID)}/stdout.log`,
          stderr_path: `${runDir(BASELINE_EXPERIMENT_ID)}/stderr.log`,
          metrics_path: `${runDir(BASELINE_EXPERIMENT_ID)}/outputs/metrics.json`,
          provenance_path: `${runDir(BASELINE_EXPERIMENT_ID)}/provenance.json`,
          patch_path: `${runDir(BASELINE_EXPERIMENT_ID)}/patch.diff`,
          actual_diff_path: `${runDir(BASELINE_EXPERIMENT_ID)}/actual.diff`,
          source_path: `${runDir(BASELINE_EXPERIMENT_ID)}/source`,
        },
        training_command: ["python", "train.py"],
        configuration_text: CONFIG_TEXT,
        source_sha256:
          "b7c4f2e19a8d30e6c5b4a1f8d92e73c05ad41b6e9f8c2d3a47b1e5f0c8d629a4",
        random_seed: 42,
        started_at: "2026-09-09T13:58:41Z",
        finished_at: "2026-09-09T13:58:49Z",
        runtime_seconds: 7.615615,
        exit_code: 0,
        status: "SUCCEEDED",
        failure_reason: null,
        report: {
          schema_version: 1,
          metrics: {
            validation_accuracy: 0.9255,
            validation_loss: 0.2393279272,
          },
          metadata: { seed: 42, epochs: 2 },
        },
      },
    },
    {
      id: CANDIDATE_EXPERIMENT_ID,
      research_id: RESEARCH_ID,
      purpose: "CANDIDATE",
      hypothesis_id: HYPOTHESIS_ID,
      sequence: 2,
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
          dropout: 0.3,
        },
      },
      metric_value: 0.927,
      delta: 0.0015,
      runtime_seconds: 4.470243,
      executor: "docker",
      error: null,
      decision: "KEEP",
      provenance: {
        research_id: RESEARCH_ID,
        experiment_id: CANDIDATE_EXPERIMENT_ID,
        hypothesis_id: HYPOTHESIS_ID,
        git: {
          baseline_repo_path: "/workspace/labpilot/.labpilot/baselines/mnist",
          base_commit_sha: BASE_COMMIT_SHA,
          baseline_sha_after: BASE_COMMIT_SHA,
          baseline_clean_after: true,
          worktree_path: `/workspace/labpilot/.labpilot/worktrees/${CANDIDATE_EXPERIMENT_ID}`,
          worktree_identity: CANDIDATE_EXPERIMENT_ID,
          actual_git_diff: DROPOUT_PATCH_DIFF,
        },
        docker: {
          image: "labpilot-mnist:phase2",
          image_id:
            "sha256:9c2c0325bd34ef60eb4fbcc7bb41e99e8b9084d73580fa8c7c1efb781df3944b",
          container_id:
            "8e1d4a7c2f9b0653d8e7a1c4b9f2e8d5a3c7b1f6e9d2a4c8b7f1e3d5a9c6b2f4",
          network: "none",
          cpus: 2,
          memory_mb: 2048,
        },
        artifacts: {
          stdout_path: `${runDir(CANDIDATE_EXPERIMENT_ID)}/stdout.log`,
          stderr_path: `${runDir(CANDIDATE_EXPERIMENT_ID)}/stderr.log`,
          metrics_path: `${runDir(CANDIDATE_EXPERIMENT_ID)}/outputs/metrics.json`,
          provenance_path: `${runDir(CANDIDATE_EXPERIMENT_ID)}/provenance.json`,
          patch_path: `${runDir(CANDIDATE_EXPERIMENT_ID)}/patch.diff`,
          actual_diff_path: `${runDir(CANDIDATE_EXPERIMENT_ID)}/actual.diff`,
          source_path: `${runDir(CANDIDATE_EXPERIMENT_ID)}/source`,
        },
        training_command: ["python", "train.py"],
        configuration_text: CONFIG_TEXT.replace("dropout: 0.0", "dropout: 0.3"),
        source_sha256:
          "e2f8a5c3b1d94706f2c8e5a1b3d7f9c4a6e2b8d5f1c7a4e9b3d6f2a8c5e1b7d9",
        random_seed: 42,
        started_at: "2026-09-09T13:59:02Z",
        finished_at: "2026-09-09T13:59:07Z",
        runtime_seconds: 4.470243,
        exit_code: 0,
        status: "SUCCEEDED",
        failure_reason: null,
        report: {
          schema_version: 1,
          metrics: {
            validation_accuracy: 0.927,
            validation_loss: 0.2394287736,
          },
          metadata: { seed: 42, epochs: 2 },
        },
      },
    },
  ],
  studies: [],
  trials: [],
  papers: [
    {
      id: "3a5b7c9d-1e2f-4a3b-8c9d-0e1f2a3b4c5d",
      title: "Dropout: A Simple Way to Prevent Neural Networks from Overfitting",
      authors: ["Srivastava, N.", "Hinton, G.", "Krizhevsky, A.", "Sutskever, I.", "Salakhutdinov, R."],
      url: "https://jmlr.org/papers/v15/srivastava14a.html",
      published_at: "2014-06-30",
      source_provider: "fixture",
    },
  ],
  claims: [
    {
      id: "5c7d9e1f-2a3b-4c5d-9e0f-1a2b3c4d5e6f",
      paper_id: "3a5b7c9d-1e2f-4a3b-8c9d-0e1f2a3b4c5d",
      statement:
        "Applying dropout to fully connected layers reduces overfitting and improves generalization on MNIST.",
      confidence: 0.9,
    },
  ],
  evidence: [
    {
      id: "7e1f3a5b-4c6d-4e7f-8a9b-2c3d4e5f6a7b",
      claim_id: "5c7d9e1f-2a3b-4c5d-9e0f-1a2b3c4d5e6f",
      relation: "SUPPORT",
      summary:
        "Validation error decreased across dropout rates up to 0.5 for fully connected MNIST networks.",
      confidence: 0.85,
    },
  ],
  hypotheses: [
    {
      id: HYPOTHESIS_ID,
      statement:
        "Setting dropout to 0.3 in the MLP classifier will improve validation accuracy by at least 0.001.",
      motivation:
        "Supporting evidence links dropout in fully connected layers to better generalization on MNIST.",
      expected_effect: "validation_accuracy improves by >= 0.001 (absolute)",
      confidence: 0.7,
      falsification_criteria:
        "Validation accuracy regresses by >= 0.01, or the experiment fails to produce a valid metric.",
      status: "ACCEPTED",
    },
  ],
  patches: [
    {
      id: "9a3c5e7f-6b8d-4f0a-2c4e-6d8e0f2a4c6e",
      hypothesis_id: HYPOTHESIS_ID,
      description: "Set dropout to 0.3 in the training configuration",
      diff: DROPOUT_PATCH_DIFF,
    },
  ],
  created_at: "2026-09-09T13:57:40Z",
  updated_at: "2026-09-09T13:59:12Z",
};
