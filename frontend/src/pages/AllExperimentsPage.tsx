import { useI18n } from "@/i18n";
import { Link } from "react-router-dom";
import { useRequest } from "@/hooks/useRequest";
import { getExperiments, getRuns } from "@/services/labpilot-api";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState, TableSkeleton } from "@/components/ui/primitives";
import { ExperimentTable } from "@/components/research/ExperimentTable";

/** All experiments across research runs. */
export default function AllExperimentsPage() {
  const { t } = useI18n();
  const { data: experiments, loading, error } = useRequest(() => getExperiments(), "experiments");
  const { data: runs } = useRequest(() => getRuns(), "runs");

  const goals = Object.fromEntries((runs ?? []).map((r) => [r.research_id, r.goal]));

  return (
    <>
      <PageHeader
        title={t("Experiments")}
        description={t("Every isolated execution across runs, with its measured metric, provenance, and decision outcome.")}
      />
      {loading ? (
        <TableSkeleton rows={6} />
      ) : error || !experiments ? (
        <EmptyState
          title={t("Experiments unavailable")}
          description={error?.message ?? t("Experiments could not be loaded.")}
        />
      ) : experiments.length === 0 ? (
        <EmptyState
          title={t("No experiments yet")}
          description={t("Experiments appear here once a research loop reaches the experiment step.")}
          action={
            <Link to="/runs" className="text-[13px] font-medium text-accent-ink hover:underline">
              {t("View research runs")}</Link>
          }
        />
      ) : (
        <ExperimentTable
          experiments={experiments}
          to={(e) => `/runs/${e.research_id}/experiments/${e.id}`}
          showResearch
          researchGoals={goals}
        />
      )}
    </>
  );
}
