import { useI18n } from "@/i18n";
import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { Braces } from "lucide-react";
import type { ResearchRun } from "@/types/domain";
import { useRequest } from "@/hooks/useRequest";
import { getRawState } from "@/services/labpilot-api";
import { cn, formatTimestamp } from "@/lib/utils";
import { KeyValue, MonoValue, Panel } from "@/components/ui/primitives";
import { BudgetProgress } from "@/components/research/BudgetProgress";
import { DecisionBadge, DecisionPendingBadge } from "@/components/ui/badges";

/**
 * ResearchState inspector: structured sections first, optional raw JSON
 * view for technical demos. The backend state is the single source of truth.
 */
export default function RunStatePage() {
  const { t, locale } = useI18n();
  const { run } = useOutletContext<{ run: ResearchRun }>();
  const researchId = run.research_id;
  const { data: rawState } = useRequest(() => getRawState(researchId), researchId);
  const [showRaw, setShowRaw] = useState(false);

  const baselineExperiment = run.experiments.find((e) => e.purpose === "BASELINE");

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title={t("Identity")}>
          <KeyValue
            columns={1}
            items={[
              { key: "schema_version", value: <MonoValue>1</MonoValue> },
              { key: "research_id", value: <MonoValue truncate>{run.research_id}</MonoValue> },
              { key: "status", value: run.status },
              { key: "next_step", value: <MonoValue>{run.next_step}</MonoValue> },
              { key: "revision", value: <MonoValue>{run.revision}</MonoValue> },
              { key: "iteration", value: <MonoValue>{run.iteration}</MonoValue> },
              { key: "created_at", value: formatTimestamp(run.created_at, locale) },
              { key: "updated_at", value: formatTimestamp(run.updated_at, locale) },
            ]}
          />
        </Panel>

        <Panel title={t("Decision")}>
          <KeyValue
            columns={1}
            items={[
              {
                key: "decision",
                value: run.decision ? <DecisionBadge decision={run.decision} /> : <DecisionPendingBadge />,
              },
              { key: t("decisions recorded"), value: <MonoValue>{run.decisions.length}</MonoValue> },
              {
                key: t("active hypothesis"),
                value: run.hypotheses.length ? (
                  <MonoValue truncate>{run.hypotheses[run.hypotheses.length - 1].id}</MonoValue>
                ) : (
                  "—"
                ),
              },
              {
                key: "termination_reason",
                value: run.termination_reason ?? "—",
              },
            ]}
          />
          {run.decisions.length > 0 && (
            <p className="mt-3 border-t border-line pt-2.5 text-xs leading-relaxed text-muted">
              {t("Latest:")}{" "}{run.decisions[run.decisions.length - 1].reason}
            </p>
          )}
        </Panel>

        <Panel title={t("Budget")}>
          <BudgetProgress budget={run.budget} />
        </Panel>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title={t("Baseline")}>
          <KeyValue
            columns={2}
            items={[
              { key: "metric_name", value: <MonoValue>{run.baseline.metric_name}</MonoValue> },
              { key: t("value"), value: <MonoValue>{run.baseline.value}</MonoValue> },
              { key: t("direction"), value: run.baseline.direction },
              { key: "min_delta", value: <MonoValue>{run.baseline.min_delta}</MonoValue> },
              { key: "regression_delta", value: <MonoValue>{run.baseline.regression_delta}</MonoValue> },
              {
                key: t("baseline experiment"),
                value: baselineExperiment ? (
                  <MonoValue truncate>{baselineExperiment.id.slice(0, 14)}…</MonoValue>
                ) : (
                  "—"
                ),
              },
            ]}
          />
        </Panel>

        <Panel title={t("Collections")}>
          <KeyValue
            columns={2}
            items={[
              { key: "papers", value: <MonoValue>{run.papers.length}</MonoValue> },
              { key: "claims", value: <MonoValue>{run.claims.length}</MonoValue> },
              { key: "evidence", value: <MonoValue>{run.evidence.length}</MonoValue> },
              { key: "hypotheses", value: <MonoValue>{run.hypotheses.length}</MonoValue> },
              { key: "patches", value: <MonoValue>{run.patches.length}</MonoValue> },
              { key: t("experiments"), value: <MonoValue>{run.experiments.length}</MonoValue> },
              { key: "studies", value: <MonoValue>{run.studies.length}</MonoValue> },
              { key: "trials", value: <MonoValue>{run.trials.length}</MonoValue> },
            ]}
          />
        </Panel>
      </div>

      {/* Checkpoint / execution */}
      <Panel title={t("Checkpoint & execution")}>
        <KeyValue
          columns={3}
          items={[
            { key: t("next_step cursor"), value: <MonoValue>{run.next_step}</MonoValue> },
            { key: "revision", value: <MonoValue>{run.revision}</MonoValue> },
            { key: t("executor"), value: <MonoValue>{run.executor}</MonoValue> },
            {
              key: t("storage"),
              value: <MonoValue truncate>.labpilot/labpilot.sqlite3</MonoValue>,
            },
            {
              key: t("resume behavior"),
              value: "completed steps commit exactly one revision",
            },
          ]}
        />
      </Panel>

      {/* Raw state toggle */}
      <div>
        <button
          type="button"
          onClick={() => setShowRaw((v) => !v)}
          aria-expanded={showRaw}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-[5px] border border-line-strong px-2.5 py-1 text-xs font-medium transition-colors",
            showRaw ? "bg-accent-soft text-accent-ink" : "bg-surface text-ink-2 hover:bg-surface-2",
          )}
        >
          <Braces className="size-3.5" aria-hidden="true" />
          {showRaw ? t("Hide raw state") : t("Show raw state (JSON)")}
        </button>
        {showRaw && (
          <pre className="mt-2.5 max-h-[480px] overflow-auto rounded-[6px] border border-line bg-surface-2 p-4 font-mono text-[11px] leading-relaxed text-ink-2">
            {JSON.stringify(rawState, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
