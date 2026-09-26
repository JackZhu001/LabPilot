import { useI18n } from "@/i18n";
import {
  CartesianGrid,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  XAxis,
  YAxis,
} from "recharts";
import type { OptimizationStudy, Trial } from "@/types/domain";

/** Trial performance: primary metric per Optuna trial number, baseline as reference. */
export function TrialChart({
  study,
  trials,
  baselineValue,
}: {
  study: OptimizationStudy;
  trials: Trial[];
  baselineValue: number;
}) {
  const { t } = useI18n();
  const best = trials.find((t) => t.id === study.best_trial_id);

  const data = trials.map((t) => ({
    n: t.optuna_trial_number,
    metric: t.primary_metric_value,
    status: t.status,
    isBest: best?.id === t.id,
  }));

  const succeeded = data.filter((d) => d.metric !== null);

  const yValues = succeeded.map((d) => d.metric as number);
  const yMin = Math.min(baselineValue, ...yValues);
  const yMax = Math.max(baselineValue, ...yValues);
  const padding = Math.max((yMax - yMin) * 0.15, 0.0005);

  return (
    <div className="h-[240px] w-full">
      <ResponsiveContainer width="100%" height="100%">
      <ComposedChart
        data={succeeded}
        margin={{ top: 8, right: 12, bottom: 0, left: 4 }}
        accessibilityLayer
      >
        <CartesianGrid stroke="var(--color-line)" strokeDasharray="2 4" vertical={false} />
        <XAxis
          dataKey="n"
          type="number"
          domain={[0, study.max_trials - 1]}
          ticks={succeeded.map((d) => d.n).filter((n): n is number => n !== null)}
          tick={{ fontSize: 11, fontFamily: "var(--font-mono)", fill: "var(--color-muted)" }}
          stroke="var(--color-line-strong)"
          tickLine={false}
          label={{
            value: t("Trial number"),
            position: "insideBottomRight",
            offset: -2,
            fontSize: 11,
            fill: "var(--color-muted)",
          }}
        />
        <YAxis
          domain={[yMin - padding, yMax + padding]}
          tick={{ fontSize: 11, fontFamily: "var(--font-mono)", fill: "var(--color-muted)" }}
          stroke="var(--color-line-strong)"
          tickLine={false}
          width={64}
          tickFormatter={(v: number) => v.toFixed(3)}
        />
        <ReferenceLine
          y={baselineValue}
          stroke="var(--color-muted)"
          strokeDasharray="4 3"
          label={{
            value: `baseline ${baselineValue.toFixed(4)}`,
            position: "insideTopLeft",
            fontSize: 11,
            fill: "var(--color-muted)",
          }}
        />
        <Scatter
          data={succeeded.filter((d) => !d.isBest)}
          dataKey="metric"
          fill="var(--color-accent)"
          fillOpacity={0.75}
        />
        <Scatter
          data={succeeded.filter((d) => d.isBest)}
          dataKey="metric"
          fill="var(--color-accent)"
          stroke="var(--color-accent-strong)"
          strokeWidth={2}
          r={7}
          shape="circle"
        />
      </ComposedChart>
      </ResponsiveContainer>
      <p className="mt-1 text-[11px] leading-relaxed text-faint">
        {t("Blue point = completed trial. Large ring = best trial (")}{" "}{best ? `trial ${best.optuna_trial_number}, ${best.primary_metric_value?.toFixed(4)}` : "—"}
        {t("). Dashed line = measured baseline. Failed and pruned trials plot no metric.")}</p>
    </div>
  );
}
