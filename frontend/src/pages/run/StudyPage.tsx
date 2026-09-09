import { useParams } from "react-router-dom";
import { useRequest } from "@/hooks/useRequest";
import { getStudy } from "@/services/labpilot-api";
import { formatMetric } from "@/lib/utils";
import { EmptyState, Panel, SectionTitle, MonoValue, CopyButton } from "@/components/ui/primitives";
import { StudyStatusBadge } from "@/components/ui/badges";
import { DeltaValue } from "@/components/research/MetricSummary";
import { TrialChart } from "@/components/hpo/TrialChart";
import { SearchSpacePanel, TrialTable } from "@/components/hpo/TrialTable";

export default function StudyPage() {
  const { studyId = "" } = useParams();
  const { data, loading, error } = useRequest(() => getStudy(studyId), studyId);

  if (loading) {
    return (
      <div className="space-y-4">
        <Panel title="Study">
          <div className="h-32 animate-pulse rounded bg-surface-3" />
        </Panel>
      </div>
    );
  }
  if (error || !data) {
    return (
      <EmptyState
        title="Study not found"
        description={`No optimization study with ID ${studyId} in this research run.`}
      />
    );
  }

  const { run, study, trials } = data;
  const best = trials.find((t) => t.id === study.best_trial_id) ?? null;
  const bestDelta = best?.primary_metric_value
    ? best.primary_metric_value - run.baseline.value
    : null;

  return (
    <div className="space-y-4">
      <header>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="mr-auto font-mono text-lg font-semibold text-ink">{study.study_name}</h1>
          <StudyStatusBadge status={study.status} />
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs text-muted">
          <span className="flex items-center gap-1.5">
            <span className="text-faint">Study ID</span>
            <MonoValue>{study.id.slice(0, 13)}…</MonoValue>
            <CopyButton value={study.id} label="study ID" />
          </span>
          <span>
            <span className="text-faint">Hypothesis </span>
            <MonoValue>{study.hypothesis_id.slice(0, 8)}…</MonoValue>
          </span>
          <span>
            <span className="text-faint">Metric </span>
            <MonoValue>{study.primary_metric}</MonoValue>
          </span>
          <span>
            <span className="text-faint">Direction </span>
            <MonoValue>{study.direction}</MonoValue>
          </span>
          <span>
            <span className="text-faint">Sampler </span>
            <MonoValue>
              {study.sampler_name} · seed {study.sampler_seed}
            </MonoValue>
          </span>
        </div>
        <p className="mt-2 text-[13px] leading-relaxed text-muted">
          Inner-loop hyperparameter search. Every trial executes under the same Git worktree and
          Docker contracts as single experiments.{" "}
          <span className="text-faint">
            Study data shown here is a design fixture — the Phase 3 Optuna backend is in development.
          </span>
        </p>
      </header>

      {/* Summary strip */}
      <section aria-label="Study summary">
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-[6px] border border-line bg-line sm:grid-cols-3 lg:grid-cols-6">
          {[
            { label: "Trial budget", value: String(study.max_trials) },
            { label: "Completed", value: String(study.completed_trials) },
            { label: "Failed", value: String(study.failed_trials) },
            { label: "Pruned", value: String(study.pruned_trials) },
            { label: "Remaining", value: String(Math.max(0, study.max_trials - study.completed_trials - study.failed_trials - study.pruned_trials)) },
            {
              label: "Best trial",
              value: best ? `#${best.optuna_trial_number}` : "—",
            },
          ].map((cell) => (
            <div key={cell.label} className="bg-surface px-3.5 py-3">
              <p className="text-[11px] tracking-wide text-muted">{cell.label}</p>
              <p className="mt-1 font-mono text-[15px] font-medium text-ink">{cell.value}</p>
            </div>
          ))}
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
        {/* B. Trial performance chart */}
        <section aria-label="Trial performance">
          <Panel title={`Trial performance — ${study.primary_metric}`}>
            <TrialChart study={study} trials={trials} baselineValue={run.baseline.value} />
          </Panel>
        </section>

        {/* A. Best trial card */}
        <div className="space-y-4">
          <section aria-label="Best trial">
            <Panel title="Best completed trial">
              {best ? (
                <div className="space-y-3">
                  <div className="flex items-baseline justify-between">
                    <span className="text-xs text-muted">Trial #{best.optuna_trial_number}</span>
                    <span className="font-mono text-lg font-semibold text-ink">
                      {formatMetric(best.primary_metric_value)}
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between border-t border-line pt-2.5">
                    <span className="text-xs text-muted">Δ vs baseline</span>
                    <DeltaValue value={bestDelta} />
                  </div>
                  <div className="border-t border-line pt-2.5">
                    <p className="mb-1.5 text-xs text-muted">Parameters</p>
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
                      {Object.entries(best.parameters).map(([k, v]) => (
                        <div key={k} className="flex items-baseline justify-between gap-2">
                          <dt className="font-mono text-[11px] text-faint">{k}</dt>
                          <dd className="font-mono text-xs font-medium text-ink">{String(v)}</dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                </div>
              ) : (
                <p className="text-[13px] text-muted">
                  No completed trial yet; the best trial is selected only from completed, eligible trials.
                </p>
              )}
            </Panel>
          </section>

          {/* D. Search space */}
          <section aria-label="Search space">
            <Panel title="Search space">
              <SearchSpacePanel space={study.search_space} />
            </Panel>
          </section>
        </div>
      </div>

      {/* C. Trial table */}
      <section aria-label="Trials">
        <SectionTitle hint={`baseline ${run.baseline.metric_name} = ${run.baseline.value}`}>
          Trials
        </SectionTitle>
        <TrialTable study={study} trials={trials} baselineValue={run.baseline.value} />
      </section>
    </div>
  );
}
