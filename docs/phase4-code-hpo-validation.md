# Phase 4.1 validation: DeepSeek code change with Optuna HPO

Measured on 2026-09-09 with the real DeepSeek OpenAI-compatible API, Optuna,
Git Worktrees, and Docker CPU execution. The successful validation research ID is
`ed21efa6-57b3-4a8d-b729-1942f1d0d991`. No API credential is stored in the run,
this report, SQLite, prompts, logs, or artifacts.

## Validation goal and bounds

Research goal:

> Improve validation accuracy while keeping the model lightweight. The experiment
> must involve a source-code change to model architecture or regularization. Do not
> solve the task only by increasing epochs, batch size, learning rate, or other
> config-only training parameters. For the selected code-level hypothesis, define
> a small hyperparameter search space and evaluate it with Optuna.

- Model: `deepseek-v4-pro`
- Maximum iterations: 1
- Maximum hypothesis-generation attempts: 2
- Maximum patch repairs: 1
- Maximum HPO trials: 4
- Maximum LLM calls: 10
- Decision threshold: `min_delta = 0.001`

The run used one hypothesis-generation attempt. DeepSeek generated:

1. Add a second hidden layer with ReLU activation and dropout after each hidden
   layer, and tune `dropout` and `hidden_dim` via Optuna.
2. Replace ReLU with LeakyReLU using a `0.01` negative slope, and tune `dropout`
   and `hidden_dim` via Optuna.
3. Add batch normalization before ReLU, and tune `dropout` and `hidden_dim` via
   Optuna.

The deterministic ranking selected hypothesis 1. Its typed plan used
`CODE_CHANGE_WITH_HPO`, modified only `model.py`, and requested four trials.

## Validated patch and search space

The real DeepSeek Code Agent proposed the source modification. Patch validation
checked the exact base SHA and target allowlist, applied the diff in a disposable
managed Worktree, captured the actual Git diff, and compiled the changed Python.
Each HPO experiment then persisted and applied that validated diff in its own
Worktree.

```diff
diff --git a/model.py b/model.py
index 8c88d11..6b77666 100644
--- a/model.py
+++ b/model.py
@@ -9,5 +9,8 @@ def build_model(hidden_dim: int, dropout: float) -> nn.Module:
         nn.Linear(28 * 28, hidden_dim),
         nn.ReLU(),
         nn.Dropout(dropout),
+        nn.Linear(hidden_dim, hidden_dim),
+        nn.ReLU(),
+        nn.Dropout(dropout),
         nn.Linear(hidden_dim, 10),
     )
```

The validated typed SearchSpace was:

```yaml
dropout:
  type: float
  low: 0.0
  high: 0.5
  step: 0.1
hidden_dim:
  type: int
  low: 32
  high: 256
  step: 32
```

Optuna selected every concrete value. DeepSeek did not enumerate the trials.

## Measured results

Baseline configuration:

```yaml
seed: 42
epochs: 2
batch_size: 64
learning_rate: 0.001
hidden_dim: 128
dropout: 0.0
train_samples: 10000
validation_samples: 2000
primary_metric: validation_accuracy
direction: maximize
```

| Trial | Dropout | Hidden dim | Status | Validation accuracy | Runtime (s) |
| ---: | ---: | ---: | --- | ---: | ---: |
| 0 | 0.2 | 256 | SUCCEEDED | **0.9285** | 3.2315 |
| 1 | 0.0 | 160 | SUCCEEDED | 0.9230 | 3.0236 |
| 2 | 0.5 | 32 | SUCCEEDED | 0.8695 | 2.9095 |
| 3 | 0.2 | 256 | SUCCEEDED | 0.9285 | 3.2668 |

- Requested HPO trials: **4**
- Successful trials: **4**
- Failed trials: **0**
- Best trial: **0**; stable first-trial tie-break over trial 3
- Best parameters: **`dropout=0.2`, `hidden_dim=256`**
- Baseline validation accuracy: **0.9255**
- Best candidate validation accuracy: **0.9285**
- Delta: **+0.0030000000000000027**
- Deterministic decision: **KEEP**
- Decision reason: **Metric meets the minimum improvement threshold**

The DecisionEngine made the decision before the critic ran. The critic persisted
an explanation with the same KEEP value and had no authority to replace it.

## LLM usage, runtime, and integrity

- LLM calls: **5**
- Input tokens: **11,060**
- Output tokens: **2,140**
- Total tokens: **13,200**
- Recorded LLM latency: **31.61392454000452 seconds**
- Total wall runtime: **47.88901149999583 seconds**
- Sum of measured baseline and trial execution runtimes: **15.496337040000071 seconds**
- Baseline SHA before: `66f808c0a5d1941906d0d99e7de845bc67f1e32a`
- Baseline SHA after: `66f808c0a5d1941906d0d99e7de845bc67f1e32a`
- Baseline status before: clean
- Baseline status after: clean
- Remaining LabPilot containers: none

Every candidate artifact contained the modified `model.py`. Every persisted
`actual.diff` was exactly the validated 400-character Git diff above. This check
also caught and fixed a stale-runner bug during validation: candidate experiments
now carry their immutable validated patch, so an executor created before patch
generation cannot fall back to an older configured patch.

## Checkpoint and resume verification

The completed SQLite state was reopened and passed to the ordinary executor again.
The returned state was byte-for-model equal to the state before resume.

- Duplicate LLM calls after resume: **0**
- Duplicate completed HPO trials after resume: **0**
- Duplicate Docker experiments after resume: **0**
- Generated hypothesis reused: **yes**
- ExperimentPlan reused: **yes**
- Validated PatchProposal/CodePatch reused: **yes**

The targeted offline integration test also checkpoints the constrained hypothesis
route, rejects and persists an initial CONFIG_ONLY batch, accepts a second
CODE_CHANGE_WITH_HPO batch, validates a real Worktree diff, runs three Optuna
trials, selects the best trial, invokes DecisionEngine, and confirms zero work on
completed resume.

## Validation fixes

Phase 4.1 required four focused fixes rather than an architectural redesign:

1. Persist a run-level required change type and a two-attempt hypothesis-generation
   limit so validation-only CONFIG_ONLY batches receive bounded structured feedback.
2. Give the hypothesis and planning roles the exact existing `TrainingOverrides`
   parameter names, while retaining deterministic rejection of unsupported spaces.
3. Carry the validated patch on each `ExperimentConfig`, preventing a long-lived
   runner from applying a stale pre-agent patch.
4. Use Git's deterministic `--recount` when checking and applying unified diffs.
   Target, SHA, path, size, content, Worktree, and security checks remain unchanged;
   only incorrect model-supplied hunk line counts are normalized.

No literature retrieval or frontend changes are part of this validation.

## Final verification

- Offline pytest suite: **221 passed, 7 deselected in 16.95s**.
- Docker suite with a normal image build: **5 passed, 223 deselected in 27.02s**.
- Live DeepSeek suite: **2 passed, 226 deselected in 4.71s**.
- Ruff check: **passed**.
- Ruff format check: **85 files already formatted**.
- Strict mypy: **no issues in 47 source files**.
- `uv lock --check` and `git diff --check`: **passed**.
