import { PageHeader } from "@/components/layout/PageHeader";
import { KeyValue, MonoValue, Panel } from "@/components/ui/primitives";

/** Runtime environment facts, mirroring the Phase 2 execution contract. */
export default function SystemPage() {
  return (
    <>
      <PageHeader
        title="System"
        description="Execution environment and persistence contract. Values reflect the Phase 2 backend; this frontend currently serves typed fixture data."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Execution">
          <KeyValue
            columns={1}
            items={[
              { key: "Executors", value: "fake (offline), docker (isolated MNIST)" },
              { key: "Container filesystem", value: "read-only root + source" },
              { key: "Network", value: <MonoValue>none</MonoValue> },
              { key: "Resource limits", value: <MonoValue>2 CPU · 2048 MiB · PID cap</MonoValue> },
              { key: "Worktrees", value: "detached, UUID-named, cleanup verified" },
            ]}
          />
        </Panel>
        <Panel title="Persistence">
          <KeyValue
            columns={1}
            items={[
              { key: "Store", value: <MonoValue truncate>SQLite (.labpilot/labpilot.sqlite3)</MonoValue> },
              { key: "State schema", value: <MonoValue>schema_version 1</MonoValue> },
              { key: "Checkpoints", value: "one revision per completed step" },
              { key: "Resume", value: "from persisted next_step cursor" },
              { key: "Artifacts", value: "stdout/stderr, metrics.json, provenance.json, diffs, source" },
            ]}
          />
        </Panel>
        <Panel title="Frontend data source">
          <KeyValue
            columns={1}
            items={[
              { key: "Mode", value: "typed fixtures (mock)" },
              { key: "Boundary", value: <MonoValue truncate>src/services/labpilot-api.ts</MonoValue> },
              { key: "Backend integration", value: "planned — HTTP adapter behind the same API" },
            ]}
          />
        </Panel>
        <Panel title="Loop phases">
          <KeyValue
            columns={1}
            items={[
              { key: "Phase 2 (current)", value: "Git worktrees, Docker execution, real MNIST metrics" },
              { key: "Phase 3", value: "Optuna hyperparameter optimization (in development)" },
              { key: "Phase 4", value: "LLM hypothesis and patch generation" },
              { key: "Phase 5", value: "arXiv / Semantic Scholar evidence grounding" },
            ]}
          />
        </Panel>
      </div>
    </>
  );
}
