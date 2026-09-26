import { useI18n } from "@/i18n";
import { Link, NavLink, Outlet, useParams } from "react-router-dom";
import { useRequest } from "@/hooks/useRequest";
import { getRun } from "@/services/labpilot-api";
import { cn, formatTimestamp } from "@/lib/utils";
import { CopyButton, EmptyState, MonoValue, PanelSkeleton } from "@/components/ui/primitives";
import { DecisionBadge, DecisionPendingBadge, RunStatusBadge } from "@/components/ui/badges";

const TABS = [
  { to: ".", label: "Overview", end: true },
  { to: "experiments", label: "Experiments", end: false },
  { to: "hpo", label: "HPO", end: false },
  { to: "evidence", label: "Evidence", end: false },
  { to: "state", label: "State", end: false },
];

export default function RunLayout() {
  const { t, locale } = useI18n();
  const { researchId = "" } = useParams();
  const { data: run, loading, error } = useRequest(() => getRun(researchId), researchId);

  if (loading) {
    return (
      <div className="space-y-4">
        <PanelSkeleton rows={6} />
      </div>
    );
  }
  if (error || !run) {
    return (
      <EmptyState
        title={t("Research run not found")}
        description={`No research run exists with ID ${researchId}. It may have been created in a different LabPilot database.`}
      />
    );
  }

  return (
    <>
      <header className="mb-4">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="mr-auto max-w-[70ch] text-xl font-semibold tracking-tight text-ink">
            {run.goal}
          </h1>
          <Link to={`/reports/${researchId}`} className="secondary-button">{t("View report")}</Link>
          <RunStatusBadge status={run.status} />
          {run.decision ? <DecisionBadge decision={run.decision} /> : <DecisionPendingBadge />}
        </div>
        <div className="mt-2.5 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs text-muted">
          <span className="flex items-center gap-1.5">
            <span className="text-faint">{t("Research ID")}</span>
            <MonoValue>{run.research_id.slice(0, 13)}…</MonoValue>
            <CopyButton value={run.research_id} label={t("research ID")} />
          </span>
          <span>
            <span className="text-faint">{t("Executor")}</span>
            <MonoValue>{run.executor}</MonoValue>
          </span>
          <span>
            <span className="text-faint">{t("Iteration")}</span>
            <MonoValue>{run.iteration}</MonoValue>
          </span>
          <span>
            <span className="text-faint">{t("Revision")}</span>
            <MonoValue>{run.revision}</MonoValue>
          </span>
          <span className="hidden sm:inline">
            <span className="text-faint">{t("Created")}</span>
            {formatTimestamp(run.created_at, locale)}
          </span>
          <span>
            <span className="text-faint">{t("Updated")}</span>
            {formatTimestamp(run.updated_at, locale)}
          </span>
        </div>
      </header>

      <nav aria-label={t("Run sections")} className="mb-4 flex gap-1 overflow-x-auto border-b border-line">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.end}
            className={({ isActive }) =>
              cn(
                "-mb-px border-b-2 px-3 py-2 text-[13px] font-medium transition-colors",
                isActive
                  ? "border-accent text-accent-ink"
                  : "border-transparent text-muted hover:border-line-strong hover:text-ink",
              )
            }
          >
            {t(tab.label)}
          </NavLink>
        ))}
      </nav>

      <Outlet context={{ run }} />
    </>
  );
}
