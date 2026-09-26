import { Navigate } from "react-router-dom";
import type { RouteObject } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import DashboardPage from "@/pages/DashboardPage";
import RunsPage from "@/pages/RunsPage";
import RunLayout from "@/pages/run/RunLayout";
import RunOverviewPage from "@/pages/run/RunOverviewPage";
import RunExperimentsPage from "@/pages/run/RunExperimentsPage";
import ExperimentDetailPage from "@/pages/run/ExperimentDetailPage";
import RunHpoPage from "@/pages/run/RunHpoPage";
import RunEvidencePage from "@/pages/run/RunEvidencePage";
import RunStatePage from "@/pages/run/RunStatePage";
import AllExperimentsPage from "@/pages/AllExperimentsPage";
import EvidencePreviewPage from "@/pages/EvidencePreviewPage";
import ReportDetailPage from "@/pages/ReportDetailPage";
import ReportsPage from "@/pages/ReportsPage";
import SystemPage from "@/pages/SystemPage";
import SettingsPage from "@/pages/SettingsPage";
import NotFoundPage from "@/pages/NotFoundPage";
import NewResearchPage from "@/pages/NewResearchPage";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "dashboard", element: <DashboardPage /> },
      { path: "new", element: <NewResearchPage /> },
      { path: "runs", element: <RunsPage /> },
      {
        path: "runs/:researchId",
        element: <RunLayout />,
        children: [
          { index: true, element: <RunOverviewPage /> },
          { path: "experiments", element: <RunExperimentsPage /> },
          { path: "experiments/:experimentId", element: <ExperimentDetailPage /> },
          { path: "hpo", element: <RunHpoPage /> },
          { path: "hpo/:studyId", lazy: async () => ({ Component: (await import("@/pages/run/StudyPage")).default }) },
          { path: "evidence", element: <RunEvidencePage /> },
          { path: "state", element: <RunStatePage /> },
        ],
      },
      { path: "experiments", element: <AllExperimentsPage /> },
      { path: "evidence", element: <EvidencePreviewPage /> },
      { path: "reports", element: <ReportsPage /> },
      { path: "reports/:researchId", element: <ReportDetailPage /> },
      { path: "system", element: <SystemPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];
