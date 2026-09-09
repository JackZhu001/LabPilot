import { Link, useOutletContext, useParams } from "react-router-dom";
import type { ResearchRun } from "@/types/domain";
import { formatMetric, formatRuntime } from "@/lib/utils";
import { KeyValue, Panel, SectionTitle } from "@/components/ui/primitives";
import { DecisionBadge } from "@/components/ui/badges";
import { MetricSummary } from "@/components/research/MetricSummary";
import { ResearchLoop } from "@/components/research/ResearchLoop";
import { BudgetProgress } from "@/components/research/BudgetProgress";

export default function RunOverviewPage() {
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
      <section aria-label="Metric summary">
        <SectionTitle hint="absolute metric units; deltas are not relative percentages">
          Metric summary
        </SectionTitle>
        <MetricSummary
          baseline={run.baseline}
          best={best}
          decision={run.decision ?? "PENDING"}
        />
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* B. Research progress */}
        <section aria-label="Research progress">
          <Panel title="Research progress">
            <KeyValue
              items={[
                { key: "Iteration", value: `${run.iteration} of ${run.budget.max_iterations}` },
                {
                  key: "Experiments used",
                  value: `${run.budget.experiments} of ${run.budget.max_experiments}`,
                },
                { key: "Failed experiments", value: String(run.budget.failed_experiments) },
                { key: "Replans", value: `${run.budget.replans} of ${run.budget.max_replans}` },
                { key: "Total experiment runtime", value: formatRuntime(totalRuntime || null) },
                {
                  key: "Termination",
                  value: run.termination_reason ?? "—",
                },
              ]}
            />
            <div className="mt-4 border-t border-line pt-4">
              <p className="mb-2.5 text-xs font-medium text-muted">Budget consumption</p>
              <BudgetProgress budget={run.budget} />
            </div>
          </Panel>
        </section>

        {/* D. Decision explanation */}
        <section aria-label="Decision">
          <Panel
            title="Decision"
            actions={run.decision ? <DecisionBadge decision={run.decision} /> : undefined}
          >
            {run.decisions.length === 0 ? (
              <p className="text-[13px] leading-relaxed text-muted">
                No decision has been recorded yet. The decision engine runs after the analyze step
                of the current iteration.
              </p>
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
                            improvement{" "}
                            <span className="font-mono">{formatMetric(d.improvement)}</span> ·{" "}
                          </>
                        )}
                        deterministic threshold comparison — not an LLM judgement
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            )}
            <p className="mt-4 border-t border-line pt-3 text-[11px] leading-relaxed text-faint">
              Policy: improvement ≥ min_delta ({run.baseline.min_delta}) → KEEP; regression ≥{" "}
              {run.baseline.regression_delta} → REJECT; otherwise REPLAN if the budget allows.
            </p>
          </Panel>
        </section>
      </div>

      {/* C. Research loop */}
      <section aria-label="Research loop">
        <Panel
          title="Research loop"
          actions={
            run.next_step !== "end" && (
              <span className="font-mono text-[11px] text-muted">next step: {run.next_step}</span>
            )
          }
        >
          <ResearchLoop nextStep={run.next_step} plannedPhases={[3, 5]} />
        </Panel>
      </section>

      {/* Hypothesis + experiments shortcut */}
      <section aria-label="Current hypothesis">
        <Panel title="Current hypothesis">
          {run.hypotheses.length === 0 ? (
            <p className="text-[13px] text-muted">No hypothesis recorded in this state.</p>
          ) : (
            <div className="space-y-3">
              {run.hypotheses.map((h) => (
                <div key={h.id} className="rounded-[6px] border border-line bg-surface-2 px-3.5 py-3">
                  <p className="text-[13px] font-medium leading-relaxed text-ink">{h.statement}</p>
                  <p className="mt-1.5 text-xs leading-relaxed text-muted">{h.motivation}</p>
                  <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 font-mono text-[11px] text-faint">
                    <span>expected: {h.expected_effect}</span>
                    <span>confidence: {h.confidence}</span>
                    <span>status: {h.status}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
          <p className="mt-3 text-xs text-muted">
            See{" "}
            <Link
              to={`/runs/${researchId}/experiments`}
              className="font-medium text-accent-ink underline-offset-2 hover:underline"
            >
              experiments
            </Link>{" "}
            for measured results behind the decision.
          </p>
        </Panel>
      </section>
    </div>
  );
}
