# Phase 2 implementation and measured validation

Run date: 2026-09-09. Research ID: `7ba5ca38-1d49-4901-bc98-a108a11942ea`.

## Architecture and changes

Phase 1's DecisionEngine, runner Protocol, SQLite repository, and checkpoint model
remain in place. A baseline step runs the unmodified code through the same Docker
runner as candidate experiments. Domain transitions and the CLI gained only the
configuration, baseline handling, and result recording needed for real execution.
No executor leases, LLM calls, HPO, or Phase 3 behavior were introduced.

Added:

- `execution/git.py`: detached worktree management, clean baseline checks,
  guarded patch application, actual diff capture, managed-only cleanup.
- `execution/docker.py`: image preparation, controlled container creation,
  stdout/stderr capture, exit inspection, timeout and container cleanup.
- `execution/runner.py`: coordinates execution and creates typed provenance.
- `execution/artifacts.py` and `execution/metrics.py`: retained source/log paths
  and strict versioned metric parsing.
- `models/execution.py`: environment/status/configuration/artifact/Git/Docker/
  metric/provenance contracts.
- `services/real.py`: Docker service selection, dedicated example preparation,
  predefined dropout patch, and checkpoint-ready real result transitions.
- `examples/mnist_baseline/`: CPU PyTorch model, configuration, training,
  dependency and dataset image preparation, and documentation.
- Five offline execution test modules and four Docker integration cases.

Modified: `models/common.py`, `models/experiments.py`, `models/state.py`,
`services/workflow.py`, `graph/workflow.py`, `cli/app.py`, `pyproject.toml`, and README.
Original Phase 1 tests remain intact. New fields have backward-compatible defaults;
old schema-version-1 snapshots load without a database migration.

## Relevant repository tree

```text
LabPilot/
├── pyproject.toml
├── uv.lock
├── README.md
├── .env.example
├── .gitignore
├── docs/phase2-report.md
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
│       ├── models/
│       │   ├── __init__.py
│       │   ├── budget.py
│       │   ├── common.py
│       │   ├── execution.py
│       │   ├── experiments.py
│       │   ├── literature.py
│       │   └── state.py
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
│   ├── test_metric_reports.py
│   ├── test_models.py
│   ├── test_persistence.py
│   ├── test_real_runner.py
│   ├── test_real_workflow.py
│   └── test_workflow.py
```

## Git and Docker design

Experiments use detached worktrees named by experiment UUID. The baseline must be
a clean dedicated repository root at the recorded SHA. Patches are checked and
applied only in registered managed worktrees. Their original bytes and actual Git
diff are retained. Regular tracked files are exported to a retained source snapshot;
Git metadata, symlinks, submodules, and pre-existing outputs are excluded/rejected.

Containers receive read-only source and a writable outputs directory, not the
baseline or Docker socket. Training runs with network disabled, a read-only root,
capability restrictions, two CPU cores, 2 GiB memory, a PID cap, and a timeout.
MNIST and dependencies are prepared in cached image layers before execution.

The first attempted demo failed during a 30-second Docker container creation
operation, before training, while preserving the baseline. Creation now has a
separate 120-second bound and label-verified cleanup for uncertain creation
failures. The abandoned container from that attempt was removed. The subsequent
successful run below and all Docker integration tests exercised the corrected code.

## Metrics and persistence contract

`outputs/metrics.json` contains `schema_version: 1`, a mapping of named finite
JSON-number metrics, and optional typed seed/epoch metadata. The configured
`ExperimentConfig.metric_name` (also exposed as `primary_metric`) must exist.
Duplicate keys, nonfinite values, wrong schemas, malformed/missing files, and seed
mismatches are failures. Logs never determine metrics.

Each completed step commits a validated ResearchState and next cursor to SQLite.
Both baseline and candidate count once against the experiment budget. Baseline
failures and candidate failures follow the existing replan/reject policy.
Each result includes source/config/seed, patch linkage, commit/diff/worktree,
image/container identity, timestamps/runtime, exit code, metrics, failure and
cleanup details. Large logs remain files. Artifact provenance is an audit record,
not a competing resume checkpoint.

## Commands and actual results

Commands ran in the existing `.venv` unless another interpreter is shown.

| Command | Actual result |
| --- | --- |
| `pytest -q` | 153 passed, 4 Docker cases deselected |
| `.labpilot/python311/bin/pytest -q` | 153 passed, 4 deselected (Python 3.11.14) |
| `pytest -m docker -v` | 4 passed, 153 deselected, 11.98 seconds |
| `ruff check .` | All checks passed |
| `ruff format --check .` | Passed; 47 files already formatted |
| `mypy src` | No issues in 27 source files |
| `labpilot run --goal "Phase 1 compatibility smoke test" --executor fake` | Completed with KEEP |

