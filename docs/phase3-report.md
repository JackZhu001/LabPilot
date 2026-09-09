# Phase 3 measured report: hierarchical hyperparameter optimization

Measured on 2026-09-09 in the local development environment. The reported values
come from the retained LabPilot state and Docker artifacts; they are development
measurements for this small CPU MNIST fixture, not benchmark claims.

## Implemented flow

```text
Fixture hypothesis + fixed candidate patch
    ↓
ExperimentPlan + typed SearchSpace
    ↓
Persistent Optuna study
    ↓
Trial parameters → validated TrainingOverrides
    ↓
DockerExperimentRunner → versioned metrics.json
    ↓
Persist LabPilot result → synchronize Optuna
    ↓
Best successful trial → baseline comparison → KEEP / REJECT / REPLAN
```

The outer research loop describes what to try. A candidate plan can contain one
code patch shared by all of its trials. The inner Optuna loop chooses parameter
values. Phase 3 implements this inner loop only; no model chooses parameters or
generates hypotheses, plans, or patches.

`SearchSpace` is composed of discriminated `FloatParameter`, `IntParameter`, and
`CategoricalParameter` models. Sampled values become a validated
`TrainingOverrides` object before execution. The MNIST demonstration searched:

| Parameter | Definition |
| --- | --- |
| `learning_rate` | float, 0.0001–0.005, logarithmic |
| `dropout` | float, 0.0–0.5 |
| `hidden_dim` | categorical: 64, 128, 256 |
| `batch_size` | categorical: 32, 64, 128 |

The measured baseline is a separate experiment and never enters the Optuna study.
Every accepted Optuna trial creates one LabPilot `Trial` and one isolated Docker
`Experiment` using the same metrics and provenance contracts as Phase 2.

## Persistence and recovery

LabPilot's existing SQLite snapshot remains authoritative for workflow position,
accepted trials, experiments, results, and budget counters. Optuna owns parameter
suggestions and ask/tell states in a per-study SQLite database. A stable study UUID,
study name, Optuna trial number, LabPilot trial UUID, and experiment UUID link the
two stores.

The adapter adopts a pending Optuna ask if interruption occurs before LabPilot saves
the reservation. If LabPilot has saved a terminal result but Optuna has not received
it, resume tells Optuna idempotently and continues. It rejects parameter, identity,
direction, or outcome conflicts. The generated `study.json` is a derived report and
is not used for resume.

Each reservation consumes one experiment and one HPO trial. A failure additionally
consumes the existing failed-experiment counter. Stored reservations and results
are not charged or executed again. The study stops suggesting when either its plan
or the research HPO budget is exhausted. Failed trials remain recorded and later
trials continue while budget remains.

Phase 3 uses `TPESampler` with a recorded seed and three startup trials. The
`seed_plus_trial_number_v1` policy reconstructs a deterministic sampler for each
trial number because Optuna's SQLite storage does not persist an in-memory sampler
RNG. Successful trials alone are eligible for selection. Direction is respected,
and ties resolve by Optuna trial number then trial UUID. With final-only MNIST
metrics, the study deliberately uses `NopPruner` and does not invent intermediate
observations.

## Real Docker run and restart

The demonstration used the following shape:

```bash
labpilot run --goal "Optimize MNIST regularization" \
  --executor docker --repo .labpilot/baselines/mnist-hpo \
  --hpo --trials 6 --sampler-seed 42 \
  --max-replans 0 --min-delta 0.001 --stop-after 14
labpilot resume 226fd826-a9ff-4df3-ba16-3f144407c825
```

The first process measured the baseline and completed trials 0–2. It paused at
revision 14 with `next_step=hpo_suggest`. A fresh CLI process loaded the same
research snapshot and Optuna study, ran trials 3–5, selected the best persisted
result, and completed at revision 25. The first three trial experiments were not
rerun.

Research ID: `226fd826-a9ff-4df3-ba16-3f144407c825`  
Study ID: `e68935f4-8c04-5db0-9018-057dc41301ad`

