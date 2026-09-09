import { Link, useOutletContext } from "react-router-dom";
import { ArrowRight, FlaskConical } from "lucide-react";
import type { ResearchRun } from "@/types/domain";
import { EmptyState, Panel } from "@/components/ui/primitives";
import { StudyStatusBadge } from "@/components/ui/badges";
import { shortId } from "@/lib/utils";

export default function RunHpoPage() {
  const { run } = useOutletContext<{ run: ResearchRun }>();

  if (run.studies.length === 0) {
    return (
      <EmptyState
        icon={<FlaskConical className="size-6" strokeWidth={1.5} />}
        title="No optimization study exists yet"
        description={
          run.executor === "fake"
            ? "Fake-executor runs do not create optimization studies. Studies are created when a hypothesis is planned with a search space (Phase 3)."
            : "Studies appear here when a hypothesis is planned with a typed search space. The Optuna backend (Phase 3) is in development; this UI is ready to display it."
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      {run.studies.map((study) => {
        const best = run.trials.find((t) => t.id === study.best_trial_id);
        return (
          <Panel
            key={study.id}
            title={<span className="font-mono">{study.study_name}</span>}
            actions={<StudyStatusBadge status={study.status} />}
            bodyClassName="p-4"
          >
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-[13px] text-ink-2">
              <span>
                <span className="text-muted">Trials </span>
                <span className="font-mono">
                  {study.completed_trials + study.failed_trials + study.pruned_trials} / {study.max_trials}
                </span>
              </span>
              <span>
                <span className="text-muted">Sampler </span>
                <span className="font-mono">
                  {study.sampler_name} (seed {study.sampler_seed})
                </span>
              </span>
              <span>
                <span className="text-muted">Best trial </span>
                <span className="font-mono">
                  {best ? `#${best.optuna_trial_number} · ${best.primary_metric_value?.toFixed(4)}` : "—"}
                </span>
              </span>
              <Link
                to={`/runs/${run.research_id}/hpo/${study.id}`}
                className="ml-auto inline-flex items-center gap-1 text-xs font-medium text-accent-ink hover:underline"
              >
                View study
                <ArrowRight className="size-3" aria-hidden="true" />
              </Link>
            </div>
            <p className="mt-2 font-mono text-[11px] text-faint">study id: {shortId(study.id, 24)}…</p>
          </Panel>
        );
      })}
    </div>
  );
}
