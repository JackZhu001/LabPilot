import { useI18n } from "@/i18n";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, FileDown, FileText, XCircle } from "lucide-react";
import { useRequest } from "@/hooks/useRequest";
import { artifactUrl, getExperiment } from "@/services/labpilot-api";
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

function ArtifactRow({ name, path, url }: { name: string; path: string; url: string | null }) {
  const { t } = useI18n();
  return (
    <li className="flex items-center justify-between gap-3 py-1.5 first:pt-0 last:pb-0">
      <div className="flex min-w-0 items-center gap-2">
        <FileText className="size-3.5 shrink-0 text-faint" aria-hidden="true" />
        <span className="text-[13px] font-medium text-ink">{name}</span>
        <MonoValue truncate className="text-faint">{path}</MonoValue>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <CopyButton value={path} label={t("artifact path")} />
        <a
          href={url ?? undefined}
          aria-disabled={!url}
          title={url ? `Download ${name}` : t("Downloads are unavailable in fixture mode")}
          className="inline-flex items-center gap-1 rounded-[4px] border border-line px-1.5 py-0.5 text-[11px] font-medium text-faint aria-disabled:pointer-events-none aria-disabled:opacity-50"
        >
          <FileDown className="size-3" aria-hidden="true" />
          {t("Download")}</a>
      </div>
    </li>
  );
}

