import { BookOpen } from "lucide-react";
import { Link } from "react-router-dom";
import { useRequest } from "@/hooks/useRequest";
import { getAllRuns } from "@/services/labpilot-api";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge, EmptyState, MonoValue, Panel } from "@/components/ui/primitives";
import { RelationBadge } from "@/components/ui/badges";

/**
 * Evidence: future preview. The Paper → Claim → Evidence → Hypothesis model
 * exists in the backend (Phase 1 fixtures), but real literature retrieval
 * (arXiv / Semantic Scholar) is Phase 5. This page previews the intended
 * relationship UI using fixture data from completed runs.
 */
export default function EvidencePreviewPage() {
  const { data: runs } = useRequest(() => getAllRuns(), "all-runs");
  const chains = (runs ?? []).filter((r) => r.papers.length > 0);

  return (
    <>
      <PageHeader
        title="Evidence"
        description="Paper → Claim → Evidence → Hypothesis grounding for research decisions."
        actions={
          <Badge variant="warning" title="Real literature retrieval is not implemented yet">
            Coming in Phase 5
          </Badge>
        }
      />

      <p className="mb-4 max-w-[75ch] text-[13px] leading-relaxed text-muted">
        This preview renders the literature chain already persisted in research states. Automated
        arXiv and Semantic Scholar retrieval, claim extraction, and evidence ranking are planned
        for Phase 5 — nothing here implies they are running.
      </p>

      {chains.length === 0 ? (
        <EmptyState
          icon={<BookOpen className="size-6" strokeWidth={1.5} />}
          title="No evidence yet"
          description="Research runs record their literature chain here once hypotheses are grounded in evidence."
        />
      ) : (
        <div className="space-y-4">
          {chains.map((run) => (
            <Panel
              key={run.research_id}
              title={
                <Link
                  to={`/runs/${run.research_id}/evidence`}
                  className="hover:text-accent-ink hover:underline"
                >
                  {run.goal}
                </Link>
              }
              bodyClassName="p-4"
            >
              <ol className="space-y-3">
                {run.claims.map((claim) => {
                  const evidence = run.evidence.filter((ev) => ev.claim_id === claim.id);
                  return (
                    <li key={claim.id} className="rounded-[6px] border border-line bg-surface-2 px-3.5 py-3">
                      <p className="text-[13px] font-medium leading-relaxed text-ink">{claim.statement}</p>
                      <ul className="mt-2 space-y-1.5">
                        {evidence.map((ev) => (
                          <li key={ev.id} className="flex flex-wrap items-baseline gap-2">
                            <RelationBadge relation={ev.relation} />
                            <span className="text-xs text-ink-2">{ev.summary}</span>
                            <span className="ml-auto font-mono text-[11px] text-faint">
                              confidence {ev.confidence}
                            </span>
                          </li>
                        ))}
                      </ul>
                      <p className="mt-2 border-t border-line pt-2 font-mono text-[11px] text-faint">
                        claim {claim.id.slice(0, 8)}… · paper {claim.paper_id.slice(0, 8)}…
                      </p>
                    </li>
                  );
                })}
              </ol>
              <p className="mt-3 text-xs text-muted">
                Linked to{" "}
                <MonoValue>{run.hypotheses.length}</MonoValue> hypothesis record(s) in the run
                state.
              </p>
            </Panel>
          ))}
        </div>
      )}
    </>
  );
}
