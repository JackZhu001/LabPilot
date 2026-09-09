import type { ResearchBudget } from "@/types/domain";
import { cn } from "@/lib/utils";

function Bar({ used, max, tone }: { used: number; max: number; tone: string }) {
  const pct = max === 0 ? 0 : Math.min(100, (used / max) * 100);
  const full = used >= max && max > 0;
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-neutral-soft">
      <div
        className={cn("h-full rounded-full transition-[width]", full ? tone : "bg-accent/70", tone === "danger" && "bg-danger/80")}
        style={{ width: `${pct}%` }}
        role="progressbar"
        aria-valuenow={used}
        aria-valuemin={0}
        aria-valuemax={max}
      />
    </div>
  );
}

/** Deterministic budget counters — hard limits on autonomous work. */
export function BudgetProgress({ budget, className }: { budget: ResearchBudget; className?: string }) {
  const rows: { label: string; used: number; max: number; danger?: boolean }[] = [
    { label: "Experiments", used: budget.experiments, max: budget.max_experiments },
    {
      label: "Failed experiments",
      used: budget.failed_experiments,
      max: budget.max_failed_experiments,
      danger: true,
    },
    { label: "Iterations", used: budget.iterations, max: budget.max_iterations },
    { label: "Replans", used: budget.replans, max: budget.max_replans },
  ];
  if (budget.max_hpo_trials > 0) {
    rows.push({ label: "HPO trials", used: budget.hpo_trials, max: budget.max_hpo_trials });
  }

  return (
    <div className={cn("space-y-3", className)}>
      {rows.map((row) => (
        <div key={row.label}>
          <div className="mb-1 flex items-baseline justify-between">
            <span className="text-xs text-muted">{row.label}</span>
            <span className="font-mono text-xs text-ink">
              {row.used}
              <span className="text-faint"> / {row.max}</span>
            </span>
          </div>
          <Bar used={row.used} max={row.max} tone={row.danger ? "danger" : "accent"} />
        </div>
      ))}
    </div>
  );
}
