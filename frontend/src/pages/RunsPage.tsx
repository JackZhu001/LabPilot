import { useI18n } from "@/i18n";
import { Link } from "react-router-dom";
import { useRequest } from "@/hooks/useRequest";
import { getRuns } from "@/services/labpilot-api";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState, Panel, TableSkeleton } from "@/components/ui/primitives";
import { DecisionBadge, DecisionPendingBadge, RunStatusBadge } from "@/components/ui/badges";
import { DeltaValue } from "@/components/research/MetricSummary";
import { formatMetric, formatTimestamp, shortId } from "@/lib/utils";

export default function RunsPage() {
  const { t, locale } = useI18n();
  const { data: runs, loading, error } = useRequest(() => getRuns(), "runs");

  return (
    <>
      <PageHeader
        title={t("Research Runs")}
        description={t("Every autonomous research loop: its goal, measured outcome, and final decision.")}
      />
      {loading ? (
        <TableSkeleton rows={5} />
      ) : error || !runs ? (
        <EmptyState
          title={t("Runs unavailable")}
          description={error?.message ?? t("Research runs could not be loaded.")}
        />
      ) : runs.length === 0 ? (
        <EmptyState
          title={t("No research runs yet")}
          description={t("Start a loop from the CLI (labpilot run --goal …) or wait for a scheduled run. Completed and in-progress runs appear here with their decision outcome.")}
        />
      ) : (
        <Panel bodyClassName="p-4">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] border-collapse">
              <thead>
                <tr>
                  {[
                    t("Research goal"),
                    t("Research ID"),
                    t("Status"),
                    t("Decision"),
                    t("Iteration"),
                    t("Baseline"),
                    t("Best"),
                    "Δ",
                    t("Experiments"),
                    t("Executor"),
                    t("Updated"),
                  ].map((h) => (
                    <th
                      key={h}
                      scope="col"
                      className="sticky top-0 border-b border-line bg-surface-2 px-2.5 py-2 text-left text-[11px] font-semibold tracking-wide text-muted"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.research_id} className="group hover:bg-surface-2">
                    <td className="max-w-[300px] truncate border-b border-line/70 px-2.5 py-2">
                      <Link
                        to={`/runs/${run.research_id}`}
                        className="text-[13px] font-medium text-accent-ink underline-offset-2 group-hover:underline"
                      >
                        {run.goal}
                      </Link>
                    </td>
                    <td className="border-b border-line/70 px-2.5 py-2 font-mono text-[11px] text-muted">
                      {shortId(run.research_id, 10)}
                    </td>
                    <td className="border-b border-line/70 px-2.5 py-2">
                      <RunStatusBadge status={run.status} />
                    </td>
                    <td className="border-b border-line/70 px-2.5 py-2">
                      {run.decision ? <DecisionBadge decision={run.decision} /> : <DecisionPendingBadge />}
                    </td>
                    <td className="border-b border-line/70 px-2.5 py-2 font-mono text-xs">
                      {run.iteration}
                    </td>
                    <td className="border-b border-line/70 px-2.5 py-2 font-mono text-xs text-ink-2">
                      {formatMetric(run.baseline_metric)}
                    </td>
                    <td className="border-b border-line/70 px-2.5 py-2 font-mono text-xs font-medium text-ink">
                      {formatMetric(run.best_metric)}
                    </td>
                    <td className="border-b border-line/70 px-2.5 py-2">
                      <DeltaValue value={run.delta} />
                    </td>
                    <td className="border-b border-line/70 px-2.5 py-2 font-mono text-xs text-ink-2">
                      {run.experiment_count}
                      {run.failed_experiments > 0 && (
                        <span className="ml-1 text-danger">({run.failed_experiments} {t("failed)")}</span>
                      )}
                    </td>
                    <td className="border-b border-line/70 px-2.5 py-2 font-mono text-xs text-ink-2">
                      {run.executor}
                    </td>
                    <td className="whitespace-nowrap border-b border-line/70 px-2.5 py-2 font-mono text-[11px] text-faint">
                      {formatTimestamp(run.updated_at, locale)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </>
  );
}
