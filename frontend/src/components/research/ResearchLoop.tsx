import { useI18n } from "@/i18n";
import { Check } from "lucide-react";
import type { Step } from "@/types/domain";
import { cn } from "@/lib/utils";

const STAGES = [
  { label: "Literature", steps: ["inspect_repository", "plan_literature_queries", "retrieve_papers", "literature"] },
  { label: "Evidence", steps: ["extract_claims", "synthesize_evidence", "evidence"] },
  { label: "Baseline", steps: ["baseline"] },
  { label: "Hypothesis", steps: ["generate_hypotheses", "hypothesis"] },
  { label: "Experiment", steps: ["plan_experiment", "generate_patch", "experiment"] },
  { label: "HPO", steps: ["hpo_plan", "hpo_suggest", "hpo_execute", "hpo_sync"] },
  { label: "Analyze", steps: ["analyze", "critique"] },
  { label: "Decision", steps: ["decision"] },
] as const;

const stageIndexForStep = (step: Step): number => {
  const idx = STAGES.findIndex((s) => (s.steps as readonly string[]).includes(step));
  return idx === -1 ? STAGES.length : idx; // "end" → all complete
};

/**
 * Research loop pipeline. When `nextStep` is provided, stages before the
 * cursor render as completed and the cursor stage as active.
 */
export function ResearchLoop({
  nextStep,
  className,
}: {
  nextStep?: Step;
  className?: string;
}) {
  const { t } = useI18n();
  const cursor = nextStep !== undefined ? stageIndexForStep(nextStep) : null;

  return (
    <ol className={cn("flex flex-wrap items-center gap-x-1 gap-y-2", className)}>
      {STAGES.map((stage, i) => {
        const done = cursor !== null && i < cursor;
        const active = cursor !== null && i === cursor && nextStep !== "end";
        return (
          <li key={stage.label} data-active={active} className="flex items-center gap-1">
            <div
              className={cn(
                "flex items-center gap-1.5 rounded-[5px] border px-2 py-1 text-xs font-medium transition-colors",
                done && "border-line bg-surface-2 text-muted",
                active && "border-accent/40 bg-accent-soft text-accent-ink",
                !done && !active && "border-dashed border-line-strong bg-transparent text-faint",
              )}
              title={t(stage.label)}
            >
              {done && <Check className="size-3 text-success" aria-hidden="true" />}
              <span className={cn(active && "font-semibold")}>{t(stage.label)}</span>
            </div>
            {i < STAGES.length - 1 && (
              <span aria-hidden="true" className={cn("text-[10px]", i < (cursor ?? 0) ? "text-success" : "text-faint")}>
                →
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
