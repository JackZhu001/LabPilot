import type { ResearchRun } from "@/types/domain";

/**
 * FIXTURES — fake-executor runs exercising the Phase 1 deterministic loop.
 * Metrics follow the documented fake-outcome scenarios (configured baseline,
 * simulated experiments); no execution provenance exists in fake mode.
 */

const replanResearchId = "b3d1f6a2-8c4e-49a7-b5d0-2e7f9c1a4b6d";
const replanH1 = "9f2b4d6a-1c8e-4a3b-8d7f-0b5e9c3a7d1f";
const replanH2 = "4a6c8e0b-2d4f-4c5a-9e1b-7d3f5a9c1e3b";
const replanExp1 = "5e7a9c1b-3f5d-4a2c-8e4b-6d8f0a2c4e6b";
const replanExp2 = "1c3e5a7b-9d1f-4b6a-8c2e-0a4d6f8b2c4e";

export const fakeReplanRun: ResearchRun = {
  research_id: replanResearchId,
  goal: "Does dropout improve validation accuracy?",
  status: "COMPLETED",
  next_step: "end",
  revision: 10,
  iteration: 2,
  termination_reason: "Second candidate kept after measured improvement",
  executor: "fake",
  baseline: {
    metric_name: "validation_accuracy",
    value: 0.8,
    direction: "MAXIMIZE",
    min_delta: 0.01,
    regression_delta: 0.01,
  },
  budget: {
    max_iterations: 3,
    max_experiments: 3,
    max_failed_experiments: 2,
    max_replans: 2,
    max_hpo_trials: 0,
    iterations: 2,
    experiments: 2,
    failed_experiments: 0,
    replans: 1,
    hpo_trials: 0,
  },
  decision: "KEEP",
  decisions: [
    {
      experiment_id: replanExp1,
      study_id: null,
      hypothesis_id: replanH1,
      decision: "REPLAN",
      reason:
        "Candidate delta of 0.0004 did not meet the minimum improvement of 0.01; another iteration is affordable, so the hypothesis is replanned.",
      improvement: 0.0004,
    },
    {
      experiment_id: replanExp2,
      study_id: null,
      hypothesis_id: replanH2,
      decision: "KEEP",
      reason:
        "Candidate validation accuracy improved by 0.0192, exceeding the configured minimum delta of 0.01.",
      improvement: 0.0192,
    },
  ],
  experiments: [
    {
      id: replanExp1,
      research_id: replanResearchId,
      purpose: "CANDIDATE",
      hypothesis_id: replanH1,
      sequence: 1,
      status: "SUCCEEDED",
      config: {
        seed: 42,
        direction: "MAXIMIZE",
        metric_name: "validation_accuracy",
        parameters: { dropout: 0.05, epochs: 2, batch_size: 64 },
      },
      metric_value: 0.8004,
      delta: 0.0004,
      runtime_seconds: 0.08,
      executor: "fake",
      error: null,
      provenance: null,
      decision: "REPLAN",
    },
    {
      id: replanExp2,
      research_id: replanResearchId,
      purpose: "CANDIDATE",
      hypothesis_id: replanH2,
      sequence: 2,
      status: "SUCCEEDED",
      config: {
        seed: 42,
        direction: "MAXIMIZE",
        metric_name: "validation_accuracy",
        parameters: { dropout: 0.4, epochs: 2, batch_size: 64 },
      },
      metric_value: 0.8192,
      delta: 0.0192,
      runtime_seconds: 0.06,
      executor: "fake",
      error: null,
      provenance: null,
      decision: "KEEP",
    },
  ],
  studies: [],
  trials: [],
  papers: [
    {
      id: "7b1d3f5a-9c2e-4b6a-8d0c-2f4a6c8e0b2d",
      title: "Dropout: A Simple Way to Prevent Neural Networks from Overfitting",
      authors: ["Srivastava, N.", "Hinton, G.", "Krizhevsky, A.", "Sutskever, I.", "Salakhutdinov, R."],
      url: "https://jmlr.org/papers/v15/srivastava14a.html",
      published_at: "2014-06-30",
      source_provider: "fixture",
    },
  ],
  claims: [
    {
      id: "2f4a6c8e-0b2d-4d7f-9a1c-5e7b9d1f3a5c",
      paper_id: "7b1d3f5a-9c2e-4b6a-8d0c-2f4a6c8e0b2d",
      statement: "Moderate dropout rates improve generalization on fully connected MNIST networks.",
      confidence: 0.9,
    },
  ],
  evidence: [
    {
      id: "6d8f0a2c-4e6b-4c1a-9f3d-1a5c7e9b3d5f",
      claim_id: "2f4a6c8e-0b2d-4d7f-9a1c-5e7b9d1f3a5c",
      relation: "SUPPORT",
      summary: "Validation error improves for dropout rates between 0.2 and 0.5 in the reported setting.",
      confidence: 0.8,
    },
  ],
  hypotheses: [
    {
      id: replanH1,
      statement: "A low dropout rate of 0.05 will improve validation accuracy by at least 0.01.",
      motivation: "Initial conservative application of the supporting dropout evidence.",
      expected_effect: "validation_accuracy improves by >= 0.01 (absolute)",
      confidence: 0.55,
      falsification_criteria: "Improvement below 0.01 absolute.",
      status: "REPLANNED",
    },
    {
      id: replanH2,
      statement: "A dropout rate of 0.4 will improve validation accuracy by at least 0.01.",
      motivation: "First candidate was inconclusive at 0.05; replanned closer to the evidence-supported range.",
      expected_effect: "validation_accuracy improves by >= 0.01 (absolute)",
      confidence: 0.6,
      falsification_criteria: "Improvement below 0.01 absolute.",
      status: "ACCEPTED",
    },
  ],
  patches: [],
  created_at: "2026-09-09T11:20:15Z",
  updated_at: "2026-09-09T11:20:19Z",
};

