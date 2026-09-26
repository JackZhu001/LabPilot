import { useI18n } from "@/i18n";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ArrowUpRight, Download } from "lucide-react";
import { useRequest } from "@/hooks/useRequest";
import { getReport, reportUrl } from "@/services/labpilot-api";
import { EmptyState, PanelSkeleton, CopyButton } from "@/components/ui/primitives";
import { RunStatusBadge, DecisionBadge } from "@/components/ui/badges";
import { formatMetric, formatDelta, formatRuntime, formatTimestamp } from "@/lib/utils";

export default function ReportDetailPage() {
  const { t, locale } = useI18n();
  const { researchId = "" } = useParams();
  const report = useRequest(() => getReport(researchId), researchId);
  if (report.loading) return <PanelSkeleton rows={8} />;
  if (report.error || !report.data) return <EmptyState title={t("Report unavailable")} description={report.error?.message ?? t("No report found.")} />;
  const document = report.data;
  const run = document.run;
  const s = document.summary;
  return <>
    <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
      <Link to="/reports" className="flex items-center gap-2 text-sm text-muted"><ArrowLeft size={15} /> {t("Reports")}</Link>
      <div className="flex flex-wrap gap-2"><a className="primary-button" href={reportUrl(researchId, "markdown")}><Download size={15} /> Markdown</a><a className="secondary-button" href={reportUrl(researchId, "json")}>{t("JSON + snapshot")}</a></div>
    </div>
    <article className="report-paper">
      <div className="mb-5 flex flex-wrap items-center gap-2"><span className="mr-auto font-mono text-xs text-muted">{t("RESEARCH REPORT /")}{" "}{researchId.slice(0, 8)}</span><RunStatusBadge status={s.status} />{s.decision && <DecisionBadge decision={s.decision} />}</div>
      <h1 className="max-w-[800px] text-3xl font-medium leading-tight tracking-tight sm:text-4xl">{s.goal}</h1>
      <p className="mt-5 text-sm text-muted">{t(s.strategy)} {t("strategy ·")}{" "}{s.executor} {t("executor · revision")}{" "}{s.revision} · {formatTimestamp(s.updated_at, locale)}</p>
      <div className="metric-ribbon mt-8">
        <div><small>{t("Baseline")}</small><strong>{formatMetric(s.baseline)}</strong></div>
        <div><small>{t("Best candidate")}</small><strong>{formatMetric(s.best)}</strong></div>
        <div><small>{t("Improvement")}</small><strong className={s.improvement !== null && s.improvement < 0 ? "text-danger" : "text-accent"}>{formatDelta(s.improvement)}</strong></div>
        <div><small>{t("Experiments")}</small><strong>{s.experiments}</strong></div>
      </div>
      <p className="text-sm leading-relaxed text-ink-2">{run.termination_reason ?? t("This research is still in progress. The report reflects its latest saved checkpoint.")}</p>
      <p className="mt-2 text-xs text-muted">{t("Objective:")}{" "}{s.metric_name} ({t(s.direction)}{t("). Positive improvement means better.")}{" "}{s.executor === "fake" && t("These results are simulated.")}</p>
      <section className="mt-9"><h2 className="mb-4 text-xl font-medium">{t("Hypotheses & outcomes")}</h2>{!run.hypotheses.length ? <p className="text-sm text-muted">{t("No hypotheses recorded yet.")}</p> : run.hypotheses.map((h) => <div key={h.id} className="mb-4 border-l-2 border-accent/40 pl-5"><p className="text-sm leading-relaxed">{h.statement}</p><p className="mt-2 text-xs text-muted">{t(h.grounding_status ?? "REPOSITORY_ONLY")} · {t(h.status)} · {h.evidence_ids?.length ?? 0} {t("evidence links")}</p></div>)}</section>
      <section className="mt-9"><h2 className="mb-4 text-xl font-medium">{t("Recorded resources")}</h2><dl className="grid grid-cols-2 gap-5 md:grid-cols-4">{[
        [t("Execution time"), formatRuntime(s.runtime_seconds)], [t("LLM calls"), s.llm_calls], [t("Tokens"), s.llm_tokens.toLocaleString()], [t("Papers / claims"), `${s.papers} / ${s.claims}`],
        [t("Successful experiments"), `${s.successful_experiments} / ${s.finished_experiments}`], [t("Accepted hypotheses"), `${s.accepted_hypotheses} / ${s.tested_hypotheses}`], [t("Successful patches"), `${s.successful_patches} / ${s.attempted_patches}`], [t("Dollar cost"), t("Not recorded")],
      ].map(([label, value]) => <div key={label}><dt className="text-xs text-muted">{label}</dt><dd className="mt-2 font-mono text-sm">{value}</dd></div>)}</dl></section>
      <section className="mt-9 border-t border-line pt-6"><h2 className="text-xl font-medium">{t("Reproducibility record")}</h2><p className="mt-3 text-sm leading-relaxed text-muted">{t("The export contains evidence sources, experiment configurations, seeds, HPO trials, patches, decisions, and execution provenance. Retain the original dataset, images and artifact files alongside it.")}</p><div className="mt-4 flex items-center gap-2"><code className="min-w-0 break-all text-[11px] text-muted">SHA-256 {s.snapshot_sha256}</code><CopyButton value={s.snapshot_sha256} label={t("snapshot fingerprint")} /></div>
        <Link to={`/runs/${researchId}`} className="mt-5 inline-flex items-center gap-2 text-sm text-accent">{t("Inspect source run")}<ArrowUpRight size={15} /></Link></section>
      <details className="mt-8 border-t border-line pt-5"><summary className="cursor-pointer text-sm text-muted">{t("Read complete Markdown report")}</summary><pre className="report-source mt-4">{document.markdown}</pre></details>
    </article>
  </>;
}
