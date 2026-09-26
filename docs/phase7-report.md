# Phase 7 — resumable repeated evaluation (first increment)

This increment adds `labpilot evaluate`, which creates one durable research run per
unique seed, executes them sequentially, resumes unfinished runs from SQLite, and
summarizes paired candidate improvements. A JSON manifest freezes the evaluation ID,
goal, seeds and recorded execution conditions; reusing the ID with changed settings is
rejected. Interrupted batches retain completed seed runs and resume without replaying them.

## Offline control-flow demonstration

- Evaluation ID: `7b1c1711-ea4b-4e27-b99b-e32ea4c555cb`
- Seeds: 17, 29, 41
- Runs: 3 completed simulations, each with a KEEP decision
- Repeating the same evaluation ID returned the same summary and did not create extra runs.
- Manifest: `.labpilot/phase7-demo/evaluations/7b1c1711-ea4b-4e27-b99b-e32ea4c555cb.json`
- Summary: `.labpilot/phase7-demo/evaluation.json` (local ignored demo data)

These fake outcomes are fixed fixtures and ignore the seed. This checks persistence,
resumption and aggregation paths only; it is not an ML result.

## Bounded Docker evaluation

- Evaluation IDs: `ce3d706d-4343-4b0b-9da9-28ae409c289e` (seeds 42–44) and
  `11e375f7-d12e-4b0b-9da9-28ae409c289e` (seeds 45–49)
- Date: 2026-09-26 (local machine)
- Goal: measure dropout 0.3 against the unchanged MNIST baseline using validation accuracy.
- Seeds: 42–49; Docker image tag `labpilot-mnist:phase2`, baseline commit
  `54148c39bf8285f760f04435c07a963b3e3b37d9`, and `min_delta=0.001`.
- Immutable image digest: `labpilot-mnist@sha256:0fd7a733d0f30af943d8ef09dc4cb50bdade0623194358fbe17c890ddbe6ad8f`.
- Dataset procedure: cached MNIST training split; each seed selects 10,000 training
  examples and 2,000 disjoint validation examples from that split using a seeded
  permutation. The baseline and candidate are paired on the same split for each seed.
- All eight baseline/candidate pairs completed successfully (16 Docker executions).
  No LLM calls were made.

| Seed | Baseline | Candidate best | Paired improvement | Decision |
|---:|---:|---:|---:|---|
| 42 | 0.9255 | 0.9270 | +0.0015 | KEEP |
| 43 | 0.9285 | 0.9260 | -0.0025 | REJECT |
| 44 | 0.9220 | 0.9225 | +0.0005 | REJECT (below threshold) |
| 45 | 0.9285 | 0.9310 | +0.0025 | KEEP |
| 46 | 0.9255 | 0.9240 | -0.0015 | REJECT |
| 47 | 0.9245 | 0.9220 | -0.0025 | REJECT |
| 48 | 0.9335 | 0.9315 | -0.0020 | REJECT |
| 49 | 0.9290 | 0.9285 | -0.0005 | REJECT |

Mean paired improvement was -0.000562 (sample standard deviation 0.001898), with 2/8
KEEP decisions. The cohort baseline mean was 0.927125 (range 0.9220–0.9335); total
recorded Docker runtime was 66.07 seconds. This small single-dataset batch does not
establish a general dropout effect and does not support retaining this change as a
reliable improvement.

An initial attempt ended before training because Docker temporarily reported the cached
image tag missing. Those failed records are kept in a separate local evaluation and
excluded here. After verifying the image, the batch was rerun under the evaluation ID
above. The baseline checkout was clean afterward and no containers remained.

The local outputs and combined JSON benchmark are under `.labpilot/phase7-real-*`; they
are ignored by Git. Reusing an evaluation ID and identical settings returns persisted
completed seed runs without duplicating them. The combined benchmark includes all eight
seed runs from the same SQLite database.

Improvements are paired against each run’s measured baseline. Baseline values can vary
by seed, so they are reported as a cohort mean and range rather than splitting otherwise
matched seeds into separate cohorts. Cohorts still require a common executor, baseline
repository and commit, command, image digest, dataset procedure, metric direction,
thresholds and budgets.

## Phase 8 follow-up

Phase 7's repeated-evaluation increment is complete. Phase 8 adds a DeepSeek-proposed
dropout 0.2 intervention and compares it with this dropout 0.3 cohort across the same
eight seeds; see the [Phase 8 report](phase8-report.md). Neither change has a positive
mean improvement. Do not generalize from these runs or treat the fake demonstration as
experimental evidence.
