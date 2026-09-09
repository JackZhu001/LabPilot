import { FileText } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge, EmptyState } from "@/components/ui/primitives";

export default function ReportsPage() {
  return (
    <>
      <PageHeader
        title="Reports"
        description="Generated research reports and phase verification write-ups."
        actions={<Badge variant="warning">Coming in Phase 6</Badge>}
      />
      <EmptyState
        icon={<FileText className="size-6" strokeWidth={1.5} />}
        title="Report generation is not implemented"
        description="LabPilot will compile measured results, decisions, and provenance into reproducible research reports. Benchmarks and evaluation are planned for Phase 6."
      />
    </>
  );
}
