import { Check } from "lucide-react";
import type { Step } from "@/types/domain";
import { cn } from "@/lib/utils";

const STAGES = [
  { label: "Literature", steps: ["literature"], phase: 1 },
  { label: "Evidence", steps: ["evidence"], phase: 1 },
  { label: "Baseline", steps: ["baseline"], phase: 2 },
  { label: "Hypothesis", steps: ["hypothesis"], phase: 1 },
  { label: "Experiment", steps: ["experiment"], phase: 2 },
  { label: "HPO", steps: ["hpo_plan", "hpo_suggest", "hpo_execute", "hpo_sync"], phase: 3 },
  { label: "Analyze", steps: ["analyze"], phase: 1 },
  { label: "Decision", steps: ["decision"], phase: 1 },
] as const;

const stageIndexForStep = (step: Step): number => {
  const idx = STAGES.findIndex((s) => (s.steps as readonly string[]).includes(step));
  return idx === -1 ? STAGES.length : idx; // "end" → all complete
};

/**
 * Research loop pipeline. When `nextStep` is provided, stages before the
 * cursor render as completed and the cursor stage as active. `plannedPhase`
 * marks stages whose backend is not implemented yet (HPO = Phase 3).
 */
export function ResearchLoop({
  nextStep,
  plannedPhases = [3],
  className,
}: {
  nextStep?: Step;
  plannedPhases?: number[];
  className?: string;
}) {
  const cursor = nextStep !== undefined ? stageIndexForStep(nextStep) : null;

  return (
    <ol className={cn("flex flex-wrap items-center gap-x-1 gap-y-2", className)}>
      {STAGES.map((stage, i) => {
        const done = cursor !== null && i < cursor;
        const active = cursor !== null && i === cursor && nextStep !== "end";
        const planned = plannedPhases.includes(stage.phase);
        return (
          <li key={stage.label} className="flex items-center gap-1">
            <div
              className={cn(
                "flex items-center gap-1.5 rounded-[5px] border px-2 py-1 text-xs font-medium transition-colors",
                done && "border-line bg-surface-2 text-muted",
                active && "border-accent/40 bg-accent-soft text-accent-ink",
                !done && !active && "border-dashed border-line-strong bg-transparent text-faint",
              )}
              title={planned ? `${stage.label} — backend in development (Phase ${stage.phase})` : stage.label}
            >
              {done && <Check className="size-3 text-success" aria-hidden="true" />}
              <span className={cn(active && "font-semibold")}>{stage.label}</span>
              {planned && (
                <span className="rounded-[3px] border border-line-strong px-1 text-[10px] font-medium tracking-wide text-faint">
                  P{stage.phase}
                </span>
              )}
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
