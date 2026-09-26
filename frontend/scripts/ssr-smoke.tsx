/* SSR smoke check: every route renders without crashing. Effects do not run
 * server-side, so pages render their loading state — this catches module
 * resolution and render-path errors only. Run via:
 *   npx vite build --ssr scripts/ssr-smoke.tsx --outDir .smoke && node .smoke/ssr-smoke.js
 */
import assert from "node:assert/strict";
import { LocaleProvider, translate } from "../src/i18n";
import { renderToString } from "react-dom/server";
import { Outlet, createMemoryRouter, RouterProvider } from "react-router-dom";
import { routes } from "../src/router";
import type { ResearchRun } from "../src/types/domain";
import { dropoutKeepRun } from "../src/mocks/run-dropout-keep";
import { hpoPreviewRun } from "../src/mocks/run-hpo";
import RunOverviewPage from "../src/pages/run/RunOverviewPage";
import RunExperimentsPage from "../src/pages/run/RunExperimentsPage";
import RunHpoPage from "../src/pages/run/RunHpoPage";
import RunEvidencePage from "../src/pages/run/RunEvidencePage";
import RunStatePage from "../src/pages/run/RunStatePage";

function RunContext({ run }: { run: ResearchRun }) {
  return <Outlet context={{ run }} />;
}

function runRoutes(run: ResearchRun) {
  return [
    {
      path: "/",
      element: <RunContext run={run} />,
      children: [
        { index: true, element: <RunOverviewPage /> },
        { path: "experiments", element: <RunExperimentsPage /> },
        { path: "hpo", element: <RunHpoPage /> },
        { path: "evidence", element: <RunEvidencePage /> },
        { path: "state", element: <RunStatePage /> },
      ],
    },
  ];
}

const paths = [
  "/dashboard",
  "/runs",
  "/runs/7ba5ca38-1d49-4901-bc98-a108a11942ea",
  "/runs/7ba5ca38-1d49-4901-bc98-a108a11942ea/experiments",
  "/runs/7ba5ca38-1d49-4901-bc98-a108a11942ea/experiments/d2f65154-f321-5e64-b044-c166e87eaf68",
  "/runs/c4e2a90f-1b3d-4a5c-8e6f-2d4b6a8c0e2f/hpo",
  "/runs/c4e2a90f-1b3d-4a5c-8e6f-2d4b6a8c0e2f/hpo/2b8d4f6a-9c1e-4a3b-8d5f-7a9c1e3b5d7f",
  "/runs/7ba5ca38-1d49-4901-bc98-a108a11942ea/evidence",
  "/runs/7ba5ca38-1d49-4901-bc98-a108a11942ea/state",
  "/experiments",
  "/evidence",
  "/reports",
  "/system",
  "/settings",
  "/nonexistent",
];

assert.equal(translate("zh", "Dashboard"), "工作台");
assert.equal(translate("en", "Dashboard"), "Dashboard");
assert.equal(translate("zh", "{count} selected runs", { count: 3 }), "已选择 3 个运行");
assert.equal(translate("zh", "raw metric name"), "raw metric name");
let failures = 0;
for (const path of paths) {
  try {
    const router = createMemoryRouter(routes, { initialEntries: [path] });
    if (!router.state.initialized) await new Promise<void>((resolve) => {
      const unsubscribe = router.subscribe((state) => { if (state.initialized) { unsubscribe(); resolve(); } });
    });
    const html = renderToString(<LocaleProvider initialLocale="zh"><RouterProvider router={router} /></LocaleProvider>);
    const ok = html.length > 200;
    console.log(`${ok ? "ok " : "FAIL"} ${path} (${html.length} bytes)`);
    if (!ok) failures++;
  } catch (err) {
    failures++;
    console.log(`FAIL ${path} — ${err}`);
  }
}
// Data-driven render paths via outlet context injection.
const runPaths = [
  "/ (overview)",
  "/experiments",
  "/hpo",
  "/evidence",
  "/state",
];
for (const run of [dropoutKeepRun, hpoPreviewRun]) {
  for (const path of runPaths) {
    try {
      const router = createMemoryRouter(runRoutes(run), {
        initialEntries: [path === "/ (overview)" ? "/" : path],
      });
      const html = renderToString(<RouterProvider router={router} />);
      const ok = html.length > 500 && !html.includes("not found");
      console.log(`${ok ? "ok " : "FAIL"} run ${run.research_id.slice(0, 8)} ${path} (${html.length} bytes)`);
      if (!ok) failures++;
    } catch (err) {
      failures++;
      console.log(`FAIL run ${run.research_id.slice(0, 8)} ${path} — ${err}`);
    }
  }
}

if (failures > 0) {
  process.exit(1);
}
console.log("SSR smoke: all routes rendered");
