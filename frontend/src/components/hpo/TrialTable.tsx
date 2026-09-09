import type { OptimizationStudy, SearchParameter, Trial } from "@/types/domain";
import { cn, formatRuntime } from "@/lib/utils";
import { TrialStatusBadge } from "@/components/ui/badges";
import { DeltaValue } from "@/components/research/MetricSummary";

/** Search-space declaration, typed exactly as the backend validates it. */
export function SearchSpacePanel({ space }: { space: SearchParameter[] }) {
  return (
    <dl className="divide-y divide-line">
      {space.map((p) => (
        <div key={p.name} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-2 first:pt-0 last:pb-0">
          <dt className="font-mono text-xs font-medium text-ink">{p.name}</dt>
          <dd className="flex items-center gap-2 font-mono text-xs text-ink-2">
            {p.type === "float" && (
              <span>
                {p.low} → {p.high}
                {p.log && (
                  <span className="ml-1.5 rounded-[3px] border border-line-strong px-1 text-[10px] font-medium text-muted">
                    log
                  </span>
                )}
                {p.step !== null && (
                  <span className="ml-1.5 rounded-[3px] border border-line-strong px-1 text-[10px] font-medium text-muted">
                    step {p.step}
                  </span>
                )}
              </span>
            )}
            {p.type === "int" && (
              <span>
                {p.low} → {p.high}
                {p.step !== 1 && <span className="text-muted"> (step {p.step})</span>}
              </span>
            )}
            {p.type === "categorical" && (
              <span>{p.choices.join(" / ")}</span>
            )}
            <span className="rounded-[3px] border border-line-strong px-1 text-[10px] font-medium uppercase tracking-wide text-faint">
              {p.type}
            </span>
          </dd>
        </div>
      ))}
    </dl>
  );
}

function th(children: string, className?: string) {
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

export function TrialTable({
  study,
  trials,
  baselineValue,
}: {
  study: OptimizationStudy;
  trials: Trial[];
  baselineValue: number;
}) {
  const params = study.search_space.map((p) => p.name);
  return (
    <div className="overflow-x-auto rounded-[6px] border border-line bg-surface">
      <table className="w-full min-w-[720px] border-collapse">
        <thead>
          <tr>
            {th("Trial")}
            {th("Status")}
            {th("Metric")}
            {th("Δ vs baseline")}
            {th("Runtime", "text-right")}
            {params.map((p) => th(p, "text-right"))}
          </tr>
        </thead>
        <tbody>
          {trials.map((t) => {
            const delta =
              t.primary_metric_value === null ? null : t.primary_metric_value - baselineValue;
            return (
              <tr key={t.id} className="hover:bg-surface-2">
                <td className="border-b border-line/70 px-3 py-2 font-mono text-xs font-medium text-ink">
                  {t.optuna_trial_number}
                  {study.best_trial_id === t.id && (
                    <span className="ml-1.5 rounded-[3px] bg-accent-soft px-1 text-[10px] font-semibold text-accent-ink">
                      BEST
                    </span>
                  )}
                </td>
                <td className="border-b border-line/70 px-3 py-2">
                  <TrialStatusBadge status={t.status} />
                </td>
                <td className="border-b border-line/70 px-3 py-2 font-mono text-xs">
                  {t.primary_metric_value === null ? "—" : t.primary_metric_value.toFixed(4)}
                </td>
                <td className="border-b border-line/70 px-3 py-2">
                  <DeltaValue value={delta} />
                </td>
                <td className="border-b border-line/70 px-3 py-2 text-right font-mono text-xs text-ink-2">
                  {formatRuntime(t.runtime_seconds)}
                </td>
                {params.map((p) => (
                  <td
                    key={p}
                    className="border-b border-line/70 px-3 py-2 text-right font-mono text-xs text-ink-2"
                  >
                    {t.parameters[p] !== undefined ? String(t.parameters[p]) : "—"}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
