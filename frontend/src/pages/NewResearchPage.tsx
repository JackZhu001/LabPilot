import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, ArrowRight, BookOpen, Check, FileText, LoaderCircle, Upload } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Panel } from "@/components/ui/primitives";
import { useI18n } from "@/i18n";
import { createResearchRun, getResearchPreview, type ResearchPlanPreview } from "@/services/labpilot-api";

type ChangeScope = "" | "CONFIG_ONLY" | "CODE_CHANGE";
type Direction = "MAXIMIZE" | "MINIMIZE";

export default function NewResearchPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [goal, setGoal] = useState("");
  const [baseline, setBaseline] = useState("");
  const [depth, setDepth] = useState(3);
  const [changeType, setChangeType] = useState<ChangeScope>("");
  const [metricName, setMetricName] = useState("validation_accuracy");
  const [direction, setDirection] = useState<Direction>("MAXIMIZE");
  const [customMetric, setCustomMetric] = useState("");
  const [constraints, setConstraints] = useState("");
  const [seed, setSeed] = useState(42);
  const [queryCount, setQueryCount] = useState(2);
  const [paperLimit, setPaperLimit] = useState(6);
  const [evidenceJudge, setEvidenceJudge] = useState<"deepseek" | "jev">("deepseek");
  const [papers, setPapers] = useState<File[]>([]);
  const [preview, setPreview] = useState<ResearchPlanPreview | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function validatePapers() {
    if (papers.length > 5) throw new Error(t("Upload at most five papers."));
    if (papers.reduce((total, file) => total + file.size, 0) > 5 * 1024 * 1024) {
      throw new Error(t("Uploaded papers must total 5 MB or less."));
    }
  }

  async function previewPlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      validatePapers();
      setPreview(await getResearchPreview({
        goal, baseline_path: baseline, papers: papers.map((paper) => paper.name),
        max_iterations: depth, max_literature_queries: queryCount,
        max_retrieved_papers: paperLimit, seed, constraints,
        change_type: changeType || null,
        metric_name: metricName === "custom" ? customMetric : metricName, direction,
        evidence_judge: evidenceJudge,
      }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("Could not prepare research preview."));
    } finally {
      setBusy(false);
    }
  }

  async function startResearch() {
    setBusy(true);
    setError("");
    try {
      validatePapers();
      const uploads = await Promise.all(papers.map(async (paper) => {
        const bytes = new Uint8Array(await paper.arrayBuffer());
        let binary = "";
        for (let offset = 0; offset < bytes.length; offset += 0x8000) {
          binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
        }
        return { name: paper.name, data: btoa(binary) };
      }));
      const run = await createResearchRun({
        goal, baseline_path: baseline, papers: uploads, max_iterations: depth,
        max_literature_queries: queryCount, max_retrieved_papers: paperLimit,
        seed, constraints, change_type: changeType || null,
        metric_name: metricName === "custom" ? customMetric : metricName, direction,
        evidence_judge: evidenceJudge,
      });
      navigate(`/runs/${run.research_id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("Could not start research."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title={t("New research")} description={t("Give LabPilot a research question, optional source papers, and the code baseline to investigate. It will search, form hypotheses, run experiments, and save a report.")} />
      <form onSubmit={previewPlan} onChange={() => setPreview(null)} className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <Panel title={t("Research brief")}>
          <label htmlFor="research-goal" className="mb-2 block text-sm font-medium text-ink">{t("Research topic or question")}</label>
          <textarea id="research-goal" required maxLength={1000} rows={5} value={goal} onChange={(event) => setGoal(event.target.value)} placeholder={t("Example: Can cosine learning-rate decay improve validation accuracy without increasing training time?")} className="w-full resize-y rounded-lg border border-line-strong bg-surface-2 p-3 text-sm text-ink outline-none transition focus:border-accent" />
          <p className="mt-2 text-xs leading-relaxed text-muted"><BookOpen size={14} className="mr-1 inline" />{t("The agent searches arXiv and Semantic Scholar, then uses the sources to ground its experiments.")}</p>
          <div className="mt-6">
            <label htmlFor="baseline-path" className="mb-2 block text-sm font-medium text-ink">{t("Baseline repository")}</label>
            <input id="baseline-path" value={baseline} onChange={(event) => { setBaseline(event.target.value); if (!event.target.value) { setMetricName("validation_accuracy"); setDirection("MAXIMIZE"); } }} placeholder={t("Leave blank to use the included MNIST baseline")} className="w-full rounded-lg border border-line-strong bg-surface-2 px-3 py-2.5 font-mono text-xs text-ink outline-none focus:border-accent" />
            <p className="mt-2 text-xs leading-relaxed text-muted">{t("Use a clean Git repository with a train.py entry point that writes outputs/metrics.json. The included baseline is selected when this is empty.")}</p>
          </div>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="metric-name" className="mb-2 block text-sm font-medium text-ink">{t("Target metric")}</label>
              <select id="metric-name" value={metricName} onChange={(event) => {
                const value = event.target.value;
                setMetricName(value);
                if (value === "validation_accuracy") setDirection("MAXIMIZE");
                if (value === "validation_loss") setDirection("MINIMIZE");
              }} className="w-full rounded-lg border border-line-strong bg-surface-2 px-3 py-2.5 font-mono text-sm text-ink outline-none focus:border-accent">
                <option value="validation_accuracy">validation_accuracy</option>
                <option value="validation_loss">validation_loss</option>
                {baseline && <option value="custom">{t("Custom metric")}</option>}
              </select>
              {metricName === "custom" && <input aria-label={t("Custom metric name")} required maxLength={80} value={customMetric} onChange={(event) => setCustomMetric(event.target.value)} placeholder="e.g. validation_f1" className="mt-2 w-full rounded-lg border border-line-strong bg-surface-2 px-3 py-2.5 font-mono text-sm text-ink outline-none focus:border-accent" />}
            </div>
            <div>
              <label htmlFor="metric-direction" className="mb-2 block text-sm font-medium text-ink">{t("Optimize direction")}</label>
              <select id="metric-direction" value={direction} disabled={!baseline} onChange={(event) => setDirection(event.target.value as Direction)} className="w-full rounded-lg border border-line-strong bg-surface-2 px-3 py-2.5 text-sm text-ink outline-none focus:border-accent disabled:opacity-60">
                <option value="MAXIMIZE">{t("Higher is better")}</option>
                <option value="MINIMIZE">{t("Lower is better")}</option>
              </select>
            </div>
            <div>
              <label htmlFor="research-depth" className="mb-2 block text-sm font-medium text-ink">{t("Research depth")}</label>
              <select id="research-depth" value={depth} onChange={(event) => setDepth(Number(event.target.value))} className="w-full rounded-lg border border-line-strong bg-surface-2 px-3 py-2.5 text-sm text-ink outline-none focus:border-accent">
                <option value={1}>{t("Quick · 1 iteration")}</option><option value={2}>{t("Standard · 2 iterations")}</option><option value={3}>{t("Deep · 3 iterations")}</option>
              </select>
            </div>
            <div>
              <label htmlFor="change-type" className="mb-2 block text-sm font-medium text-ink">{t("Allowed change scope")}</label>
              <select id="change-type" value={changeType} onChange={(event) => setChangeType(event.target.value as ChangeScope)} className="w-full rounded-lg border border-line-strong bg-surface-2 px-3 py-2.5 text-sm text-ink outline-none focus:border-accent">
                <option value="">{t("Let LabPilot choose")}</option><option value="CONFIG_ONLY">{t("Configuration only")}</option><option value="CODE_CHANGE">{t("Source code changes")}</option>
              </select>
            </div>
          </div>
          <details className="mt-6 rounded-lg border border-line bg-surface-2 px-4 py-3">
            <summary className="cursor-pointer text-sm font-medium text-ink">{t("Advanced research controls")}</summary>
            <div className="mt-4 space-y-4">
              <div>
                <label htmlFor="research-constraints" className="mb-2 block text-sm font-medium text-ink">{t("Research constraints and preferences")}</label>
                <textarea id="research-constraints" maxLength={3000} rows={3} value={constraints} onChange={(event) => setConstraints(event.target.value)} placeholder={t("Example: Keep training under 10 minutes; prefer simple changes; compare against the existing augmentation baseline.")} className="w-full resize-y rounded-lg border border-line-strong bg-surface p-3 text-sm text-ink outline-none focus:border-accent" />
                <p className="mt-1 text-xs text-muted">{t("These instructions guide literature search, hypotheses and experiments.")}</p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div><label htmlFor="seed" className="mb-2 block text-sm font-medium text-ink">{t("Random seed")}</label><input id="seed" type="number" min={0} max={4294967295} step={1} value={seed} onChange={(event) => setSeed(Number(event.target.value))} className="w-full rounded-lg border border-line-strong bg-surface px-3 py-2.5 font-mono text-sm text-ink outline-none focus:border-accent" /><p className="mt-1 text-xs text-muted">{t("Recorded with every experiment for reproducibility.")}</p></div>
                <div><label htmlFor="query-count" className="mb-2 block text-sm font-medium text-ink">{t("Literature searches")}</label><select id="query-count" value={queryCount} onChange={(event) => setQueryCount(Number(event.target.value))} className="w-full rounded-lg border border-line-strong bg-surface px-3 py-2.5 text-sm text-ink outline-none focus:border-accent"><option value={1}>1</option><option value={2}>2</option><option value={3}>3</option></select></div>
                <div><label htmlFor="paper-limit" className="mb-2 block text-sm font-medium text-ink">{t("Maximum papers to retrieve")}</label><select id="paper-limit" value={paperLimit} onChange={(event) => setPaperLimit(Number(event.target.value))} className="w-full rounded-lg border border-line-strong bg-surface px-3 py-2.5 text-sm text-ink outline-none focus:border-accent"><option value={3}>3</option><option value={6}>6</option><option value={10}>10</option></select><p className="mt-1 text-xs text-muted">{t("Uploaded papers are additional to this limit.")}</p></div>
                <div><label htmlFor="evidence-judge" className="mb-2 block text-sm font-medium text-ink">{t("Evidence assessment")}</label><select id="evidence-judge" value={evidenceJudge} onChange={(event) => setEvidenceJudge(event.target.value as "deepseek" | "jev")} className="w-full rounded-lg border border-line-strong bg-surface px-3 py-2.5 text-sm text-ink outline-none focus:border-accent"><option value="deepseek">DeepSeek</option><option value="jev">Jev</option></select><p className="mt-1 text-xs text-muted">{t("Jev adds a separate evidence relevance and strength assessment.")}</p></div>
              </div>
            </div>
          </details>
        </Panel>

        <div className="space-y-6">
          <Panel title={t("Add a paper")}>
            <label htmlFor="paper-file" className="flex cursor-pointer flex-col items-center rounded-lg border border-dashed border-line-strong bg-surface-2 px-4 py-7 text-center transition hover:border-accent">
              <Upload size={19} className="mb-3 text-accent" /><span className="text-sm font-medium text-ink">{t("Choose papers")}</span>
              <span className="mt-1 text-xs text-muted">PDF, Markdown, TXT · {t("up to 5 files, 5 MB total")}</span>
              <input id="paper-file" type="file" multiple accept=".pdf,.md,.txt,application/pdf,text/plain,text/markdown" className="sr-only" onChange={(event) => setPapers((current) => [...current, ...Array.from(event.target.files ?? [])].filter((file, index, all) => all.findIndex((item) => item.name === file.name && item.size === file.size) === index))} />
            </label>
            {papers.length > 0 && <ul className="mt-3 space-y-1 text-xs text-muted">{papers.map((paper) => <li key={`${paper.name}-${paper.size}`} className="truncate">{paper.name}</li>)}</ul>}
            {papers.length > 0 && <button type="button" onClick={() => setPapers([])} className="mt-3 text-xs text-muted hover:text-ink">{t("Remove all papers")}</button>}
            <p className="mt-4 text-xs leading-relaxed text-muted"><FileText size={14} className="mr-1 inline" />{t("The uploaded paper is included in source tracking and claim extraction alongside searched literature.")}</p>
          </Panel>
          {error && <p role="alert" className="rounded-lg border border-danger/30 bg-danger-soft p-3 text-sm text-danger">{error}</p>}
          <button type="submit" disabled={busy || !goal.trim()} className="primary-button w-full justify-center disabled:cursor-not-allowed disabled:opacity-50">
            {busy ? <LoaderCircle size={16} className="animate-spin" /> : <ArrowRight size={16} />}
            {busy ? t("Preparing plan…") : t("Preview research plan")}
          </button>
          <Link to="/runs" className="block text-center text-xs text-muted hover:text-ink">{t("Return to research runs")}</Link>
        </div>
      </form>

      {preview && <div className="mt-6"><Panel title={t("Research plan preview")}>
        <p className="text-sm text-muted">{t("This plan checks your baseline and constraints. Literature review and hypotheses are generated when the run starts.")}</p>
        <div className="mt-5 grid gap-5 md:grid-cols-2">
          <div><p className="text-xs uppercase tracking-wide text-muted">{t("Baseline")}</p><p className="mt-1 font-medium text-ink">{preview.baseline.name}</p><p className="mt-1 break-all font-mono text-xs text-muted">{preview.baseline.commit_sha}</p><p className="mt-1 text-xs text-muted">{preview.baseline.file_count} {t("files inspected")}</p>
            {preview.baseline.important_files.length > 0 && <p className="mt-2 text-xs text-muted">{preview.baseline.important_files.join(" · ")}</p>}</div>
          <div><p className="text-xs uppercase tracking-wide text-muted">{t("Objective")}</p><p className="mt-1 font-mono text-sm text-ink">{preview.objective.metric_name}</p><p className="mt-1 text-sm text-muted">{t(preview.objective.direction === "MAXIMIZE" ? "Higher is better" : "Lower is better")}</p><p className="mt-2 text-xs text-muted">{t("Random seed")}: {preview.seed}</p></div>
        </div>
        <ol className="mt-6 space-y-3 border-l border-line pl-4 text-sm text-ink">
          <li><span className="font-medium">{t("1. Search literature")}</span><p className="mt-1 text-xs text-muted">{preview.literature.providers.join(" · ")} · {preview.literature.max_queries} {t("queries, up to")} {preview.literature.max_papers} {t("papers")}</p></li>
          <li><span className="font-medium">{t("2. Ground research in evidence")}</span><p className="mt-1 text-xs text-muted">{preview.papers.length ? preview.papers.join(" · ") : t("No uploaded papers; use retrieved sources.")}</p></li>
          <li><span className="font-medium">{t("3. Run controlled experiments")}</span><p className="mt-1 text-xs text-muted">{preview.max_iterations} {t("iterations; up to")} {preview.max_experiments} {t("experiments")} · {t(preview.change_type === "CONFIG_ONLY" ? "Configuration only" : preview.change_type === "CODE_CHANGE" ? "Source code changes" : "Let LabPilot choose")}</p></li>
          <li><span className="font-medium">{t("4. Save results and report")}</span></li>
        </ol>
        {preview.constraints && <div className="mt-5 rounded-lg border border-line bg-surface-2 p-3"><p className="text-xs font-medium text-muted">{t("Research constraints")}</p><p className="mt-1 whitespace-pre-wrap text-sm text-ink">{preview.constraints}</p></div>}
        {preview.warnings.length > 0 && <div className="mt-5 rounded-lg border border-warning/30 bg-warning-soft p-3 text-sm text-ink"><p className="font-medium">{t("Baseline checks")}</p><ul className="mt-2 list-inside list-disc text-xs">{preview.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></div>}
        <div className="mt-6 flex flex-wrap gap-3">
          <button type="button" disabled={busy} onClick={() => { setPreview(null); setError(""); }} className="secondary-button"><ArrowLeft size={15} />{t("Edit brief")}</button>
          <button type="button" disabled={busy || !preview.evidence_judge_ready} onClick={startResearch} className="primary-button disabled:opacity-50">{busy ? <LoaderCircle size={16} className="animate-spin" /> : <Check size={16} />}{busy ? t("Starting research…") : t("Confirm and start")}</button>
        </div>
      </Panel></div>}
    </>
  );
}
