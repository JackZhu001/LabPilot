# LabPilot

**Autonomous ML Research & Experimentation Agent**

LabPilot aims to make ML research reproducible, traceable, and bounded: every
hypothesis should connect to evidence, every experiment to a hypothesis, and every
decision to a measurable result.

```text
Literature → Evidence → Hypothesis → Experiment → Metric → Keep / Reject / Replan
```

**Current scope: Phase 3 — resumable hierarchical hyperparameter optimization.**
Fake mode preserves the fast, offline research loop. Docker mode measures a CPU
MNIST baseline, runs a fixed candidate across a typed Optuna search space, and
feeds the best successful trial into the existing deterministic decision engine.

No LLM calls, generated hypotheses or patches, or real literature retrieval are
implemented. The literature, evidence, and hypothesis stages still use explicit
fixtures; Docker execution, metrics, and inner-loop parameter search are real.

## Why this project exists

Research scripts often lose the context behind an experiment: its source claim,
expected effect, baseline, reason for rejection, or the next action after a crash.
LabPilot makes those relationships and transitions explicit in a persisted research
state. Its value is the engineering of that loop, rather than a collection of
chatbot roles.

## Current capabilities

- Pydantic v2 models for literature, evidence, hypotheses, patches, experiments,
  trials, metrics, budgets, decisions, and the central research state.
- UUID provenance links, immutable models, validated JSON round trips, schema
  versioning, finite metrics, confidence bounds, and timezone-aware timestamps.
- Independent numerical decision policy supporting maximization and minimization.
- LangGraph orchestration with bounded KEEP, REJECT, and REPLAN paths.
- Injectable literature, evidence, hypothesis, and experiment service protocols.
- Deterministic fake scenarios, including expected experiment failures.
- SQLAlchemy 2.x / SQLite snapshots, metadata listings, and optimistic revisions.
- Pause after any completed step; resume in a fresh process from the next step.
- Typed floating-point, integer, and categorical search spaces with validated
  conversion to experiment configuration.
- Persistent Optuna studies, seeded TPE sampling, exact HPO budget accounting,
  failed-trial continuation, and deterministic best-trial selection.
- One isolated Docker experiment per accepted trial, with a generated validated
  parameter file retained in its source snapshot.
- CLI inspection, JSON export to stdout, and standard logging with research,
  hypothesis, study, trial, and experiment identifiers.

Docker mode adds `ExecutionEnvironment`, `ExecutionStatus`, `ExperimentArtifact`,
`GitMetadata`, `DockerMetadata`, `MetricReport`, and `ExecutionProvenance`. Supplied
patches are retained in `CodePatch`. In HPO mode, one Optuna trial maps to one
LabPilot `Trial` and one `Experiment`; the measured baseline remains outside the study.

## Architecture

```text
CLI → LangGraph adapter → research transitions → injected services
                  │               │
                  │               └── pure DecisionEngine + ResearchBudget
                  └── repository → SQLite (snapshot + indexed metadata)
```

