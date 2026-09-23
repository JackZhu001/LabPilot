# LabPilot Frontend

Research control plane UI for LabPilot — autonomous ML research and
experimentation agent. This frontend is isolated from the Python backend and
currently runs on **typed fixture data** that mirrors the real domain models
(`src/labpilot/models/*.py`, `src/labpilot/hpo/models.py`), including the
measured Phase 2 dropout experiment (research `7ba5ca38-…`, baseline 0.9255 →
candidate 0.9270, delta +0.0015, decision KEEP).

## Stack

- React 19 + TypeScript (Vite)
- Tailwind CSS v4 (design tokens in `src/index.css`)
- React Router
- Recharts (HPO trial chart)
- lucide-react icons
- IBM Plex Sans / IBM Plex Mono (self-hosted via Fontsource)

No state-management framework: React state + the `useRequest` hook +
the API service boundary.

## Commands

```bash
npm install     # install dependencies
npm run dev     # dev server (http://localhost:5173)
npm run build   # typecheck + production build (tsc -b && vite build)
npm run lint    # oxlint
npm run smoke   # SSR render smoke check of every route
npm run preview # serve the production build
```

## Architecture

```text
src/
├── components/
│   ├── layout/       AppShell (sidebar/topbar), PageHeader
│   ├── ui/           primitives (Panel, Badge, EmptyState, CodeDiff, …), status badges
│   ├── research/     ResearchLoop, BudgetProgress, ActivityTimeline,
│   │                 MetricSummary, ExperimentTable
│   └── hpo/          TrialChart, TrialTable + SearchSpacePanel
├── hooks/            useRequest (async request state)
├── lib/              cn + formatters (metrics, deltas, runtimes, SHAs)
├── mocks/            fixture data (real Phase 2 run + HPO preview + fake runs)
├── pages/            route pages (dashboard, runs, run tabs, experiment, HPO, …)
├── services/         labpilot-api.ts — the single data-access boundary
├── types/            domain.ts — typed after the Python models
├── router.tsx        route table (shared by main and the SSR smoke check)
└── main.tsx
```

**Data boundary:** components import only `services/labpilot-api.ts`. Fixtures
live in `src/mocks/` and are imported by the service layer alone. When the
backend exists, the service functions switch to HTTP fetches without touching
UI components.

## Routes

| Route | Content |
| --- | --- |
| `/dashboard` | Current research, loop, recent runs, activity timeline |
| `/runs` | Research run list |
| `/runs/:researchId` | Run detail (tabs: Overview, Experiments, HPO, Evidence, State) |
| `/runs/:researchId/experiments/:experimentId` | Experiment detail: config, Git/Docker provenance, diff, artifacts |
| `/runs/:researchId/hpo/:studyId` | Optuna study: best trial, trial chart, trial table, search space |
| `/experiments` | All experiments across runs |
| `/evidence` | Paper → Claim → Evidence preview (Phase 5 label) |
| `/reports` | Placeholder (Phase 6 label) |
| `/system`, `/settings` | Runtime facts, preferences |

## Backend integration points

The future backend replaces `src/services/labpilot-api.ts` only:

- `getRuns()` → list of run summaries (ResearchState metadata)
- `getAllRuns()` / `getRun(id)` → full ResearchState
- `getExperiments([researchId])` / `getExperiment(id)` → experiments + provenance
- `getStudy(id)` → OptimizationStudy + trials
- `getRawState(id)` → serialized ResearchState JSON
- `getActivity(limit)` → run event feed

Every function is async and already returns the shapes the UI consumes;
swap the fixture resolution for `fetch` calls and no component changes.

## Fixtures and honesty

- The dropout KEEP run uses **real Phase 2 measured values** (metrics, SHAs,
  image IDs, runtimes) from `docs/phase2-report.md`.
- The HPO study fixture is illustrative (Phase 3 backend in development) and
  the study page says so explicitly.
- Fake-executor runs mirror the documented Phase 1 scenarios.
- Download/Open artifact actions are disabled, not faked.
