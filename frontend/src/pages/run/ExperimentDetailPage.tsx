import { Link, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, FileDown, FileText, XCircle } from "lucide-react";
import { useRequest } from "@/hooks/useRequest";
import { getExperiment } from "@/services/labpilot-api";
import { formatRuntime, formatTimestamp, shortId } from "@/lib/utils";
import {
  CopyButton,
  EmptyState,
  KeyValue,
  MonoValue,
  Panel,
  ShaValue,
} from "@/components/ui/primitives";
import {
  DecisionBadge,
  DecisionPendingBadge,
  ExperimentStatusBadge,
  PurposeBadge,
} from "@/components/ui/badges";
import { CodeDiff } from "@/components/ui/CodeDiff";

function ArtifactRow({ name, path }: { name: string; path: string }) {
  return (
    <li className="flex items-center justify-between gap-3 py-1.5 first:pt-0 last:pb-0">
      <div className="flex min-w-0 items-center gap-2">
        <FileText className="size-3.5 shrink-0 text-faint" aria-hidden="true" />
        <span className="text-[13px] font-medium text-ink">{name}</span>
        <MonoValue truncate className="text-faint">{path}</MonoValue>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <CopyButton value={path} label="artifact path" />
        <button
          type="button"
          disabled
          title="Artifact access requires the backend integration (planned)"
          className="inline-flex items-center gap-1 rounded-[4px] border border-line px-1.5 py-0.5 text-[11px] font-medium text-faint"
        >
          <FileDown className="size-3" aria-hidden="true" />
          Download
        </button>
      </div>
    </li>
  );
}