export default function ExperimentDetailPage() {
  const { t, locale } = useI18n();
  const { researchId = "", experimentId = "" } = useParams();
  const { data, loading, error } = useRequest(() => getExperiment(experimentId), experimentId);

  if (loading) {
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title={t("Summary")}>
          <div className="h-40 animate-pulse rounded bg-surface-3" />
        </Panel>
        <Panel title={t("Provenance")}>
          <div className="h-40 animate-pulse rounded bg-surface-3" />
        </Panel>
      </div>
    );
  }
  if (error || !data) {
    return (
      <EmptyState
        title={t("Experiment not found")}
        description={`No experiment with ID ${experimentId} in this research run.`}
        action={
          <Link
            to={`/runs/${researchId}/experiments`}
            className="text-[13px] font-medium text-accent-ink hover:underline"
          >
            {t("Back to experiments")}</Link>
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
          {t("All experiments")}</Link>
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
            <span className="text-faint">{t("Experiment ID")}</span>
            <MonoValue>{shortId(experiment.id, 12)}</MonoValue>
            <CopyButton value={experiment.id} label={t("experiment ID")} />
          </span>
          <span className="text-faint">
            {t("Sequence")}<MonoValue>#{experiment.sequence}</MonoValue>
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
            {t("Experiment failed")}</p>
          {experiment.error && <p className="mt-1 text-[13px] text-ink-2">{experiment.error}</p>}
        </div>
      )}

      {/* Summary */}
      <section aria-label={t("Experiment summary")}>
        <Panel title={t("Summary")}>
          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-[6px] border border-line bg-line sm:grid-cols-4">
            {[
              { label: t("Primary metric"), value: experiment.metric_value?.toFixed(4) ?? "—" },
              { label: t("Metric name"), value: experiment.config.metric_name },
              { label: t("Runtime"), value: formatRuntime(experiment.runtime_seconds) },
              { label: t("Executor"), value: experiment.executor },
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
        <section aria-label={t("Configuration")}>
          <Panel title={t("Configuration")}>
            <KeyValue
              columns={2}
              items={[
                { key: t("seed"), value: <span className="font-mono text-xs">{experiment.config.seed}</span> },
                { key: t("direction"), value: experiment.config.direction },
                ...Object.entries(experiment.config.parameters).map(([k, v]) => ({
                  key: k,
                  value: <span className="font-mono text-xs">{String(v)}</span>,
                })),
              ]}
            />
          </Panel>
        </section>

        {/* Docker provenance */}
        <section aria-label={t("Execution environment")}>
          <Panel title={t("Execution environment")}>
            {!prov ? (
              <p className="text-[13px] leading-relaxed text-muted">
                {t("Fake executor: no isolated execution provenance is recorded in fake mode. Real provenance (Git worktree, Docker identity, artifacts) is captured in Docker mode.")}</p>
            ) : (
              <KeyValue
                columns={2}
                items={[
                  { key: t("Image"), value: <span className="font-mono text-xs">{prov.docker.image}</span> },
                  {
                    key: t("Image ID"),
                    value: prov.docker.image_id ? (
                      <span className="inline-flex items-center gap-1">
                        <MonoValue truncate>{prov.docker.image_id.replace("sha256:", "").slice(0, 19)}…</MonoValue>
                        <CopyButton value={prov.docker.image_id} label={t("image ID")} />
                      </span>
                    ) : (
                      "—"
                    ),
                  },
                  {
                    key: t("Container ID"),
                    value: prov.docker.container_id ? (
                      <span className="inline-flex items-center gap-1">
                        <MonoValue truncate>{prov.docker.container_id.slice(0, 12)}…</MonoValue>
                        <CopyButton value={prov.docker.container_id} label={t("container ID")} />
                      </span>
                    ) : (
                      "—"
                    ),
                  },
                  { key: t("Network mode"), value: prov.docker.network },
                  { key: t("CPU limit"), value: `${prov.docker.cpus}` },
                  { key: t("Memory limit"), value: `${prov.docker.memory_mb} MiB` },
                  { key: t("Exit code"), value: prov.exit_code === null ? "—" : String(prov.exit_code) },
                  { key: t("Execution status"), value: prov.status },
                  { key: t("Started"), value: formatTimestamp(prov.started_at, locale) },
                  { key: t("Finished"), value: formatTimestamp(prov.finished_at, locale) },
                  { key: t("Total runtime"), value: formatRuntime(prov.runtime_seconds) },
                  {
                    key: t("Training command"),
                    value: <span className="font-mono text-xs">{prov.training_command.join(" ")}</span>,
                  },
                ]}
              />
            )}
          </Panel>
        </section>
      </div>

      {/* Git provenance */}
      <section aria-label={t("Git provenance")}>
        <Panel title={t("Git provenance")}>
          {!prov ? (
            <p className="text-[13px] text-muted">{t("No Git provenance (fake executor).")}</p>
          ) : (
            <div className="space-y-4">
              <KeyValue
                columns={3}
                items={[
                  { key: t("Base commit"), value: <ShaValue sha={prov.git.base_commit_sha} /> },
                  { key: t("Baseline SHA after"), value: <ShaValue sha={prov.git.baseline_sha_after ?? ""} /> },
                  {
                    key: t("Baseline integrity"),
                    value:
                      prov.git.baseline_clean_after === true ? (
                        <span className="inline-flex items-center gap-1 text-[13px] font-medium text-success">
                          <CheckCircle2 className="size-3.5" aria-hidden="true" />
                          {t("clean after experiment")}</span>
                      ) : (
                        <span className="text-[13px] font-medium text-danger">{t("dirty")}</span>
                      ),
                  },
                  {
                    key: t("Worktree"),
                    value: <MonoValue truncate>{prov.git.worktree_identity}</MonoValue>,
                  },
                  {
                    key: t("Worktree path"),
                    value: <MonoValue truncate>{prov.git.worktree_path}</MonoValue>,
                  },
                  { key: t("Source hash (SHA-256)"), value: prov.source_sha256 ? (
                    <span className="inline-flex items-center gap-1">
                      <MonoValue truncate>{prov.source_sha256.slice(0, 16)}…</MonoValue>
                      <CopyButton value={prov.source_sha256} label={t("source hash")} />
                    </span>
                  ) : ("—") },
                ]}
              />
              <div>
                <p className="mb-2 text-xs font-medium text-muted">
                  {t("Experiment diff")}{" "}{prov.git.actual_git_diff ? "" : t("(none — baseline run)")}
                </p>
                <CodeDiff diff={prov.git.actual_git_diff} title="actual.diff" />
              </div>
            </div>
          )}
        </Panel>
      </section>

      {/* Artifacts */}
      {prov && (
        <section aria-label={t("Artifacts")}>
          <Panel title={t("Artifacts")}>
            <ul className="divide-y divide-line">
              <ArtifactRow name="stdout.log" path={prov.artifacts.stdout_path} url={artifactUrl(experiment.id, "stdout.log")} />
              <ArtifactRow name="stderr.log" path={prov.artifacts.stderr_path} url={artifactUrl(experiment.id, "stderr.log")} />
              <ArtifactRow name="metrics.json" path={prov.artifacts.metrics_path} url={artifactUrl(experiment.id, "metrics.json")} />
              <ArtifactRow name="provenance.json" path={prov.artifacts.provenance_path} url={artifactUrl(experiment.id, "provenance.json")} />
              <ArtifactRow name="patch.diff" path={prov.artifacts.patch_path} url={artifactUrl(experiment.id, "patch.diff")} />
              <ArtifactRow name="actual.diff" path={prov.artifacts.actual_diff_path} url={artifactUrl(experiment.id, "actual.diff")} />
            </ul>
          </Panel>
        </section>
      )}
    </div>
  );
}