The graph uses a small typed envelope around `ResearchState`; it does not use a
nested dictionary as its domain model. Nodes call a domain transition, save its
result, and return the updated state. This follows LangGraph's
[StateGraph and conditional routing API](https://docs.langchain.com/oss/python/langgraph/graph-api).
Business logic lives in `services/workflow.py`, numerical comparison in
`decisions/engine.py`, and storage in `persistence/repository.py`.

```text
START → literature → evidence → hypothesis ─────────→ experiment → analyze → decision
                                   │                                  ↑          │
                                   └→ plan → suggest → execute → sync ┘          │
                                   ↑                                             │
                                   └──────────── REPLAN, budget allows ──────────┤
                                                                   KEEP/REJECT → END
```

Every entry is routed from the saved `next_step`. Before creating a hypothesis or
running an experiment, the domain workflow checks its relevant budget. Analysis
records a decision and rationale; the decision step applies it to the hypothesis
and selects termination or another iteration. All evidence and previous decisions
remain in the snapshot.

### Decision policy

The baseline specifies the objective name, direction, minimum improvement, and
significant regression threshold. Deltas are absolute metric units, not relative
percentages. For minimization, the comparison sign is reversed so a positive delta
always means improvement.

| Result | Decision |
| --- | --- |
| Improvement ≥ `min_delta` | KEEP |
| Regression ≥ `regression_delta` | REJECT |
| Inconclusive | REPLAN if another iteration is affordable; otherwise REJECT |
| Expected experiment failure | REPLAN if another iteration is affordable; otherwise REJECT |

Both thresholds must be positive and finite. Boundary comparisons use a `1e-12`
relative floating-point tolerance. An improvement can be kept on the last allowed
experiment. The baseline stays fixed for the run; KEEP terminates the run.

### Budget semantics

Counters record iterations started, experiments completed (success or failure),
failed experiments, and replans committed. The default limits are 3 iterations,
3 experiments, 2 failed experiments, and 2 replans.

- `can_continue()` checks whether a **new** iteration can start.
- `can_run_experiment()` checks experiment and failure capacity. The final already
  started iteration is allowed to finish even when the iteration cap is reached.
- `can_replan()` also requires a remaining replan slot and room for another iteration.
- A zero iteration, experiment, or failure limit prevents experiment work entirely.
  A zero replan limit permits the initial iteration but no retries.
- Budget termination before any experiment leaves the decision empty and records
  a termination reason. Exhaustion after an inconclusive/failed result yields REJECT.

### Checkpoint and resume contract

**SQLite is the single source of truth.** There is no second LangGraph checkpointer.
A committed row contains the complete validated snapshot, next-step cursor,
revision, and indexed metadata, all in one database transaction. `schema_version=1`
is explicit; unsupported versions are rejected rather than silently interpreted.

A successful node commits exactly one revision. `--stop-after N` pauses after N
steps in the current invocation. For example, `--stop-after 4` saves the completed
experiment with `next_step=analyze`. Resume loads it and runs analysis without
repeating the experiment. A completed run is an unchanged no-op on resume.

Unexpected service exceptions propagate and preserve the previous committed
cursor. Expected simulated experiment failures are recorded as FAILED and analyzed
normally. A crash **before a step commits** may replay that step. Stable UUIDs and
stateless fake providers make replay deterministic in Phase 1. This is checkpointed
step execution, not an exactly-once guarantee for future external side effects.

Optimistic revision checks reject stale writes. They do not acquire an execution
lease: two processes may execute the same uncommitted service before one write is
rejected. Use one executor per run. Phase 2 intentionally has no execution leases or
stale-worker coordination. Completed database checkpoints skip real execution on
resume. A crash during an active Docker step may leave a container, worktree, or
artifact directory that requires manual reconciliation. Existing execution
directories are refused rather than silently overwritten or restarted. Artifact
provenance is an audit output, not an independent resume checkpoint.

The fake outcome sequence and seed are persisted in the state. Restarting a CLI
process reconstructs the same fake services; it does not depend on a hidden random
number generator or in-memory call counter. IDs are stable within a research ID,
and control flow is deterministic. New research IDs and wall-clock timestamps vary.

HPO adds a linked Optuna SQLite database per study. Optuna owns trial suggestions
and its ask/tell states. The versioned LabPilot snapshot owns accepted executions,
results, counters, and the workflow cursor. Stable study/trial/experiment UUIDs and
Optuna trial numbers connect them. An interrupted ask is adopted on resume, and an
already synchronized result is accepted idempotently; conflicting records fail
closed. `study.json` is regenerated after checkpoints and is never a resume source.

## Project structure

```text
LabPilot/
├── pyproject.toml
├── uv.lock
├── README.md
├── .env.example
├── .gitignore
├── docs/phase2-report.md
├── docs/phase3-report.md
├── src/
│   └── labpilot/
│       ├── cli/
│       │   ├── __init__.py
│       │   └── app.py
│       ├── decisions/
│       │   ├── __init__.py
│       │   └── engine.py
│       ├── execution/
│       │   ├── __init__.py
│       │   ├── artifacts.py
│       │   ├── docker.py
│       │   ├── git.py
│       │   ├── metrics.py
│       │   └── runner.py
│       ├── graph/
│       │   ├── __init__.py
│       │   └── workflow.py
│       ├── hpo/
│       │   ├── mapper.py
│       │   ├── models.py
│       │   ├── optuna.py
│       │   ├── reporting.py
│       │   ├── search_space.py
│       │   ├── selection.py
│       │   └── service.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── budget.py
│       │   ├── common.py
│       │   ├── execution.py
│       │   ├── experiments.py
│       │   ├── literature.py
│       │   ├── state.py
│       │   └── training.py
│       ├── persistence/
│       │   ├── __init__.py
│       │   └── repository.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── fakes.py
│       │   ├── interfaces.py
│       │   ├── real.py
│       │   └── workflow.py
│       └── __init__.py
├── examples/
│   └── mnist_baseline/
│       ├── .dockerignore
│       ├── .gitignore
│       ├── Dockerfile
│       ├── README.md
│       ├── config.yaml
│       ├── download.py
│       ├── model.py
│       ├── requirements.txt
│       └── train.py
├── tests/
│   ├── docker/
│   │   └── test_integration.py
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_cli.py
│   ├── test_decisions.py
│   ├── test_docker_adapter.py
│   ├── test_fakes.py
│   ├── test_git_execution.py
│   ├── test_hpo_models.py
│   ├── test_hpo_workflow.py
│   ├── test_metric_reports.py
│   ├── test_models.py
│   ├── test_persistence.py
│   ├── test_real_runner.py
│   ├── test_real_workflow.py
│   └── test_workflow.py
```

Phase 2 adds `execution/{git,docker,runner,metrics,artifacts}.py`,
`models/execution.py`, `services/real.py`, the MNIST example, and execution tests.
Phase 3 adds `hpo/`, typed training overrides, study/trial state, and HPO tests.
Existing schema-version-1 snapshots remain readable because extensions have
compatible defaults. No database migration was needed. Optuna uses its own scoped
database for sampler state; it does not replace the LabPilot checkpoint repository.
LLMs, prompts, and search provider implementations remain deferred.

## Setup

Python **3.11+** is required. Dependency installation needs access to a package
index or a populated local cache.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
labpilot --help
labpilot init
```

For locked dependency resolution with uv:

```bash
uv sync --locked --extra dev
uv run labpilot --help
```

The default database is `.labpilot/labpilot.sqlite3`, relative to the current
working directory. Use the same `--db` path across commands when changing directories.
The CLI creates parent directories and initializes tables as needed; `init` is
optional and idempotent. `.env.example` documents that no credentials are required;
the app does not load `.env` files. Keep optional LangSmith tracing disabled for
offline execution if it was enabled in your shell by another application.

## CLI examples

```bash
labpilot run --goal "Does dropout improve validation accuracy?"
labpilot status <research-id>
labpilot status <research-id> --json
labpilot runs
```

The default fake outcome improves the baseline, resulting in KEEP at iteration 1.

Exercise REPLAN followed by KEEP, with a persisted interruption:

```bash
labpilot run --goal "Does dropout improve validation accuracy?" \
  --outcomes inconclusive,improve --stop-after 4 --db .labpilot/demo.sqlite3
labpilot status <research-id> --db .labpilot/demo.sqlite3
labpilot resume <research-id> --db .labpilot/demo.sqlite3
```

`--outcomes` accepts `improve`, `regress`, `inconclusive`, and `fail`. The last outcome
repeats if the sequence is shorter than the run. `--stop-after 6` pauses after the
first full iteration when REPLAN is selected; terminal decisions finish immediately.
The option is also available on `resume` and always counts steps in that invocation.

```bash
labpilot run --goal "Regression fixture" --outcomes regress
labpilot run --goal "Failure fixture" --outcomes fail,improve
labpilot run --goal "Bounded inconclusive fixture" --outcomes inconclusive \
  --max-iterations 2 --max-experiments 2 --max-failed-experiments 1 --max-replans 1
labpilot --verbose run --goal "Logged fixture"
```

Library callers can construct `ResearchState` with a custom `Baseline` and inject
`ResearchServices` into `graph.workflow.execute`. The CLI deliberately exposes only
a small set of fake and Docker execution options.

Run the predefined Phase 3 MNIST inner-loop search:

```bash
labpilot prepare-example .labpilot/baselines/mnist-hpo
labpilot run --goal "Optimize MNIST regularization" \
  --executor docker --repo .labpilot/baselines/mnist-hpo \
  --hpo --trials 6 --sampler-seed 42 \
  --max-replans 0 --min-delta 0.001
labpilot status <research-id>
```

`--hpo` requires Docker execution. `--trials` sets both the study plan and HPO trial limit. The default Docker HPO
experiment budget includes one measured baseline plus every requested trial.
`--sampler-seed` controls the reproducible Phase 3 TPE policy. `status` and the
final run output show every trial, its parameters, metric, runtime, best trial,
baseline, and raw delta. Use `--stop-after N` and then `resume` to exercise a fresh
process restart; committed trials are not executed again.

## Development

```bash
pytest
ruff check .
ruff format --check .
mypy src
```

Tests block socket connections and DNS resolution and remove API keys. Coverage
includes domain validation and provenance, decision thresholds in both directions,
all routing outcomes, each budget limit, fake determinism, stale database writes,
restart at every nonterminal step of a two-iteration run, exceptions before commit,
committed experiments not rerunning, and CLI behavior. Tests use temporary databases.

The [measured Phase 2 report](docs/phase2-report.md) and
[measured Phase 3 report](docs/phase3-report.md) record the local demos and
verification results.

## Phase 2: isolated real execution

```text
Clean baseline repository at a recorded commit
    ↓
Detached, UUID-named Git worktree
    ↓
Validate and apply supplied unified diff (candidate only)
    ↓
Capture actual diff and a copy of regular tracked source files
    ↓
Docker: read-only source, writable outputs, network disabled
    ↓
outputs/metrics.json → typed MetricReport → persisted ExperimentResult
    ↓
Measured baseline comparison → KEEP / REJECT / REPLAN
```

The baseline and candidate use the same `DockerExperimentRunner`. A new `baseline`
workflow step records the unmodified experiment and replaces the numerical
baseline with its measured primary metric. A candidate then uses the predefined
0.0 → 0.3 dropout patch. The baseline counts toward `max_experiments`; both baseline
and candidate failures count toward the failure cap. Baseline retries consume
replan slots without inventing a hypothesis iteration. Two experiments and zero
replans produce a single baseline/candidate comparison.

The baseline checkout must be a clean **dedicated repository root**. Worktree
registration necessarily updates Git's administrative metadata, but neither its
HEAD nor its tracked/untracked working-tree contents are changed by experiments.
Each real result records a post-execution HEAD and cleanliness check. Runtime
storage must be outside the baseline repository. Cleanup verifies that a target
is a UUID-named direct child of the managed root and is registered to that baseline.
It refuses unrelated paths and symlinks.

### Run the MNIST example

Prerequisites: Python 3.11+, Git, and a running Docker daemon. No GPU is needed.
Initial image preparation downloads dependencies and MNIST; training runs with
networking disabled. See [the example README](examples/mnist_baseline/README.md)
for its data split, model configuration, and reproducibility limits.

```bash
labpilot prepare-example .labpilot/baselines/mnist
labpilot run --goal "Does dropout improve validation accuracy?" \
  --executor docker --repo .labpilot/baselines/mnist \
  --max-experiments 2 --max-replans 0 --min-delta 0.001 --stop-after 5
labpilot status <research-id>
labpilot resume <research-id>
```

The preparation command copies and commits the template into a new repository;
it refuses existing destinations. In Docker mode, step 3 completes the baseline
and step 5 completes the first candidate. Pausing there leaves `next_step=analyze`.
A fresh `resume` process compares the already persisted metrics without repeating
training. `status --json` exposes both experiment results, their provenance, and
the final decision rationale.

Options include `--patch FILE`, `--image IMAGE`, `--reuse-image`, `--timeout SECONDS`,
`--runtime-root PATH`, `--min-delta`, and the existing budget flags. With image reuse,
the caller is responsible for providing an image with suitable dependencies/data.
`ExperimentConfig.metric_name` is the primary metric name; its `primary_metric`
property exposes the same value. Direction is explicit in `ExperimentConfig` and
`Baseline`. Library callers can select another objective/direction and training
command without placing execution logic in graph nodes.

### Docker and artifacts

`DockerClient` handles image preparation, container creation, attachment, exit-code
inspection, timeout killing, and removal. The runner coordinates it with separate
worktree and metric services. Docker commands use argument lists, never a host
shell. The resolved immutable image ID, command, resource limits, and container ID
are retained. The container has a read-only root filesystem and source mount,
network `none`, dropped capabilities, no-new-privileges, two CPUs, 2 GiB memory,
a PID limit, a temporary filesystem, and one writable output mount. Neither the
Docker socket nor the baseline checkout is mounted. These controls use Docker's
[documented container options](https://docs.docker.com/reference/cli/docker/container/run/).

MNIST is cached in an image layer, verified by torchvision's dataset downloader,
and opened with `download=False` during training. Dependencies and dataset
preparation may use the network during builds. Direct Python dependencies are
pinned; transitive dependencies and the base image tag are not fully locked.
Actual image IDs and complete source snapshots identify the environment/code used
for a measured result. This is not a promise of bit-level reproducibility across
architectures or future image rebuilds.

```text
.labpilot/
├── baselines/mnist/                 # Dedicated clean Git repository
├── worktrees/<experiment-id>/       # Temporary; removed after execution
└── runs/<research-id>/<experiment-id>/
    ├── stdout.log                  # Build/training stdout
    ├── stderr.log                  # Build/training stderr
    ├── patch.diff
    ├── actual.diff
    ├── provenance.json
    ├── source/                     # Retained tracked-source snapshot; no .git
    └── outputs/metrics.json
```

`ResearchState.experiments[*].result.execution` stores typed provenance, including
identity, baseline commit, worktree identity, actual diff, source hash,
configuration text, seed, image/container identity, command, timestamps, total
runtime, exit code, metric report, failure reason, and cleanup warnings. Logs stay
on disk. The total runtime includes preparation, execution, validation, and cleanup.
The database remains authoritative for ordinary resume; artifact retention is
manual in this phase.

### Metrics and failures

The training command must write a regular, non-symlink file at
`outputs/metrics.json`, no larger than 1 MiB:

```json
{
  "schema_version": 1,
  "metrics": {
    "validation_accuracy": 0.91,
    "validation_loss": 0.25
  },
  "metadata": {"seed": 42, "epochs": 2}
}
```

These numbers illustrate the schema, not a reported experiment. `metrics` is an
explicit mapping of metric names to finite JSON numbers. Metadata is optional;
when present, its seed must match the experiment. Duplicate keys, nonfinite values,
unknown fields, invalid versions, malformed JSON, missing files, and a missing
primary metric are failures. Natural-language logs are never used for comparison.

Invalid/conflicting patches, Docker build failures, nonzero exits, timeouts, and
metric errors return FAILED results for the existing decision policy. Timeout is
also distinguished in execution provenance. Worktree/container cleanup warnings
are logged and retained separately, preserving a valid metric or the original
failure. Unexpected storage/programming errors still propagate rather than being
misrepresented as a scientific result.

### Docker tests

```bash
pytest                 # Fast offline suite; Docker tests deselected
pytest -m docker       # Real MNIST, persisted resume, timeout, exit and missing metrics
ruff check .
ruff format --check .
mypy src
```

Docker tests skip only when Docker is unavailable. Once a daemon is reachable,
build and execution failures fail tests. Initial integration-test image preparation
may need network access; subsequent training is offline. Unit tests use temporary
Git repositories and mocked Docker boundaries, with socket access blocked.

## Phase 3: hierarchical HPO

```text
Hypothesis + fixed candidate patch
    ↓
ExperimentPlan → typed SearchSpace
    ↓
Persistent Optuna study (seeded TPE)
    ↓
Sampled parameters → validated TrainingOverrides
    ↓
DockerExperimentRunner → outputs/metrics.json
    ↓
LabPilot Trial + Optuna tell
    ↓ repeat within budget
Best successful trial → measured baseline → DecisionEngine
```

The outer loop chooses what code or architecture to try: a hypothesis may carry one
fixed patch and a search space. The inner loop chooses numeric and categorical
values for that fixed candidate. Phase 3 implements only the inner loop. Optuna,
rather than a language model, samples `learning_rate`, `dropout`, `hidden_dim`, and
`batch_size` for the MNIST fixture.

`SearchSpace` is a discriminated union of `FloatParameter`, `IntParameter`, and
`CategoricalParameter`. It rejects reversed bounds, incompatible log/step options,
steps that do not divide the range, empty or duplicate choices, and duplicate names.
Sampled values cross into execution only through the validated `TrainingOverrides`
model. The runner writes `labpilot-parameters.json` into the captured trial source;
the training script reads only those four supported fields. Each trial retains the
same candidate patch but gets a separate worktree, artifact directory, container,
experiment ID, and provenance record.

Each study has a stable UUID/name and stores Optuna data at:

```text
.labpilot/runs/<research-id>/studies/<study-id>/
├── optuna.sqlite3     # Optuna-owned suggestions and ask/tell states
└── study.json         # Regenerable human/machine-readable LabPilot view
```

The LabPilot snapshot contains typed `ExperimentPlan`, `OptimizationStudy`, and
`Trial` records. Reserving a trial charges `experiments` and `hpo_trials` together,
exactly once. Execution failure also charges the existing failed-experiment counter,
is reported to Optuna as failed, and does not stop later trials while budget remains.
The study ends FAILED when it has no successful trial. Advanced pruning is omitted
because the current trainer emits only final metrics; a `NopPruner` avoids inventing
intermediate observations.

Best-trial selection considers successful trials only, respects maximize/minimize,
and breaks equal metrics by Optuna trial number then UUID. The selected metric is
passed to the existing `DecisionEngine`; the baseline is measured once and is never
an Optuna trial. The per-trial seed policy is recorded as
`seed_plus_trial_number_v1`, so a restarted process reproduces the same remaining
suggestion sequence without relying on an in-memory sampler RNG.

## Limitations

- Experiment execution, metrics, and inner-loop HPO are real; literature and
  hypothesis inputs remain explicit deterministic fixtures or supplied patches.
- One local executor per run; no leases, distributed scheduling, or automatic
  reconciliation after a process crash during active Docker execution.
- Worktrees and containers are cleaned up normally, but cleanup failures can leave
  resources for manual inspection. Source snapshots, logs, images, and datasets are retained.
- Only text patches and regular tracked source files are supported; symlinks,
  submodules, Git metadata, and pre-existing output paths are rejected.
- Dockerfiles, images, repositories, and patches are trusted local inputs. Docker
  isolation here is not a complete defense against intentionally hostile code.
- Schema extensions are backward-compatible; migration tooling remains deferred.
- No LLM calls, generated patches, real literature APIs, MLflow, web UI,
  distributed execution, paper writing, or vector database.
- The current HPO implementation is sequential and supports final metrics only.
  It has no pruning, executor leases, parallel workers, or active-container recovery.

## Roadmap

| Phase | Scope |
| --- | --- |
| 1 | Typed state, deterministic orchestration, SQLite checkpoint/resume |
| 2 | Git worktrees, supplied patches, Docker execution, real MNIST metrics |
| **3 (current)** | Typed, persisted, budgeted Optuna HPO through Docker trials |
| 4 | LLM hypothesis and code patch generation |
| 5 | arXiv and Semantic Scholar evidence grounding |
| 6 | Benchmarks and evaluation |

### Exact Phase 4 TODOs (not implemented)

- [ ] Add a real `LLMClient` behind an injectable interface.
- [ ] Validate all model output through structured schemas with explicit retry/failure handling.
- [ ] Inspect repository context within bounded, auditable inputs.
- [ ] Generate evidence-linked hypotheses and typed `ExperimentPlan` proposals.
- [ ] Generate and validate candidate code patches before isolated execution.
- [ ] Preserve the outer-loop patch / inner-loop Optuna boundary.
- [ ] Account for model tokens, cost, attempts, and failure budgets in `ResearchBudget`.
- [ ] Persist prompts, model identity, structured responses, and provenance without secrets.
- [ ] Add deterministic fake-client tests before any opt-in network integration tests.
