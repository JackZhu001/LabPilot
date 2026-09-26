import { useI18n } from "@/i18n";
import { Info } from "lucide-react";
import type { Baseline } from "@/types/domain";
import { cn, deltaAsPercentagePoints, formatDelta, formatMetric } from "@/lib/utils";

/**
 * Delta with a percentage-point tooltip. Deltas are absolute metric units
 * (the decision engine's contract), so both readings are shown.
 */
export function DeltaValue({
  value,
  className,
  digits = 4,
}: {
  value: number | null | undefined;
  className?: string;
  digits?: number;
}) {
  if (value === null || value === undefined) {
    return <span className={cn("font-mono text-xs text-faint", className)}>—</span>;
  }
  const tone =
    value > 0 ? "text-success" : value < 0 ? "text-danger" : "text-muted";
  return (
    <span
      className={cn("inline-flex items-center gap-1", className)}
      title={`${deltaAsPercentagePoints(value)} (absolute metric units: ${formatDelta(value, digits)})`}
    >
      <span className={cn("font-mono text-xs font-medium", tone)}>
        {formatDelta(value, digits)}
      </span>
      <Info className="size-3 text-faint" aria-hidden="true" />
    </span>
  );
}

/** Compact metric strip: baseline / best / delta / threshold / decision. No KPI-card theater. */
export function MetricSummary({
  baseline,
  best,
  decision,
  className,
}: {
  baseline: Baseline;
  best: number | null;
  decision: string;
  className?: string;
}) {
  const { t } = useI18n();
  const delta = best === null ? null : (best - baseline.value) * (baseline.direction === "MAXIMIZE" ? 1 : -1);
  const cells: { label: string; value: string; accent?: boolean }[] = [
    { label: `Baseline ${baseline.metric_name}`, value: formatMetric(baseline.value) },
    { label: t("Best measured"), value: formatMetric(best) },
    {
      label: t("Improvement (absolute)"),
      value: formatDelta(delta),
      accent: delta !== null && delta >= baseline.min_delta,
    },
    {
      label: t("Decision threshold"),
      value: `≥ ${baseline.min_delta}`,
    },
    { label: t("Decision"), value: decision, accent: decision === "KEEP" },
  ];

  return (
    <div className={cn("grid grid-cols-2 gap-px overflow-hidden rounded-[6px] border border-line bg-line sm:grid-cols-3 lg:grid-cols-5", className)}>
      {cells.map((cell) => (
        <div key={cell.label} className="bg-surface px-3.5 py-3">
          <p className="text-[11px] tracking-wide text-muted">{cell.label}</p>
          <p
            className={cn(
              "mt-1 font-mono text-[15px] font-medium text-ink",
              cell.accent && "text-success",
            )}
          >
            {cell.value}
          </p>
        </div>
      ))}
    </div>
  );
}
