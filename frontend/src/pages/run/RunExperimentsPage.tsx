import { useOutletContext } from "react-router-dom";
import type { ResearchRun } from "@/types/domain";
import { ExperimentTable } from "@/components/research/ExperimentTable";

export default function RunExperimentsPage() {
  const { run } = useOutletContext<{ run: ResearchRun }>();
  return (
    <ExperimentTable
      experiments={run.experiments}
      to={(e) => `/runs/${run.research_id}/experiments/${e.id}`}
    />
  );
}
