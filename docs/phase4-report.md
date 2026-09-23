# Phase 4 measured report: structured DeepSeek outer loop

Measured on 2026-09-09 using the real DeepSeek OpenAI-compatible API and real
Docker CPU execution. No credential is stored in this report, ResearchState,
SQLite, prompts, logs, or experiment artifacts.

## Agent harness

```text
Research goal
    ↓
Bounded repository inspector
    ↓
Measured Docker baseline
    ↓
Hypothesis role → deterministic ranking
    ↓
Experiment planning role
    ↓
Config override / validated patch / Optuna inner loop
    ↓
Docker metric → DecisionEngine
    ↓
Supplemental critic → KEEP / REJECT / REPLAN
```

Each role consumes typed context and returns a Pydantic model. DeepSeek does not
receive shell access and cannot change the baseline checkout. It proposes actions;
the repository selector, patch policy, WorktreeManager, DockerExperimentRunner,
Optuna, metrics parser, budget, and DecisionEngine enforce them.

The provider-independent `LLMClient` returns structured output plus one usage
record for every accepted provider response. `DeepSeekLLMClient` uses JSON mode,
includes the response schema in the request, validates the JSON, supplies bounded
validation feedback, and retries only within the configured limit. The API key is
read from `DEEPSEEK_API_KEY` only when constructing the provider transport.

## Repository and patch safety

The inspector considered tracked files only and selected 7,574 characters from six
small text files: `README.md`, `train.py`, `model.py`, `config.yaml`,
`requirements.txt`, and `download.py`. It excluded Git metadata, environments,
datasets, outputs, logs, binaries, `.env*`, credential names, and oversized files.
The selected content itself was not persisted in ResearchState.

Patch proposals are restricted to the plan's known tracked targets and exact base
SHA. Validation rejects traversal, absolute paths, `.git`, secret/runtime targets,
binary/symlink/submodule patches, excessive size/file count, and destructive command
execution. A disposable managed worktree runs `git apply --check`, applies the
patch, captures the actual diff, and compiles changed Python before the proposal is
accepted. A real opt-in DeepSeek test generated a one-file unified diff, passed this
pipeline, and left the baseline unchanged.

## Real end-to-end run

Research ID: `675b09a4-3ddd-415c-a93f-7a675c9d1dd2`

Research goal: **Improve validation accuracy while keeping the model lightweight**  
DeepSeek model: **deepseek-v4-pro**  
LLM calls: **4**  
Input tokens: **6,512**  
Output tokens: **1,526**  
Total tokens: **8,038**  
Recorded LLM latency: **22.989115832999232 seconds**

DeepSeek generated three repository/history-grounded hypotheses:

1. Increase training epochs from 2 to 5 while keeping other parameters fixed.
2. Increase hidden dimension from 128 to 256.
3. Add dropout 0.2 after the hidden activation.

The deterministic ranking selected hypothesis 1 from confidence, expected impact,
estimated cost, duplicate history, and stable tie-breaking.

Selected hypothesis: **Increase the number of training epochs from 2 to 5 while
keeping other hyperparameters fixed.**  
Change type: **CONFIG_ONLY**  
Patch summary: **No source patch required; validated `epochs=5` training override.**  
SearchSpace: **None**  
HPO trials: **0**  
Docker candidate trials: **1**

The generated experiment plan inspected `config.yaml` and `train.py`, retained the
configured `validation_accuracy` maximize objective, estimated 300 seconds, and
required configuration, entrypoint, lightweight-model, metric, and determinism
checks. The executor used the validated `TrainingOverrides(epochs=5)` config file.

Baseline metric: **0.9255**  
Best candidate metric: **0.9445**  
Delta: **+0.019000000000000017**  
Decision: **KEEP**  
Replans: **0**  
Total run duration from persisted timestamps: **30.902228 seconds**  
Measured Docker execution runtime: **7.743732957998873 seconds**

The `DecisionEngine` selected KEEP because the measured improvement exceeded the
configured `0.001` threshold. The critic then explained that fixed decision; it had
no route or schema authority to alter it.

Baseline SHA before: `54148c39bf8285f760f04435c07a963b3e3b37d9`  
Baseline SHA after: `54148c39bf8285f760f04435c07a963b3e3b37d9`  
Baseline clean: **true**

Both experiment provenance records report a clean baseline and unchanged HEAD.
No LabPilot containers remained after the run.

Local ignored audit files:

- `.labpilot/phase4-demo.sqlite3`
- `.labpilot/phase4-demo-run.txt`
- `.labpilot/phase4-demo-state.json`
- `.labpilot/runs/675b09a4-3ddd-415c-a93f-7a675c9d1dd2/`

## Checkpoint, accounting, and failure behavior

Repository inspection, hypothesis selection, planning, patch acceptance, trial
execution, analysis, and critique are separate durable steps. Ordinary resume starts
at the saved cursor and does not repeat completed calls or experiments. Request IDs,
operation, prompt template version, model, input/output/cached/reasoning tokens, and
latency are persisted. `llm_calls` and `llm_tokens` must exactly equal those records.

Transient provider, authentication, configuration, and budget failures produce a
BLOCKED state with the retry cursor. Exhausted structured-output validation produces
a terminal FAILED state. Invalid patches receive at most the configured repair
attempts; final preflight failure is represented as a failed experiment and enters
the deterministic REPLAN/REJECT policy without spending Docker or HPO work.

## Verification and limits

The offline suite covers request construction, settings, missing credentials,
structured validation retry, usage and token budgets, context filtering, secret
exclusion, hypothesis duplicates, plan contracts, HPO guardrails, patch safety,
repair limits, critic authority, and LLM-step resume. Live tests cover structured
DeepSeek connectivity and a real validated unified diff. Docker tests continue to
cover MNIST execution, resume, HPO, timeout, nonzero exit, and missing metrics.

Final verification after the last source change:

- Python 3.13 offline suite: **218 passed, 7 deselected in 15.81s**.
- Python 3.11 offline suite: **218 passed, 7 deselected in 23.37s**.
- Live DeepSeek suite: **2 passed, 223 deselected in 7.84s**.
- Docker suite: **5 passed, 220 deselected in 22.82s** using the unchanged,
  previously built test image. The registry metadata endpoint was unavailable during
  the final rebuild attempt; an earlier clean rebuild and run passed in 33.14s.
- Ruff check: **passed**.
- Ruff format check: **83 files already formatted**.
- Strict mypy: **no issues in 47 source files**.
- `uv lock --check` and `git diff --check`: **passed**.

Phase 4 remains sequential and local. It does not provide executor leases or
recovery during an active Docker process. Context selection uses deterministic size
and path rules rather than semantic embeddings. Monetary cost is not persisted
because pricing is intentionally external and changeable; exact tokens are stored.
Only final training metrics are available, so Phase 3 pruning remains inactive.

Phase 5 is not implemented. Its boundary is arXiv and Semantic Scholar retrieval,
paper ingestion, claim extraction, SUPPORT/CONTRADICT/NEUTRAL relations,
evidence-grounded hypothesis generation, and citation provenance.
