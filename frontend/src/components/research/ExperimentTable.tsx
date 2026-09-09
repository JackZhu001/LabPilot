import { useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { Experiment } from "@/types/domain";
import { cn, formatRuntime, shortId } from "@/lib/utils";
import { CopyButton, EmptyState } from "@/components/ui/primitives";
import { DecisionBadge, DecisionPendingBadge, ExperimentStatusBadge, PurposeBadge } from "@/components/ui/badges";
import { DeltaValue } from "@/components/research/MetricSummary";

type Filter = "all" | "SUCCEEDED" | "FAILED" | "BASELINE" | "CANDIDATE";

const FILTERS: { id: Filter; label: string; test: (e: Experiment) => boolean }[] = [
  { id: "all", label: "All", test: () => true },
  { id: "SUCCEEDED", label: "Succeeded", test: (e) => e.status === "SUCCEEDED" },
  { id: "FAILED", label: "Failed", test: (e) => e.status === "FAILED" },
  { id: "BASELINE", label: "Baseline", test: (e) => e.purpose === "BASELINE" },
  { id: "CANDIDATE", label: "Candidate", test: (e) => e.purpose === "CANDIDATE" },
];

function th(children: ReactNode, className?: string) {
  return (
    <th
      scope="col"
      className={cn(
        "sticky top-0 z-10 border-b border-line bg-surface-2 px-3 py-2 text-left text-[11px] font-semibold tracking-wide text-muted",
        className,
      )}
    >
      {children}
    </th>
  );
}

/**
 * Experiment table. Rows navigate to experiment detail; the sha column is
 * hidden on narrow screens in favor of horizontal scroll.
 */
export function ExperimentTable({
  experiments,
  to,
  showResearch = false,
  researchGoals,
}: {
  experiments: Experiment[];
  to: (experiment: Experiment) => string;
  showResearch?: boolean;
  researchGoals?: Record<string, string>;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const navigate = useNavigate();
  const rows = useMemo(
    () => experiments.filter(FILTERS.find((f) => f.id === filter)!.test),
    [experiments, filter],
  );

  return (
    <div className="space-y-3">
      <div role="group" aria-label="Filter experiments" className="flex flex-wrap gap-1.5">
        {FILTERS.map((f) => {
          const count = f.id === "all" ? experiments.length : experiments.filter(f.test).length;
          const active = filter === f.id;
          return (
            <button
              key={f.id}
              type="button"
              aria-pressed={active}
              onClick={() => setFilter(f.id)}
              className={cn(
                "rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors",
                active
                  ? "border-accent/40 bg-accent-soft text-accent-ink"
                  : "border-line-strong bg-surface text-muted hover:bg-surface-2 hover:text-ink",
              )}
            >
              {f.label}
              <span className="ml-1 font-mono text-[11px] text-faint">{count}</span>
            </button>
          );
        })}
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No experiments match"
          description={
            experiments.length === 0
              ? "This research run has not executed any experiments yet."
              : "No experiments match the selected filter."
          }
        />
      ) : (
        <div className="overflow-x-auto rounded-[6px] border border-line bg-surface">
          <table className="w-full min-w-[760px] border-collapse">
            <thead>
              <tr>
                {th("Experiment")}
                {showResearch && th("Research goal", "min-w-[220px] max-w-[320px] truncate")}
                {th("Type")}
                {th("Status")}
                {th("Metric")}
                {th("Δ vs baseline")}
                {th("Runtime", "text-right")}
                {th("Executor")}
                {th("Commit SHA")}
                {th("Decision")}
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => {
                const sha = e.provenance?.git.base_commit_sha;
                return (
                  <tr
                    key={e.id}
                    tabIndex={0}
                    className="cursor-pointer transition-colors hover:bg-surface-2 focus-visible:bg-surface-2"
                    onClick={() => navigate(to(e))}
                    onKeyDown={(ev) => {
                      if (ev.key === "Enter") navigate(to(e));
                    }}
                  >
                    <td className="border-b border-line/70 px-3 py-2">
                      <Link
                        to={to(e)}
                        className="inline-flex items-center gap-1.5 font-mono text-xs font-medium text-accent-ink hover:underline"
                      >
                        {shortId(e.id, 14)}
                        <CopyButton value={e.id} label="experiment ID" />
                      </Link>
                      <span className="ml-2 text-[11px] text-faint">#{e.sequence}</span>
                    </td>
                    {showResearch && (
                      <td className="max-w-[320px] truncate border-b border-line/70 px-3 py-2 text-[13px] text-ink-2">
                        {researchGoals?.[e.research_id] ?? e.research_id}
                      </td>
                    )}
                    <td className="border-b border-line/70 px-3 py-2">
                      <PurposeBadge purpose={e.purpose} />
                    </td>
                    <td className="border-b border-line/70 px-3 py-2">
                      <ExperimentStatusBadge status={e.status} />
                    </td>
                    <td className="border-b border-line/70 px-3 py-2 font-mono text-xs">
                      {e.metric_value === null ? "—" : e.metric_value.toFixed(4)}
                    </td>
                    <td className="border-b border-line/70 px-3 py-2">
                      <DeltaValue value={e.delta} />
                    </td>
                    <td className="border-b border-line/70 px-3 py-2 text-right font-mono text-xs text-ink-2">
                      {formatRuntime(e.runtime_seconds)}
                    </td>
                    <td className="border-b border-line/70 px-3 py-2">
                      <span className="font-mono text-xs text-ink-2">{e.executor}</span>
                    </td>
                    <td className="border-b border-line/70 px-3 py-2">
                      {sha ? (
                        <span className="inline-flex items-center gap-1 font-mono text-xs text-ink-2">
                          {sha.slice(0, 7)}
                          <CopyButton value={sha} label="commit SHA" />
                        </span>
                      ) : (
                        <span className="font-mono text-xs text-faint">—</span>
                      )}
                    </td>
                    <td className="border-b border-line/70 px-3 py-2">
                      {e.decision ? <DecisionBadge decision={e.decision} /> : <DecisionPendingBadge />}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
