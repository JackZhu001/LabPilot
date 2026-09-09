import { useOutletContext } from "react-router-dom";
import type { ResearchRun } from "@/types/domain";
import { MonoValue, Panel, EmptyState } from "@/components/ui/primitives";
import { RelationBadge } from "@/components/ui/badges";

/**
 * Evidence tab: the paper → claim → evidence → hypothesis chain recorded in
 * the run state. Literature retrieval is not implemented (Phase 5); current
 * runs carry explicit fixture literature.
 */
export default function RunEvidencePage() {
  const { run } = useOutletContext<{ run: ResearchRun }>();
  const hasChain = run.papers.length > 0;

  return (
    <div className="space-y-4">
      {!hasChain ? (
        <EmptyState
          title="No literature recorded"
          description="This run has no papers, claims, or evidence in its state. Literature grounding arrives in Phase 5."
        />
      ) : (
        <>
          <Panel title="Literature chain" bodyClassName="p-4">
            <ol className="space-y-4">
              {run.papers.map((paper) => (
                <li key={paper.id} className="rounded-[6px] border border-line bg-surface-2 px-3.5 py-3">
                  {/* Paper */}
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <p className="text-[13px] font-semibold text-ink">{paper.title}</p>
                    <MonoValue className="text-faint">{paper.source_provider}</MonoValue>
                  </div>
                  <p className="mt-0.5 text-xs text-muted">
                    {paper.authors.join(", ")}
                    {paper.published_at && ` · ${paper.published_at}`}
                  </p>
                  {paper.url && (
                    <a
                      href={paper.url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-0.5 inline-block font-mono text-[11px] text-accent-ink underline-offset-2 hover:underline"
                    >
                      {paper.url}
                    </a>
                  )}

                  {/* Claims + evidence */}
                  <div className="mt-3 space-y-3 border-t border-line pt-3">
                    {run.claims
                      .filter((c) => c.paper_id === paper.id)
                      .map((claim) => (
                        <div key={claim.id}>
                          <p className="text-[13px] leading-relaxed text-ink-2">
                            <span className="mr-1.5 rounded-[3px] border border-line-strong px-1 text-[10px] font-semibold tracking-wide text-faint">
                              CLAIM
                            </span>
                            {claim.statement}
                            <span className="ml-2 font-mono text-[11px] text-faint">
                              confidence {claim.confidence}
                            </span>
                          </p>
                          <ul className="mt-2 space-y-1.5">
                            {run.evidence
                              .filter((ev) => ev.claim_id === claim.id)
                              .map((ev) => (
                                <li
                                  key={ev.id}
                                  className="flex flex-wrap items-baseline gap-2 rounded-[5px] bg-surface px-2.5 py-1.5"
                                >
                                  <RelationBadge relation={ev.relation} />
                                  <span className="text-xs leading-relaxed text-ink-2">{ev.summary}</span>
                                  <span className="ml-auto font-mono text-[11px] text-faint">
                                    confidence {ev.confidence}
                                  </span>
                                </li>
                              ))}
                          </ul>
                        </div>
                      ))}
                  </div>
                </li>
              ))}
            </ol>
          </Panel>

          {/* Linked hypotheses */}
          <Panel title="Linked hypotheses">
            <ul className="space-y-2.5">
              {run.hypotheses.map((h) => (
                <li key={h.id} className="rounded-[6px] border border-line bg-surface-2 px-3.5 py-3">
                  <p className="text-[13px] font-medium leading-relaxed text-ink">{h.statement}</p>
                  <p className="mt-1 font-mono text-[11px] text-faint">
                    evidence linked via state provenance · status {h.status} · expected {h.expected_effect}
                  </p>
                </li>
              ))}
            </ul>
          </Panel>
        </>
      )}
    </div>
  );
}
