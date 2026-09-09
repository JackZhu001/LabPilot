# LabPilot

**Autonomous ML Research & Experimentation Agent**

LabPilot aims to make ML research reproducible, traceable, and bounded: every
hypothesis should connect to evidence, every experiment to a hypothesis, and every
decision to a measurable result.

```text
Literature → Evidence → Hypothesis → Experiment → Metric → Keep / Reject / Replan
```

**Current scope: Phase 1 — foundational architecture.** The complete control loop
runs with deterministic, explicitly synthetic fixtures. It does not retrieve real
papers, generate patches, train models, or call an LLM. No API keys, Docker, GPU,
or network access are required to run the workflow or tests after installation.

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
- CLI inspection, JSON export to stdout, and standard logging with research,
  hypothesis, and experiment identifiers.

`CodePatch` and `Trial` are typed contracts. Phase 1 creates one simulated trial per
experiment and no code patches. Multiple trials and patch execution are future work.

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
START → literature → evidence → hypothesis → experiment → analyze → decision
                                   ↑                                │
                                   └────── REPLAN, budget allows ────┤
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
experiment. The baseline stays fixed for the run; KEEP terminates Phase 1.

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
rejected. Use one executor per run in Phase 1. A future runner needs an idempotency
and reconciliation contract before real side effects are introduced.

The fake outcome sequence and seed are persisted in the state. Restarting a CLI
process reconstructs the same fake services; it does not depend on a hidden random
number generator or in-memory call counter. IDs are stable within a research ID,
and control flow is deterministic. New research IDs and wall-clock timestamps vary.

## Project structure

```text
LabPilot/
├── pyproject.toml
├── uv.lock
├── README.md
├── .env.example
├── .gitignore
├── src/labpilot/
│   ├── __init__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   └── app.py
│   ├── decisions/
│   │   ├── __init__.py
│   │   └── engine.py
│   ├── graph/
│   │   ├── __init__.py
│   │   └── workflow.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── budget.py
│   │   ├── common.py
│   │   ├── experiments.py
│   │   ├── literature.py
│   │   └── state.py
│   ├── persistence/
│   │   ├── __init__.py
│   │   └── repository.py
│   └── services/
│       ├── __init__.py
│       ├── fakes.py
│       ├── interfaces.py
│       └── workflow.py
└── tests/
    ├── conftest.py
    ├── test_cli.py
    ├── test_decisions.py
    ├── test_fakes.py
    ├── test_models.py
    ├── test_persistence.py
    └── test_workflow.py
```

Empty placeholder packages for LLMs, prompts, Docker, and search providers are
intentionally deferred. Add typed integration metadata alongside a schema migration
when those contracts exist; no speculative catch-all metadata dictionary is used.

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
the options needed for the Phase 1 demonstrations.

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

## Limitations

- Synthetic evidence and metrics are fixtures, not scientific results.
- Execution is synchronous, local, and single-executor per run.
- Checkpoints are whole snapshots at node boundaries, not mid-experiment recovery.
- Schema versioning is present; migration tooling and old-version migrations are deferred.
- No real literature APIs, LLM calls, patch generation, Git isolation, Docker, HPO,
  MLflow, distributed execution, web UI, paper writing, or vector database.

## Roadmap

| Phase | Scope |
| --- | --- |
| **1 (current)** | Research state, deterministic orchestration, persistence, checkpoint/resume |
| 2 | Git worktree and Docker experiment execution |
| 3 | Optuna hyperparameter optimization |
| 4 | LLM hypothesis and code patch generation |
| 5 | arXiv and Semantic Scholar evidence grounding |
| 6 | Benchmarks and evaluation |

### Exact Phase 2 implementation checklist

- [ ] Define typed workspace, base commit, patch digest, container image digest,
      artifact manifest, and execution identity models; add a versioned state migration.
- [ ] Implement Git worktree lifecycle per experiment with explicit cleanup and
      preservation of the user's checkout.
- [ ] Apply and validate a supplied patch in its worktree; do not generate patches yet.
- [ ] Implement a Docker-backed `ExperimentRunner` with an explicit command contract,
      pinned image, resource limits, timeout, cancellation, and controlled mounts/network.
- [ ] Capture exit status, stdout/stderr, artifact paths, and a validated metric result;
      distinguish infrastructure failures from rejected scientific hypotheses.
- [ ] Introduce durable execution intent, idempotent experiment identity, an executor
      lease, and restart reconciliation before enabling external side effects.
- [ ] Charge experiment/failure budgets once per execution identity, including retries
      and crashes, and retain full provenance from supplied patch through result.
- [ ] Add fixture-repository and container integration tests for success, failure,
      timeout, cancellation, cleanup, stale executors, and crash/resume; keep the
      existing unit suite offline and Docker-free.
- [ ] Document prerequisites and add an explicit CLI execution-mode selector while
      preserving the deterministic fake mode.

Optuna, LLM patch generation, and literature API integration remain in later phases.