export default function ExperimentDetailPage() {
  const { researchId = "", experimentId = "" } = useParams();
  const { data, loading, error } = useRequest(
    () => getExperiment(experimentId),
    [experimentId],
  );

  if (loading) {
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Summary">
          <div className="h-40 animate-pulse rounded bg-surface-3" />
        </Panel>
        <Panel title="Provenance">
          <div className="h-40 animate-pulse rounded bg-surface-3" />
        </Panel>
      </div>
    );
  }
  if (error || !data) {
    return (
      <EmptyState
        title="Experiment not found"
        description={`No experiment with ID ${experimentId} in this research run.`}
        action={
          <Link
            to={`/runs/${researchId}/experiments`}
            className="text-[13px] font-medium text-accent-ink hover:underline"
          >
            Back to experiments
          </Link>
        }
      />
    );
  }

  const { run, experiment } = data;
  const prov = experiment.provenance;

  return (
    <div className="space-y-4">
      <header>
        <Link
          to={`/runs/${researchId}/experiments`}
          className="mb-2 inline-flex items-center gap-1 text-xs font-medium text-muted transition-colors hover:text-ink"
        >
          <ArrowLeft className="size-3.5" aria-hidden="true" />
          All experiments
        </Link>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="mr-auto font-mono text-lg font-semibold text-ink">
            {experiment.id.slice(0, 18)}…
          </h1>
          <PurposeBadge purpose={experiment.purpose} />
          <ExperimentStatusBadge status={experiment.status} />
          {experiment.decision ? <DecisionBadge decision={experiment.decision} /> : <DecisionPendingBadge />}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs text-muted">
          <span className="flex items-center gap-1.5">
            <span className="text-faint">Experiment ID</span>
            <MonoValue>{shortId(experiment.id, 12)}</MonoValue>
            <CopyButton value={experiment.id} label="experiment ID" />
          </span>
          <span className="text-faint">
            Sequence <MonoValue>#{experiment.sequence}</MonoValue>
          </span>
          <span>
            <Link
              to={`/runs/${researchId}`}
              className="font-medium text-accent-ink underline-offset-2 hover:underline"
            >
              {run.goal}
            </Link>
          </span>
        </div>
      </header>

      {experiment.status === "FAILED" && (
        <div role="alert" className="rounded-panel border border-danger/30 bg-danger-soft/40 px-4 py-3">
          <p className="flex items-center gap-1.5 text-sm font-medium text-danger">
            <XCircle className="size-4" aria-hidden="true" />
            Experiment failed
          </p>
          {experiment.error && <p className="mt-1 text-[13px] text-ink-2">{experiment.error}</p>}
        </div>
      )}

      {/* Summary */}
      <section aria-label="Experiment summary">
        <Panel title="Summary">
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-[6px] border border-line bg-line sm:grid-cols-4">
            {[
              { label: "Primary metric", value: experiment.metric_value?.toFixed(4) ?? "—" },
              { label: "Metric name", value: experiment.config.metric_name },
              { label: "Runtime", value: formatRuntime(experiment.runtime_seconds) },
              { label: "Executor", value: experiment.executor },
            ].map((cell) => (
              <div key={cell.label} className="bg-surface px-3.5 py-3">
                <p className="text-[11px] tracking-wide text-muted">{cell.label}</p>
                <p className="mt-1 font-mono text-[15px] font-medium text-ink">{cell.value}</p>
              </div>
            ))}
          </div>
          {prov?.report && (
            <div className="mt-3">
              <KeyValue
                columns={3}
                items={Object.entries(prov.report.metrics).map(([name, value]) => ({
                  key: name,
                  value: <span className="font-mono text-xs">{value}</span>,
                }))}
              />
            </div>
          )}
        </Panel>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Configuration */}
        <section aria-label="Configuration">
          <Panel title="Configuration">
            <KeyValue
              columns={2}
              items={[
                { key: "seed", value: <span className="font-mono text-xs">{experiment.config.seed}</span> },
                { key: "direction", value: experiment.config.direction },
                ...Object.entries(experiment.config.parameters).map(([k, v]) => ({
                  key: k,
                  value: <span className="font-mono text-xs">{String(v)}</span>,
                })),
              ]}
            />
          </Panel>
        </section>

        {/* Docker provenance */}
        <section aria-label="Execution environment">
          <Panel title="Execution environment">
            {!prov ? (
              <p className="text-[13px] leading-relaxed text-muted">
                Fake executor: no isolated execution provenance is recorded in fake mode. Real
                provenance (Git worktree, Docker identity, artifacts) is captured in Docker mode.
              </p>
            ) : (
              <KeyValue
                columns={2}
                items={[
                  { key: "Image", value: <span className="font-mono text-xs">{prov.docker.image}</span> },
                  {
                    key: "Image ID",
                    value: prov.docker.image_id ? (
                      <span className="inline-flex items-center gap-1">
                        <MonoValue truncate>{prov.docker.image_id.replace("sha256:", "").slice(0, 19)}…</MonoValue>
                        <CopyButton value={prov.docker.image_id} label="image ID" />
                      </span>
                    ) : (
                      "—"
                    ),
                  },
                  {
                    key: "Container ID",
                    value: prov.docker.container_id ? (
                      <span className="inline-flex items-center gap-1">
                        <MonoValue truncate>{prov.docker.container_id.slice(0, 12)}…</MonoValue>
                        <CopyButton value={prov.docker.container_id} label="container ID" />
                      </span>
                    ) : (
                      "—"
                    ),
                  },
                  { key: "Network mode", value: prov.docker.network },
                  { key: "CPU limit", value: `${prov.docker.cpus}` },
                  { key: "Memory limit", value: `${prov.docker.memory_mb} MiB` },
                  { key: "Exit code", value: prov.exit_code === null ? "—" : String(prov.exit_code) },
                  { key: "Execution status", value: prov.status },
                  { key: "Started", value: formatTimestamp(prov.started_at) },
                  { key: "Finished", value: formatTimestamp(prov.finished_at) },
                  { key: "Total runtime", value: formatRuntime(prov.runtime_seconds) },
                  {
                    key: "Training command",
                    value: <span className="font-mono text-xs">{prov.training_command.join(" ")}</span>,
                  },
                ]}
              />
            )}
          </Panel>
        </section>
      </div>

      {/* Git provenance */}
      <section aria-label="Git provenance">
        <Panel title="Git provenance">
          {!prov ? (
            <p className="text-[13px] text-muted">No Git provenance (fake executor).</p>
          ) : (
            <div className="space-y-4">
              <KeyValue
                columns={3}
                items={[
                  { key: "Base commit", value: <ShaValue sha={prov.git.base_commit_sha} /> },
                  { key: "Baseline SHA after", value: <ShaValue sha={prov.git.baseline_sha_after ?? ""} /> },
                  {
                    key: "Baseline integrity",
                    value:
                      prov.git.baseline_clean_after === true ? (
                        <span className="inline-flex items-center gap-1 text-[13px] font-medium text-success">
                          <CheckCircle2 className="size-3.5" aria-hidden="true" />
                          clean after experiment
                        </span>
                      ) : (
                        <span className="text-[13px] font-medium text-danger">dirty</span>
                      ),
                  },
                  {
                    key: "Worktree",
                    value: <MonoValue truncate>{prov.git.worktree_identity}</MonoValue>,
                  },
                  {
                    key: "Worktree path",
                    value: <MonoValue truncate>{prov.git.worktree_path}</MonoValue>,
                  },
                  { key: "Source hash (SHA-256)", value: prov.source_sha256 ? (
                    <span className="inline-flex items-center gap-1">
                      <MonoValue truncate>{prov.source_sha256.slice(0, 16)}…</MonoValue>
                      <CopyButton value={prov.source_sha256} label="source hash" />
                    </span>
                  ) : ("—") },
                ]}
              />
              <div>
                <p className="mb-2 text-xs font-medium text-muted">
                  Experiment diff {prov.git.actual_git_diff ? "" : "(none — baseline run)"}
                </p>
                <CodeDiff diff={prov.git.actual_git_diff} title="actual.diff" />
              </div>
            </div>
          )}
        </Panel>
      </section>

      {/* Artifacts */}
      {prov && (
        <section aria-label="Artifacts">
          <Panel title="Artifacts">
            <ul className="divide-y divide-line">
              <ArtifactRow name="stdout.log" path={prov.artifacts.stdout_path} />
              <ArtifactRow name="stderr.log" path={prov.artifacts.stderr_path} />
              <ArtifactRow name="metrics.json" path={prov.artifacts.metrics_path} />
              <ArtifactRow name="provenance.json" path={prov.artifacts.provenance_path} />
              <ArtifactRow name="patch.diff" path={prov.artifacts.patch_path} />
              <ArtifactRow name="actual.diff" path={prov.artifacts.actual_diff_path} />
            </ul>
          </Panel>
        </section>
      )}
    </div>
  );
}
