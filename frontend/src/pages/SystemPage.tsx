import { useI18n } from "@/i18n";
import { PageHeader } from "@/components/layout/PageHeader";
import { KeyValue, MonoValue, Panel } from "@/components/ui/primitives";

/** Runtime environment facts, mirroring the Phase 2 execution contract. */
export default function SystemPage() {
  const { t } = useI18n();
  return (
    <>
      <PageHeader
        title={t("System")}
        description={t("Runtime environment, persisted research state, and frontend API connection.")}
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title={t("Execution")}>
          <KeyValue
            columns={1}
            items={[
              { key: t("Executors"), value: t("fake (offline), docker (isolated MNIST and FashionMNIST)") },
              { key: t("Container filesystem"), value: t("read-only root + source") },
              { key: t("Network"), value: <MonoValue>none</MonoValue> },
              { key: t("Resource limits"), value: <MonoValue>{t("2 CPU · 2048 MiB · PID cap")}</MonoValue> },
              { key: t("Worktrees"), value: t("detached, UUID-named, cleanup verified") },
            ]}
          />
        </Panel>
        <Panel title={t("Persistence")}>
          <KeyValue
            columns={1}
            items={[
              { key: t("Store"), value: <MonoValue truncate>SQLite (.labpilot/labpilot.sqlite3)</MonoValue> },
              { key: t("State schema"), value: <MonoValue>schema_version 1</MonoValue> },
              { key: t("Checkpoints"), value: t("one revision per completed step") },
              { key: t("Resume"), value: t("from persisted next_step cursor") },
              { key: t("Artifacts"), value: t("stdout/stderr, metrics.json, provenance.json, diffs, source") },
            ]}
          />
        </Panel>
        <Panel title={t("Frontend data source")}>
          <KeyValue
            columns={1}
            items={[
              { key: t("Mode"), value: import.meta.env.VITE_LABPILOT_USE_MOCKS === "true" ? t("typed fixtures (mock)") : t("SQLite research API") },
              { key: t("Boundary"), value: <MonoValue truncate>src/services/labpilot-api.ts</MonoValue> },
              { key: t("Backend integration"), value: <MonoValue truncate>/api → labpilot serve-api</MonoValue> },
            ]}
          />
        </Panel>
        <Panel title={t("Loop phases")}>
          <KeyValue
            columns={1}
            items={[
              { key: t("Phase 2"), value: t("Git worktrees, Docker execution, real MNIST metrics") },
              { key: t("Phase 3"), value: t("Optuna hyperparameter optimization") },
              { key: t("Phase 4"), value: t("LLM hypothesis and patch generation") },
              { key: t("Phase 5"), value: t("arXiv / Semantic Scholar evidence grounding") },
              { key: t("Phase 6"), value: t("Snapshot reports and observational benchmarks") },
              { key: t("Phase 7"), value: t("Resumable multi-seed evaluations") },
              { key: t("Phase 8"), value: t("DeepSeek-assisted multi-seed campaigns") },
              { key: t("Phase 9"), value: t("FashionMNIST source-linked evaluation") },
              { key: t("Phase 10"), value: t("Next: datasets with different image shapes") },
            ]}
          />
        </Panel>
      </div>
    </>
  );
}
