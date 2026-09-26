import { useI18n } from "@/i18n";
import { Link } from "react-router-dom";
import { ArrowUpRight, ArrowRight, FlaskConical, FileText } from "lucide-react";
import { useRequest } from "@/hooks/useRequest";
import { getActivity, getFeaturedRun, getRuns } from "@/services/labpilot-api";
import { Panel, PanelSkeleton, EmptyState } from "@/components/ui/primitives";
import { DecisionBadge, RunStatusBadge } from "@/components/ui/badges";
import { ResearchLoop } from "@/components/research/ResearchLoop";
import { ResearchCore } from "@/components/research/ResearchCore";
import { ActivityTimeline } from "@/components/research/ActivityTimeline";
import { formatMetric, formatDelta, formatTimestamp } from "@/lib/utils";

export default function DashboardPage() {
  const { t, locale } = useI18n();
  const featured = useRequest(() => getFeaturedRun(), "featured");
  const runs = useRequest(() => getRuns(), "runs");
  const activity = useRequest(() => getActivity(5), "activity");
  const latest = featured.data;
  const summary = runs.data?.find((run) => run.research_id === latest?.research_id);
  const count = (value: number | undefined) => value === undefined ? "···" : String(value).padStart(2, "0");

  return (
    <>
      <section className="workspace-hero" aria-label={t("Research workspace")}>
        <div>
          <p className="mb-5 font-mono text-[11px] uppercase tracking-[.2em] text-muted">{t("Autonomous research workspace")}</p>
          <h1 className="hero-title">{t("Ideas into")}<br /><span>{t("evidence.")}</span></h1>
          <p className="hero-copy">{t("Follow the questions, inspect the experiments, and understand what your research agent learned.")}</p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Link className="primary-button" to="/runs">{t("Explore research")}<ArrowUpRight size={16} /></Link>
            <Link className="secondary-button" to="/reports">{t("View reports")}<FileText size={15} /></Link>
          </div>
        </div>
        <ResearchCore />
      </section>

      <section aria-label={t("Workspace totals")} className="metric-ribbon">
        <div><small>{t("Research runs")}</small><strong>{count(runs.data?.length)}</strong></div>
        <div><small>{t("Experiments recorded")}</small><strong>{count(runs.data?.reduce((total, run) => total + run.experiment_count, 0))}</strong></div>
        <div><small>{t("KEEP decisions")}</small><strong className="text-accent">{count(runs.data?.filter((run) => run.decision === "KEEP").length)}</strong></div>
        <div><small>{t("Docker research runs")}</small><strong>{count(runs.data?.filter((run) => run.executor === "docker").length)}</strong></div>
      </section>

      <section aria-label={t("Current research")} className="mb-8">
        {featured.loading ? <PanelSkeleton rows={4} /> : !latest ? (
          <EmptyState title={t("No current research")} description={featured.error?.message ?? t("Create a research run to begin.")} />
        ) : (
          <div className="current-run">
            <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
              <p className="flex items-center gap-2 text-xs text-muted"><FlaskConical size={15} /> {t("Latest research")}</p>
              <div className="flex gap-2"><RunStatusBadge status={latest.status} />{latest.decision && <DecisionBadge decision={latest.decision} />}</div>
            </div>
            <div className="grid gap-6 xl:grid-cols-[1.3fr_1fr]">
              <div>
                <h2>{latest.goal}</h2>
                <p className="mt-3 text-xs text-muted">{latest.executor === "fake" ? t("Simulated execution") : t("Docker execution")} {t("· Updated")}{" "}{formatTimestamp(latest.updated_at, locale)}</p>
                <div className="mt-5 flex flex-wrap gap-5 text-[13px]">
                  <Link className="inline-flex items-center gap-2 text-accent-ink hover:underline" to={`/runs/${latest.research_id}`}>{t("Inspect run")}<ArrowRight size={14} /></Link>
                  <Link className="inline-flex items-center gap-2 text-muted hover:text-ink" to={`/reports/${latest.research_id}`}>{t("Read report")}<ArrowUpRight size={14} /></Link>
                </div>
              </div>
              <dl className="grid grid-cols-3 gap-4 self-center xl:border-l xl:border-line xl:pl-8">
                <div><dt className="text-xs text-muted">{t("Baseline")}</dt><dd className="mt-2 font-mono text-xl">{formatMetric(summary?.baseline_metric)}</dd></div>
                <div><dt className="text-xs text-muted">{t("Best candidate")}</dt><dd className="mt-2 font-mono text-xl">{formatMetric(summary?.best_metric)}</dd></div>
                <div><dt className="text-xs text-muted">{t("Improvement")}</dt><dd className={`mt-2 font-mono text-xl ${(summary?.delta ?? 0) < 0 ? "text-danger" : "text-accent"}`}>{formatDelta(summary?.delta)}</dd></div>
              </dl>
            </div>
            <div className="mt-7 border-t border-line pt-5"><ResearchLoop nextStep={latest.next_step} /></div>
          </div>
        )}
      </section>

      <div className="grid gap-7 xl:grid-cols-[1.4fr_1fr]">
        <section aria-labelledby="recent-runs">
          <div className="mb-4 flex items-center justify-between"><h2 id="recent-runs" className="text-lg font-medium tracking-tight">{t("Research journal")}</h2><Link to="/runs" className="text-xs text-muted hover:text-accent">{t("All runs")}<span aria-hidden="true">↗</span></Link></div>
          {runs.loading ? <PanelSkeleton rows={4} /> : runs.error || !runs.data ? <EmptyState title={t("Runs unavailable")} description={runs.error?.message ?? t("Could not load research runs.")} /> : runs.data.length === 0 ? <EmptyState title={t("Your journal is empty")} description={t("Research runs appear here once a loop has started.")} /> : (
            <div>{runs.data.slice(0, 5).map((run, index) => (
              <Link key={run.research_id} to={`/runs/${run.research_id}`} className="run-row">
                <span className="font-mono text-xs text-faint">{String(index + 1).padStart(2, "0")}</span>
                <div className="min-w-0 flex-1"><p className="truncate text-sm text-ink">{run.goal}</p><p className="mt-1 text-[11px] text-muted">{run.executor} · {run.experiment_count} {t("experiments")}</p></div>
                {run.decision ? <DecisionBadge decision={run.decision} /> : <RunStatusBadge status={run.status} />}
                <ArrowUpRight className="shrink-0 text-faint" size={15} />
              </Link>
            ))}</div>
          )}
        </section>
        <section aria-labelledby="activity">
          <h2 id="activity" className="mb-4 text-lg font-medium tracking-tight">{t("Latest activity")}</h2>
          <Panel>{activity.loading ? <p className="text-sm text-muted">{t("Loading activity…")}</p> : activity.error ? <p className="text-sm text-muted">{t("Activity could not be loaded.")}</p> : <ActivityTimeline events={activity.data ?? []} showRunLink />}</Panel>
        </section>
      </div>
    </>
  );
}
