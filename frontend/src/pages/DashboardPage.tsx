import { Link } from "react-router-dom";
import { ArrowRight, FlaskConical } from "lucide-react";
import { useRequest } from "@/hooks/useRequest";
import { getActivity, getFeaturedRun, getRuns } from "@/services/labpilot-api";
import { PageHeader } from "@/components/layout/PageHeader";
import { Panel, PanelSkeleton, TableSkeleton, Skeleton, EmptyState } from "@/components/ui/primitives";
import { DecisionBadge, DecisionPendingBadge, RunStatusBadge } from "@/components/ui/badges";
import { ResearchLoop } from "@/components/research/ResearchLoop";
import { ActivityTimeline } from "@/components/research/ActivityTimeline";
import { DeltaValue } from "@/components/research/MetricSummary";
import { formatMetric, formatTimestamp, shortId } from "@/lib/utils";
import type { RunSummary } from "@/types/domain";

function RecentRunsTable({ runs }: { runs: RunSummary[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse">
        <thead>
          <tr>
            {["Goal", "Status", "Decision", "Baseline", "Best", "Δ", "Experiments", "Updated"].map(
              (h) => (
                <th
                  key={h}
                  scope="col"
                  className="border-b border-line px-2.5 py-2 text-left text-[11px] font-semibold tracking-wide text-muted first:pl-0 last:pr-0"
                >
                  {h}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.research_id} className="group">
              <td className="max-w-[260px] truncate border-b border-line/70 px-2.5 py-2 pl-0">
                <Link
                  to={`/runs/${run.research_id}`}
                  className="text-[13px] font-medium text-accent-ink underline-offset-2 group-hover:underline"
                >
                  {run.goal}
                </Link>
              </td>
              <td className="border-b border-line/70 px-2.5 py-2">
                <RunStatusBadge status={run.status} />
              </td>
              <td className="border-b border-line/70 px-2.5 py-2">
                {run.decision ? <DecisionBadge decision={run.decision} /> : <DecisionPendingBadge />}
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
                  <span className="ml-1 text-danger">({run.failed_experiments} failed)</span>
                )}
              </td>
              <td className="whitespace-nowrap border-b border-line/70 px-2.5 py-2 pr-0 font-mono text-[11px] text-faint">
                {formatTimestamp(run.updated_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function DashboardPage() {
  const featured = useRequest(() => getFeaturedRun(), "featured");
  const runs = useRequest(() => getRuns(), "runs");
  const activity = useRequest(() => getActivity(10), "activity");

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="What the research agent is trying, what it measured, and what it decided."
      />

      {/* A. Current research */}
      <section aria-labelledby="current-research" className="mb-4">
        <h2 id="current-research" className="sr-only">
          Current research
        </h2>
        {featured.loading ? (
          <PanelSkeleton rows={3} />
        ) : featured.error || !featured.data ? (
          <EmptyState
            title="Research unavailable"
            description="The current research run could not be loaded."
          />
        ) : (
          <Panel
            title={
              <span className="flex items-center gap-2">
                <FlaskConical className="size-3.5 text-accent" aria-hidden="true" />
                Current research
              </span>
            }
            actions={
              <Link
                to={`/runs/${featured.data.research_id}`}
                className="inline-flex items-center gap-1 rounded-[4px] px-1.5 py-0.5 text-xs font-medium text-accent-ink transition-colors hover:bg-accent-soft"
              >
                View run
                <ArrowRight className="size-3" aria-hidden="true" />
              </Link>
            }
            bodyClassName="p-4 lg:p-5"
          >
            <div className="flex flex-wrap items-center gap-2">
              <p className="mr-auto max-w-[60ch] text-[15px] font-semibold text-ink">
                {featured.data.goal}
              </p>
              <RunStatusBadge status={featured.data.status} />
              {featured.data.decision ? (
                <DecisionBadge decision={featured.data.decision} />
              ) : (
                <DecisionPendingBadge />
              )}
            </div>
            <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-line pt-4 sm:grid-cols-3 lg:grid-cols-6">
              {[
                { label: "Baseline", value: formatMetric(featured.data.baseline.value) },
                {
                  label: "Best measured",
                  value: formatMetric(
                    featured.data.experiments.reduce<number | null>(
                      (best, e) =>
                        e.metric_value === null
                          ? best
                          : best === null || e.metric_value > best
                            ? e.metric_value
                            : best,
                      null,
                    ),
                  ),
                },
                { label: "Iteration", value: String(featured.data.iteration) },
                { label: "Experiments", value: `${featured.data.budget.experiments} / ${featured.data.budget.max_experiments}` },
                { label: "Executor", value: featured.data.executor },
                {
                  label: "Research ID",
                  value: <span className="font-mono text-xs">{shortId(featured.data.research_id, 12)}</span>,
                },
              ].map((cell) => (
                <div key={cell.label}>
                  <p className="text-[11px] tracking-wide text-muted">{cell.label}</p>
                  <p className="mt-0.5 font-mono text-sm font-medium text-ink">{cell.value}</p>
                </div>
              ))}
            </div>
          </Panel>
        )}
      </section>

      {/* B. Research loop */}
      <section aria-labelledby="research-loop" className="mb-4">
        <Panel
          title="Research loop"
          actions={
            <span className="text-[11px] text-faint">
              Literature and HPO stages marked with their backend phase
            </span>
          }
        >
          <ResearchLoop plannedPhases={[3, 5]} />
          <p className="mt-3 border-t border-line pt-3 text-xs leading-relaxed text-muted">
            Phase 2 executes real isolated experiments: Git worktree, Docker container, validated
            metrics. Literature retrieval (Phase 5) and Optuna search (Phase 3) are in development
            and marked accordingly.
          </p>
        </Panel>
      </section>

      <div className="grid gap-4 xl:grid-cols-[1fr_400px]">
        {/* C. Recent runs */}
        <section aria-labelledby="recent-runs">
          <h2 id="recent-runs" className="mb-2.5 text-[13px] font-semibold tracking-wide text-ink">
            Recent runs
          </h2>
          {runs.loading ? (
            <TableSkeleton rows={4} />
          ) : runs.error || !runs.data ? (
            <EmptyState
              title="Runs unavailable"
              description="Research runs could not be loaded. Retry from the Research Runs page."
            />
          ) : runs.data.length === 0 ? (
            <EmptyState
              title="No research runs yet"
              description="Runs appear here once LabPilot starts a research loop. Start one with the CLI: labpilot run --goal …"
            />
          ) : (
            <Panel bodyClassName="p-4">
              <RecentRunsTable runs={runs.data} />
            </Panel>
          )}
        </section>

        {/* D. Activity timeline */}
        <section aria-labelledby="activity">
          <h2 id="activity" className="mb-2.5 text-[13px] font-semibold tracking-wide text-ink">
            Activity
          </h2>
          <Panel bodyClassName="p-4">
            {activity.loading ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="flex gap-3">
                    <Skeleton className="size-[23px] shrink-0 rounded-full" />
                    <div className="flex-1 space-y-1.5">
                      <Skeleton className="h-3 w-2/3" />
                      <Skeleton className="h-2.5 w-1/2" />
                    </div>
                  </div>
                ))}
              </div>
            ) : activity.error || !activity.data ? (
              <p className="text-[13px] text-muted">Activity feed unavailable.</p>
            ) : (
              <ActivityTimeline events={activity.data} showRunLink />
            )}
          </Panel>
        </section>
      </div>
    </>
  );
}
