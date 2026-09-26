import { useI18n } from "@/i18n";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Download, Files } from "lucide-react";
import { useRequest } from "@/hooks/useRequest";
import { getReports, getBenchmark, benchmarkUrl } from "@/services/labpilot-api";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState, Panel, PanelSkeleton } from "@/components/ui/primitives";
import { RunStatusBadge } from "@/components/ui/badges";
import { formatDelta, formatRuntime } from "@/lib/utils";

const percent = (value: number | null) => value === null ? "n/a" : `${(value * 100).toFixed(1)}%`;

export default function ReportsPage() {
  const { t } = useI18n();
  const reports = useRequest(getReports, "reports");
  const [selected, setSelected] = useState<string[]>([]);
  const comparison = useRequest(() => getBenchmark(selected), `benchmark:${[...selected].sort().join(",")}`);
  return (
    <>
      <PageHeader title={t("Reports & evaluation")} description={t("A reproducible record of what changed, what was measured, and what held up.")} />
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4 rounded-panel border border-line bg-surface-2 px-6 py-5">
        <div className="flex items-center gap-4"><Files size={26} className="text-accent" /><div><p className="text-sm font-medium">{t("Research archive")}</p><p className="mt-1 text-xs text-muted">{t("Reports are regenerated from saved snapshots, without new experiments or LLM calls.")}</p></div></div>
        <span className="font-mono text-3xl">{reports.data?.length ?? "···"}</span>
      </div>
      {reports.loading ? <PanelSkeleton rows={5} /> : reports.error ? <EmptyState title={t("Reports unavailable")} description={reports.error.message} /> : !reports.data?.length ? <EmptyState title={t("No reports yet")} description={t("Saved research runs will appear here automatically.")} /> : (
        <Panel title={t("Run reports")} actions={<button type="button" className="text-xs text-muted hover:text-ink" onClick={() => setSelected([])} disabled={!selected.length}>{t("Clear selection")}</button>}>
          <p className="mb-3 text-xs text-muted">{t("Select runs to narrow the comparison below. With no selection, all saved runs are included.")}</p>
          <div className="overflow-x-auto"><table className="w-full min-w-[660px] text-left text-sm">
            <thead className="text-xs text-muted"><tr>{[t("Select"), t("Research"), t("Strategy"), t("Status"), t("Improvement"), t("Report")].map((x) => <th className="pb-3 font-normal" key={x} scope="col">{x}</th>)}</tr></thead>
            <tbody>{reports.data.map((run) => <tr key={run.research_id} className="border-t border-line">
              <td className="py-4"><input type="checkbox" className="size-4 accent-accent" aria-label={t("Compare {goal} ({id})", {goal: run.goal, id: run.research_id})} checked={selected.includes(run.research_id)} onChange={() => setSelected((ids) => ids.includes(run.research_id) ? ids.filter((id) => id !== run.research_id) : [...ids, run.research_id])} /></td>
              <td className="max-w-[320px] py-4 pr-4"><Link to={`/reports/${run.research_id}`} className="hover:text-accent">{run.goal}</Link><p className="mt-1 font-mono text-[10px] text-faint">{run.research_id.slice(0, 8)} {t("· revision")}{" "}{run.revision}</p></td>
              <td className="pr-4 text-xs text-muted">{t(run.strategy)}</td><td className="pr-4"><RunStatusBadge status={run.status} /></td>
              <td className="pr-4 font-mono text-xs">{formatDelta(run.improvement)}</td>
              <td><Link to={`/reports/${run.research_id}`} aria-label={t("Read report for {goal}", {goal: run.goal})} className="inline-flex p-2 text-accent"><ArrowUpRight size={17} /></Link></td>
            </tr>)}</tbody>
          </table></div>
        </Panel>
      )}
      <section className="mt-10" aria-labelledby="benchmark-title">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-4"><div><h2 id="benchmark-title" className="text-2xl font-medium tracking-tight">{t("Compare the evidence")}</h2><p className="mt-2 text-sm text-muted">{selected.length ? t("{count} selected runs", { count: selected.length }) : t("All saved runs")} {t("· grouped by recorded experimental conditions.")}</p></div>
          {comparison.data && <a className="secondary-button" href={benchmarkUrl(selected, "markdown")}><Download size={15} /> {t("Export comparison")}</a>}
        </div>
        {comparison.loading ? <PanelSkeleton rows={3} /> : comparison.error ? <EmptyState title={t("Comparison unavailable")} description={comparison.error.message} /> : !comparison.data?.groups.length ? <p className="text-sm text-muted">{t("No runs to compare yet.")}</p> : (
          <div className="space-y-4">
            <p className="text-xs leading-relaxed text-muted">{t("Observational results do not establish that a research strategy caused an improvement. Simulations are grouped separately.")}</p>
            {comparison.data.groups.map((group) => <details key={group.id} open className="rounded-panel border border-line bg-surface p-5">
              <summary className="cursor-pointer text-sm font-medium">{group.context.metric_name} <span className="ml-2 text-xs font-normal text-muted">{group.context.executor} · {t(group.context.direction)} {t("· cohort")}{" "}{group.id.slice(0, 6)}</span></summary>
              <p className="my-3 text-xs text-muted">{t("Baseline")}{" "}{group.context.baseline ?? t("pending")} {t("· up to")}{" "}{group.context.max_experiments} {t("experiments ·")}{" "}{group.context.max_hpo_trials} {t("HPO trials · commit")}{" "}{group.context.base_commit?.slice(0, 8) ?? t("not recorded")}</p>
              <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-xs"><thead className="text-muted"><tr>{[t("Strategy"), t("Completed / total"), t("Measured"), t("Mean improvement"), t("Sample std."), t("KEEP rate"), t("Tokens"), t("Execution time")].map((x) => <th key={x} scope="col" className="py-3 pr-4 font-normal">{x}</th>)}</tr></thead>
                <tbody>{group.strategies.map((s) => <tr key={t(s.strategy)} className="border-t border-line font-mono"><td className="py-3 pr-4 text-accent">{t(s.strategy)}</td><td>{s.completed} / {s.runs}</td><td>{s.measured_runs}</td><td>{formatDelta(s.mean_improvement)}</td><td>{s.std_improvement?.toFixed(4) ?? t("n/a")}</td><td>{percent(s.keep_rate)}</td><td>{s.llm_tokens.toLocaleString()}</td><td>{s.runtime_seconds === null ? t("n/a") : formatRuntime(s.runtime_seconds)}</td></tr>)}</tbody>
              </table></div>
              {group.strategies.map((s) => <p key={t(s.strategy)} className="mt-3 text-[11px] leading-relaxed text-muted">{t(s.strategy)}{t(": experiment success")}{" "}{percent(s.experiment_success_rate)} {t("· tested hypothesis acceptance")}{" "}{percent(s.hypothesis_acceptance_rate)} {t("· patch execution success")}{" "}{percent(s.patch_execution_success_rate)}</p>)}
            </details>)}
            <details className="text-xs text-muted"><summary className="cursor-pointer">{t("Methodology & limitations")}</summary><ul className="mt-3 list-disc space-y-2 pl-4">{comparison.data.limitations.map((line) => <li key={line}>{t(line)}</li>)}</ul></details>
          </div>
        )}
      </section>
    </>
  );
}
