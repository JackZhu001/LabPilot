# LabPilot Frontend

Research control plane UI for LabPilot. It reads persisted research runs from
the Python API by default. Typed fixtures remain available for UI development.

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

Start the API from the repository root, then the frontend in another terminal:

```bash
uv run labpilot serve-api --db .labpilot/labpilot.sqlite3
cd frontend && npm run dev
```

Vite forwards `/api` to `http://127.0.0.1:8000`. Set `VITE_LABPILOT_API_URL`
for another API address, or `VITE_LABPILOT_USE_MOCKS=true` to show fixtures
without an API. The API is read-only; create and resume runs with the CLI.

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
├── mocks/            optional fixture data for UI development
├── pages/            route pages (dashboard, runs, run tabs, experiment, HPO, …)
├── services/         labpilot-api.ts — the single data-access boundary
├── types/            domain.ts — typed after the Python models
├── router.tsx        route table (shared by main and the SSR smoke check)
└── main.tsx
```

**Data boundary:** components import only `services/labpilot-api.ts`. That
service calls the Python API by default and uses `src/mocks/` only when the
mock environment flag is set.

## Routes

| Route | Content |
| --- | --- |
| `/dashboard` | Current research, loop, recent runs, activity timeline |
| `/runs` | Research run list |
| `/runs/:researchId` | Run detail (tabs: Overview, Experiments, HPO, Evidence, State) |
| `/runs/:researchId/experiments/:experimentId` | Experiment detail: config, Git/Docker provenance, diff, downloadable artifacts |
| `/runs/:researchId/hpo/:studyId` | Optuna study: best trial, trial chart, trial table, search space |
| `/experiments` | All experiments across runs |
| `/evidence` | Paper → Claim → Evidence across persisted runs |
| `/reports` | Saved research reports and cohort benchmark comparison |
| `/reports/:researchId` | Report preview with Markdown / JSON export |
| `/system`, `/settings` | Runtime facts, preferences |

## Backend data routes

The read-only API serves:

- `getRuns()` → list of run summaries (ResearchState metadata)
- `getAllRuns()` / `getRun(id)` → full ResearchState
- `getExperiments([researchId])` / `getExperiment(id)` → experiments + provenance
- `getStudy(id)` → OptimizationStudy + trials
- `getRawState(id)` → serialized ResearchState JSON
- `getActivity(limit)` → run event feed
- `artifactUrl(experimentId, name)` → an allowlisted artifact download

The API adapts the existing SQLite `ResearchState` to these UI shapes.

## Optional fixtures

- The dropout KEEP run uses **real Phase 2 measured values** (metrics, SHAs,
  image IDs, runtimes) from `docs/phase2-report.md`.
- The HPO study fixture is illustrative; live HPO data comes from SQLite.
- Fake-executor runs mirror the documented Phase 1 scenarios.
- Artifact downloads are live with the API; fixture mode disables them.


The graphite/lime interface includes a CSS 3D research model on the dashboard.
Motion can be paused and respects `prefers-reduced-motion`; the header toggles a
persisted light/dark theme. Reports and benchmark comparison require the live API.
The HPO chart is loaded when its route is opened, keeping it out of the initial bundle.

### Language and motion

The header switches English / 简体中文 and persists the choice in localStorage.
On first use it follows the browser language. UI labels and dates are localized;
research content, code, raw state and report exports retain their original text.
The motion toggle pauses animations globally; the 3D model has its own pause control.
Both respect the OS reduced-motion preference. `npm run smoke` checks translation
fallback/interpolation and renders the route tree, including the lazy HPO route.