| Trial | Status | Learning rate | Dropout | Hidden | Batch | Accuracy | Runtime (s) |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | SUCCEEDED | 0.00043284502212938834 | 0.4753571532049581 | 64 | 128 | 0.8905 | 4.832793 |
| 1 | SUCCEEDED | 0.00015684629241532954 | 0.3045332696397407 | 256 | 32 | 0.9115 | 4.222671 |
| 2 | SUCCEEDED | 0.0026204252099715254 | 0.052398052184934873 | 64 | 32 | 0.9425 | 3.800610 |
| 3 | SUCCEEDED | 0.0038267373707078474 | 0.01724109080123018 | 64 | 64 | 0.9265 | 10.995343 |
| 4 | SUCCEEDED | 0.004802950528382854 | 0.027391923678784735 | 128 | 32 | 0.9335 | 4.836402 |
| 5 | SUCCEEDED | 0.0009630698618354848 | 0.23734326725611238 | 64 | 32 | 0.9255 | 3.897727 |

Baseline metric: **0.9255**  
Requested trials: **6**  
Completed successful trials: **6**  
Failed trials: **0**  
Best trial number: **2**  
Best parameters: **learning_rate=0.0026204252099715254,
dropout=0.052398052184934873, hidden_dim=64, batch_size=32**  
Best metric: **0.9425**  
Delta versus baseline: **+0.017000000000000015**  
Decision: **KEEP**  
Total HPO trial runtime: **32.585545459998684 seconds**

The total is the sum of recorded trial runtimes. It excludes baseline time and the
human/process pause between commands, so it is not end-to-end wall-clock duration.

Baseline SHA before: `f6465476ea583e3f1b50b3ab0d8396ea569d0012`  
Baseline SHA after: `f6465476ea583e3f1b50b3ab0d8396ea569d0012`  
Baseline clean after: **true**

The dedicated baseline repository remained at the same commit with an empty
`git status --porcelain`. All six recorded trial provenance objects also report a
clean baseline after execution, and no LabPilot containers remained after the run.

Retained local audit files:

- `.labpilot/phase3-demo-start.txt`
- `.labpilot/phase3-demo-resume.txt`
- `.labpilot/phase3-demo-state.json`
- `.labpilot/runs/226fd826-a9ff-4df3-ba16-3f144407c825/studies/e68935f4-8c04-5db0-9018-057dc41301ad/`

## Verification

The normal suite covers typed validation and serialization, all Optuna mappings,
maximize/minimize selection, failure continuation, all-failed studies, budget
exhaustion, resume boundaries, orphan-ask adoption, outcome synchronization, and
duplicate prevention with a fake runner. Docker-marked coverage adds a real
three-trial MNIST study resumed from a fresh repository object, alongside the Phase
2 baseline/candidate, timeout, nonzero-exit, and missing-metrics cases.

Final verification results:

- Python 3.13 normal suite: **202 passed, 5 deselected in 13.89s**.
- Python 3.11 normal suite: **202 passed, 5 deselected in 13.90s**.
- Docker-marked suite: **5 passed, 202 deselected in 25.62s**.
- Ruff check: **passed**.
- Ruff formatting check: **61 files already formatted**.
- Strict mypy: **no issues in 36 source files**.
- `uv lock --check`: **resolved 65 packages successfully**.
- `git diff --check`: **passed with no output**.

## Known limitations and Phase 4 boundary

- Search runs sequentially in one local process; there are no leases, distributed
  workers, or stale-worker coordination.
- A process crash during active Docker execution retains the Phase 2 manual
  reconciliation limitation. Recovery is guaranteed at committed workflow steps.
- Pruning is modeled but inactive because training reports final metrics only.
- The CLI uses the fixed MNIST Phase 3 search space. Library callers can supply a
  different typed search space.
- Optuna and research snapshots are linked stores; conflicts are detected rather
  than automatically repaired.
- Literature, evidence, and hypothesis content remains deterministic fixtures.

Phase 4 is intentionally unimplemented. Its exact next steps are a real injectable
`LLMClient`, schema-validated structured output, bounded repository inspection,
hypothesis and `ExperimentPlan` generation, validated patch generation, and
token/cost accounting. Those additions must preserve the existing split: a model
proposes what to try, Optuna selects inner-loop values, Docker runs experiments,
and `DecisionEngine` judges measured outcomes.
