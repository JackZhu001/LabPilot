# Phase 8 — DeepSeek-guided multi-seed evaluation

The roadmap had no Phase 8 definition. This increment connects the existing bounded
DeepSeek agent to measured experiments, then evaluates two model-proposed dropout
settings across the same eight seeds. It remains a small, single-dataset study.

## DeepSeek setup and live run

- The local API key is stored in the ignored root `.env` file with mode `600`; it is
  not committed or copied into prompts, state, reports, or logs. Source `.env` into
  the shell before running LabPilot.
- Model: `deepseek-flash`, now the current Flash API model name. DeepSeek documents
  that `deepseek-v4-pro` requests route to V4.1-Flash after 2026-09-14; see the
  [official API changelog](https://api-docs.deepseek.com/updates/).
- Successful Research ID: `e7ce8672-6827-4ccd-bc57-f8a869fe38d1`.
- Hypothesis: set `dropout` to `0.3` in `config.yaml`, leaving source code unchanged.
- Seed 42 baseline: `0.9255`; candidate: `0.9270`; paired delta: `+0.0015`; decision:
  `KEEP` at `min_delta=0.001`.
- The run used 5 accepted DeepSeek calls and 12,404 tokens. All Phase 8 attempts in
  the local SQLite database used 13 accepted calls and 35,209 tokens; early attempts
  that stopped before a candidate result are retained locally but excluded from the
  comparisons below.
- Docker image digest: `sha256:0fd7a733d0f30af943d8ef09dc4cb50bdade0623194358fbe17c890ddbe6ad8f`.
  Baseline repository commit: `54148c39bf8285f760f04435c07a963b3e3b37d9`.

The seed-42 result is a repeat of the same seed and intervention already present in
Phase 7, not independent confirmation. The agent selected a single configuration
change; it did not author or modify model source code.

## Matched eight-seed comparison

Both candidates use the same cached MNIST training split. For each seed, the training
and validation subsets are selected with that seed, and baseline/candidate are paired
on that same split. Each evaluation used the same image digest, baseline commit,
`min_delta=0.001`, and seeds 42–49. The `dropout=0.2` value came from an earlier
DeepSeek hypothesis; its config-only suggestion was translated to a one-line config
diff after that run stopped at plan validation. `dropout=0.3` is the intervention
selected by the successful live agent run.

| Seed | Baseline | Dropout 0.2 | Delta | Decision | Dropout 0.3 | Delta | Decision |
|---:|---:|---:|---:|---|---:|---:|---|
| 42 | 0.9255 | 0.9265 | +0.0010 | KEEP | 0.9270 | +0.0015 | KEEP |
| 43 | 0.9285 | 0.9295 | +0.0010 | KEEP | 0.9260 | -0.0025 | REJECT |
| 44 | 0.9220 | 0.9210 | -0.0010 | REJECT | 0.9225 | +0.0005 | REJECT |
| 45 | 0.9285 | 0.9290 | +0.0005 | REJECT | 0.9310 | +0.0025 | KEEP |
| 46 | 0.9255 | 0.9240 | -0.0015 | REJECT | 0.9240 | -0.0015 | REJECT |
| 47 | 0.9245 | 0.9230 | -0.0015 | REJECT | 0.9220 | -0.0025 | REJECT |
| 48 | 0.9335 | 0.9340 | +0.0005 | REJECT | 0.9315 | -0.0020 | REJECT |
| 49 | 0.9290 | 0.9265 | -0.0025 | REJECT | 0.9285 | -0.0005 | REJECT |

| Intervention | Mean paired improvement | Sample standard deviation | KEEP decisions |
|---|---:|---:|---:|
| Dropout 0.2 | -0.0004375 | 0.001348 | 2/8 |
| Dropout 0.3 | -0.0005625 | 0.001898 | 2/8 |

Neither candidate has a positive mean paired improvement, and both clear the decision
threshold on only two seeds. Do not promote either as a reliable improvement. The
single seed-42 `KEEP` result demonstrates the agent and execution path, not model
quality or generalization.

## Implementation and remaining work

- The default API model is now `deepseek-flash`.
- Repository inspection asks for a tracked path verbatim; experiment planning receives
  an explicit list of allowed paths. Advisory inspection paths are reduced to tracked
  files, while modification targets remain restricted to known tracked files.
- Benchmark cohorts now include a hash of the distinct candidate interventions and the
  observed immutable Docker image ID. Repeated identical attempts do not create separate
  cohorts, and different dropout values cannot be pooled as one treatment.
- The System page and bilingual README show Phase 8 progress.
- A completed CONFIG_ONLY proposal can now be handed directly to `labpilot evaluate
  --from-run RUN_ID`. It validates source completion, proposal type, goal, repository,
  commit, image, and command; candidate runs inherit the exact typed overrides while
  baselines remain unmodified. The evaluation manifest, seed snapshots, and benchmark
  summary retain source IDs and the applied settings.
- End-to-end handoff evaluation: `8ad63c37-5f03-4364-92d1-dffd5f986038`, using the
  saved DeepSeek run above and seeds 42–49. All eight seed runs completed; the saved
  baselines had no override, every candidate recorded `dropout=0.3`, and every seed
  retained the source Research, hypothesis, and plan IDs. The mean paired improvement
  was `-0.0005625` with a sample standard deviation of `0.001898`; 2/8 seeds reached
  KEEP. These reuse the existing MNIST seeds and are a workflow/reproducibility check,
  not new independent evidence.

## Phase 9 follow-up

Phase 9 delivered a second, source-linked benchmark on FashionMNIST. The dataset
profile, metadata contract, and results are documented in [the Phase 9 report](phase9-report.md).
The measured effect does not justify promoting the proposed setting.

The failed setup and validation attempts are preserved in ignored local records under
`.labpilot/phase8-deepseek/`. They produced no candidate metric included in the table.