const runningResearchId = "e5a3c7f1-0b2d-4e8a-9c4f-6d2b8a0e4c6f";
const runningHypothesisId = "3c5e7a9b-1d4f-4b6a-8e0c-9f2a4d6b8c0e";
const pendingExpId = "8a0e4c6f-2b4d-4f9a-b1c3-5e7a9d1f3b5c";

export const fakeRunningRun: ResearchRun = {
  research_id: runningResearchId,
  goal: "Does a wider hidden layer improve validation accuracy?",
  status: "RUNNING",
  next_step: "experiment",
  revision: 3,
  iteration: 1,
  termination_reason: null,
  executor: "fake",
  baseline: {
    metric_name: "validation_accuracy",
    value: 0.8,
    direction: "MAXIMIZE",
    min_delta: 0.01,
    regression_delta: 0.01,
  },
  budget: {
    max_iterations: 3,
    max_experiments: 3,
    max_failed_experiments: 2,
    max_replans: 2,
    max_hpo_trials: 0,
    iterations: 1,
    experiments: 0,
    failed_experiments: 0,
    replans: 0,
    hpo_trials: 0,
  },
  decision: null,
  decisions: [],
  experiments: [
    {
      id: pendingExpId,
      research_id: runningResearchId,
      purpose: "CANDIDATE",
      hypothesis_id: runningHypothesisId,
      sequence: 1,
      status: "PENDING",
      config: {
        seed: 42,
        direction: "MAXIMIZE",
        metric_name: "validation_accuracy",
        parameters: { hidden_dim: 256, epochs: 2, batch_size: 64 },
      },
      metric_value: null,
      delta: null,
      runtime_seconds: null,
      executor: "fake",
      error: null,
      provenance: null,
      decision: null,
    },
  ],
  studies: [],
  trials: [],
  papers: [
    {
      id: "0d2f4a6c-8e0b-4a2c-9b4d-1f3a5c7e9b1d",
      title: "Understanding the difficulty of training deep feedforward neural networks",
      authors: ["Glorot, X.", "Bengio, Y."],
      url: "https://proceedings.mlr.press/v9/glorot10a.html",
      published_at: "2010-05-16",
      source_provider: "fixture",
    },
  ],
  claims: [
    {
      id: "5a7c9e1b-3d5f-4a8b-8c0d-2f4a6c8e0b2d",
      paper_id: "0d2f4a6c-8e0b-4a2c-9b4d-1f3a5c7e9b1d",
      statement: "Network width interacts with initialization and can shift validation accuracy.",
      confidence: 0.7,
    },
  ],
  evidence: [
    {
      id: "9b1d3f5a-7c2e-4d0b-8a6c-4e6f8a0c2d4b",
      claim_id: "5a7c9e1b-3d5f-4a8b-8c0d-2f4a6c8e0b2d",
      relation: "SUPPORT",
      summary: "Wider layers changed validation accuracy measurably under controlled initialization.",
      confidence: 0.6,
    },
  ],
  hypotheses: [
    {
      id: runningHypothesisId,
      statement: "Increasing the hidden dimension from 128 to 256 will improve validation accuracy by at least 0.01.",
      motivation: "Supporting evidence links width, under the same initialization scheme, to accuracy shifts.",
      expected_effect: "validation_accuracy improves by >= 0.01 (absolute)",
      confidence: 0.5,
      falsification_criteria: "Improvement below 0.01 absolute.",
      status: "PROPOSED",
    },
  ],
  patches: [],
  created_at: "2026-09-09T16:40:31Z",
  updated_at: "2026-09-09T16:40:34Z",
};
