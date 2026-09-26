# Phase 6 — reports and evaluation

Validated locally on 2026-09-26. Phase 6 provides deterministic snapshot reports,
observational multi-run benchmarks, CLI exports, and a connected frontend.

## Delivered

- `labpilot report RUN_ID --db PATH --format markdown|json`: saved hypotheses,
  paper/claim/evidence provenance, patches, experiment configurations, seeds,
  trials, decisions, resource usage, revision and SHA-256 snapshot fingerprint.
- `labpilot benchmark --db PATH` (repeatable) and optional repeated `--run-id`:
  recorded-condition cohorts, strategy summaries, improvement mean/sample standard
  deviation, KEEP rate, experiment/hypothesis/patch operational rates, tokens and
  execution time. JSON and Markdown exports are supported.
- Local read-only API and `/reports` frontend with run selection, report preview,
  source-run links and downloads. Preview details use one saved snapshot.
- Graphite/lime dashboard, interactive CSS 3D research model, pause control,
  reduced-motion support, persistent light/dark themes, responsive layouts and
  lazy-loaded HPO charts. No new frontend dependencies.

## Validation

- 238 offline tests passed; 9 Docker/live-provider tests deselected. No new training
  or paid LLM requests were needed for this phase.
- Ruff formatting/lint and strict mypy passed. Frontend production build and lint passed.
- Regression check covers minimizing objectives, absent measurements, duplicate and
  conflicting snapshots, JSON round-trip, deterministic legacy paper metadata, and CLI exports.
- HTTP checks through the frontend proxy verified report preview, Markdown/JSON
  attachment responses, matching fingerprints, and selected-run comparison.
- Browser checks verified the dashboard at desktop and narrow viewport sizes,
  light/dark switching, 3D pause/resume, report selection and report navigation.
- The default database plus the Phase 5 demo database produced 8 unique runs in
  6 recorded-condition cohorts. The Phase 5 report exported 31,166 bytes of Markdown.
  These are existing experiment results, not newly measured research outcomes.
- Initial JavaScript bundle: 402.86 kB (122.09 kB gzip); HPO chart route:
  328.52 kB (97.19 kB gzip). Before splitting, the initial bundle was 731.42 kB.

## Interpretation and limits

Benchmarks describe saved runs; they do not launch controlled ablations or establish
causal benefits of literature grounding. Cohorts match the recorded repository,
commit, image tag, command, objective, baseline, thresholds and experiment/HPO budgets.
Check dataset versions, image digests, model configuration and seed policies before
making scientific comparisons. Incomplete or unmeasured runs do not enter improvement
statistics; simulation results are separate. Execution success is not scientific success.
Dollar cost is unknown because billing rates are not recorded.

Exports contain complete state and provenance, not the referenced artifact files,
datasets or container images. Retain those separately for reproduction. Legacy paper
retrieval timestamps that were never recorded remain null; loading a snapshot no longer
invents a current timestamp and changes its report fingerprint. Exports reflect the
latest persisted revision at request time; retain downloaded snapshots to freeze a record.
