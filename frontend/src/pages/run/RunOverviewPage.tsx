import { useI18n } from "@/i18n";
import { Link, useOutletContext, useParams } from "react-router-dom";
import type { ResearchRun } from "@/types/domain";
import { formatMetric, formatRuntime } from "@/lib/utils";
import { KeyValue, Panel, SectionTitle } from "@/components/ui/primitives";
import { DecisionBadge } from "@/components/ui/badges";
import { MetricSummary } from "@/components/research/MetricSummary";
import { ResearchLoop } from "@/components/research/ResearchLoop";
import { BudgetProgress } from "@/components/research/BudgetProgress";

export default function RunOverviewPage() {
  const { t } = useI18n();
  const { run } = useOutletContext<{ run: ResearchRun }>();
  const { researchId = "" } = useParams();

  const candidateValues = run.experiments
    .filter((e) => e.purpose === "CANDIDATE" && e.metric_value !== null)
    .map((e) => e.metric_value as number);
  const best =
    candidateValues.length === 0
      ? null
      : run.baseline.direction === "MAXIMIZE"
        ? Math.max(...candidateValues)
        : Math.min(...candidateValues);

  const totalRuntime = run.experiments.reduce((sum, e) => sum + (e.runtime_seconds ?? 0), 0);

  return (
    <div className="space-y-4">
      {/* A. Metric summary */}
      <section aria-label={t("Metric summary")}>
        <SectionTitle hint={t("absolute metric units; deltas are not relative percentages")}>
          {t("Metric summary")}</SectionTitle>
        <MetricSummary
          baseline={run.baseline}
          best={best}
          decision={run.decision ?? t("PENDING")}
        />
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* B. Research progress */}
        <section aria-label={t("Research progress")}>
          <Panel title={t("Research progress")}>
            <KeyValue
              items={[
                { key: t("Iteration"), value: `${run.iteration} of ${run.budget.max_iterations}` },
                {
                  key: t("Experiments used"),
                  value: `${run.budget.experiments} of ${run.budget.max_experiments}`,
                },
                { key: t("Failed experiments"), value: String(run.budget.failed_experiments) },
                { key: t("Replans"), value: `${run.budget.replans} of ${run.budget.max_replans}` },
                { key: t("Total experiment runtime"), value: formatRuntime(totalRuntime || null) },
                {
                  key: t("Termination"),
                  value: run.termination_reason ?? "—",
                },
              ]}
            />
            <div className="mt-4 border-t border-line pt-4">
              <p className="mb-2.5 text-xs font-medium text-muted">{t("Budget consumption")}</p>
              <BudgetProgress budget={run.budget} />
            </div>
          </Panel>
        </section>

        {/* D. Decision explanation */}
        <section aria-label={t("Decision")}>
          <Panel
            title={t("Decision")}
            actions={run.decision ? <DecisionBadge decision={run.decision} /> : undefined}
          >
            {run.decisions.length === 0 ? (
              <p className="text-[13px] leading-relaxed text-muted">
                {t("No decision has been recorded yet. The decision engine runs after the analyze step of the current iteration.")}</p>
            ) : (
              <ol className="space-y-4">
                {run.decisions.map((d, i) => (
                  <li key={i} className="flex gap-3">
                    <DecisionBadge decision={d.decision} />
                    <div className="min-w-0">
                      <p className="text-[13px] leading-relaxed text-ink-2">{d.reason}</p>
                      <p className="mt-1 text-[11px] text-faint">
                        {d.improvement !== null && (
                          <>
                            {t("improvement")}{" "}
                            <span className="font-mono">{formatMetric(d.improvement)}</span> ·{" "}
                          </>
                        )}
                        {t("deterministic threshold comparison — not an LLM judgement")}</p>
                    </div>
                  </li>
                ))}
              </ol>
            )}
            <p className="mt-4 border-t border-line pt-3 text-[11px] leading-relaxed text-faint">
              {t("Policy: improvement ≥ min_delta (")}{" "}{run.baseline.min_delta}{t(") → KEEP; regression ≥")}{" "}
              {run.baseline.regression_delta} {t("→ REJECT; otherwise REPLAN if the budget allows.")}</p>
          </Panel>
        </section>
      </div>

      {/* C. Research loop */}
      <section aria-label={t("Research loop")}>
        <Panel
          title={t("Research loop")}
          actions={
            run.next_step !== "end" && (
              <span className="font-mono text-[11px] text-muted">{t("next step:")}{" "}{run.next_step}</span>
            )
          }
        >
          <ResearchLoop nextStep={run.next_step} />
        </Panel>
      </section>

      {/* Hypothesis + experiments shortcut */}
      <section aria-label={t("Current hypothesis")}>
        <Panel title={t("Current hypothesis")}>
          {run.hypotheses.length === 0 ? (
            <p className="text-[13px] text-muted">{t("No hypothesis recorded in this state.")}</p>
          ) : (
            <div className="space-y-3">
              {run.hypotheses.map((h) => (
                <div key={h.id} className="rounded-[6px] border border-line bg-surface-2 px-3.5 py-3">
                  <p className="text-[13px] font-medium leading-relaxed text-ink">{h.statement}</p>
                  <p className="mt-1.5 text-xs leading-relaxed text-muted">{h.motivation}</p>
                  <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 font-mono text-[11px] text-faint">
                    <span>{t("expected:")}{" "}{h.expected_effect}</span>
                    <span>{t("confidence:")}{" "}{h.confidence}</span>
                    <span>{t("status:")}{" "}{t(h.status)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
          <p className="mt-3 text-xs text-muted">
            {t("See")}{" "}
            <Link
              to={`/runs/${researchId}/experiments`}
              className="font-medium text-accent-ink underline-offset-2 hover:underline"
            >
              {t("experiments")}</Link>{" "}
            {t("for measured results behind the decision.")}</p>
        </Panel>
      </section>
    </div>
  );
}