Docker integration cases cover a real baseline and patched MNIST run, fresh-store
resume without re-execution, timeout and cleanup, exit code 7, and missing metrics.
Unit tests cover all original Phase 1 behavior, Git isolation, unsafe/invalid/conflicting
patches, metrics validation, build/runtime failures, cleanup warnings, raw patch
whitespace preservation, budgets, and full execution provenance persistence.

The real demo commands were:

```bash
labpilot prepare-example .labpilot/baselines/mnist
labpilot run --goal "Does dropout improve validation accuracy?" \
  --executor docker --repo .labpilot/baselines/mnist \
  --max-experiments 2 --max-replans 0 --min-delta 0.001 --stop-after 5
labpilot resume 7ba5ca38-1d49-4901-bc98-a108a11942ea
labpilot status 7ba5ca38-1d49-4901-bc98-a108a11942ea --json
```

## Actual MNIST results

| Measurement | Baseline | Dropout candidate |
| --- | ---: | ---: |
| Dropout | 0.0 | 0.3 |
| Validation accuracy | 0.9255 | 0.9270 |
| Validation loss | 0.2393279272 | 0.2394287736 |
| Total execution runtime | 7.615615 seconds | 4.470243 seconds |
| Exit code | 0 | 0 |

Measured accuracy delta: **+0.0015**
(0.15 percentage points). Minimum improvement threshold: **0.001**.
Decision: **KEEP**, produced by the existing deterministic engine.

Both runs used seed 42, two epochs, 10,000 training examples, and 2,000 disjoint
validation examples from a seeded permutation of MNIST's training split. The
held-out official test split was not used. These are development measurements,
not a general claim about dropout or a full MNIST benchmark. Runtime includes
cached image preparation, execution, validation, and cleanup; the first dependency
and dataset download was separate and is not included in these timings.

Baseline image identity: `sha256:2b3c9b05e806fc0e98c45d0edf5a3107404c1f268b4ac37b52f3a3425c05fc99`.
Candidate image identity: `sha256:9c2c0325bd34ef60eb4fbcc7bb41e99e8b9084d73580fa8c7c1efb781df3944b`.
Docker build exports can have different manifest identities even when dependency
layers are reused; each experiment retains the exact identity it executed.

Baseline SHA before: `74481d37a3e6085d1fd1e6d017a781f895cde78c`.
Baseline SHA after: `74481d37a3e6085d1fd1e6d017a781f895cde78c`.
Baseline clean after experiment: **true**.
Both recorded integrity checks passed; subsequent `git status --porcelain` was
empty. Both worktrees and containers were removed, with no cleanup warnings.

The run paused at revision 5 with two committed experiments and `next_step=analyze`.
A new CLI process resumed to revision 7, COMPLETED, with
exactly the same two experiment results and a final KEEP decision.

Local audit files remain under:

- `.labpilot/phase2-demo-state.json`
- `.labpilot/phase2-demo-run.txt` and `.labpilot/phase2-demo-resume.txt`
- `.labpilot/phase2-docker-tests.txt`
- `.labpilot/runs/7ba5ca38-1d49-4901-bc98-a108a11942ea/24b67028-0f27-5d74-91c3-9e4385aa6b49/`
- `.labpilot/runs/7ba5ca38-1d49-4901-bc98-a108a11942ea/d2f65154-f321-5e64-b044-c166e87eaf68/`

These runtime files are ignored by Git. The two experiment directories retain
stdout/stderr, metrics, original patch, actual diff, source snapshot, and provenance.

## Known limitations

- Single local executor per run. Ordinary committed-step resume works; process
  crashes during active execution may require manual reconciliation. No leases or
  stale-worker coordination were added.
- Existing artifact directories are refused instead of silently overwritten.
  Unexpected filesystem/database failures propagate.
- Dockerfiles/images/patches are trusted local inputs, not a hostile-code security boundary.
- Direct ML dependencies are pinned; transitive dependencies and base image tags
  are not fully locked. Cross-platform bit-identical training is not promised.
- Dataset/image caches and audit artifacts are retained; automatic retention is deferred.
- The setup/fixture stages are synthetic; no literature grounding, LLM patch
  generation, or hyperparameter optimization is implemented.

## Exact Phase 3 TODOs

1. Define typed categorical, integer, and floating-point search spaces and validation.
2. Persist Optuna study identity and reproducible sampler configuration.
3. Support multiple uniquely identified trials per hypothesis, each with configuration,
   seed, execution provenance, result, and budget accounting.
4. Map suggested parameters to validated configurations while preserving worktree
   isolation and the Docker/metric contracts.
5. Define intermediate metric reporting and pruning/cancellation semantics.
6. Select the best eligible completed trial using objective direction and deterministic tie-breaking.
7. Persist study/trial progress and resume without rerunning committed trials.
8. Add bounded offline adapter tests and optional Docker search integration tests.
9. Add minimal CLI search options and document budgets, pruning, and reproducibility.
