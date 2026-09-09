import { Link } from "react-router-dom";
import {
  CheckCircle2,
  GitBranch,
  RotateCcw,
  Scale,
  Timer,
  TrendingUp,
} from "lucide-react";
import type { ActivityEvent, ActivityKind } from "@/types/domain";
import { formatTimestamp } from "@/lib/utils";

const kindMeta: Record<ActivityKind, { icon: typeof CheckCircle2; className: string }> = {
  baseline_completed: { icon: CheckCircle2, className: "text-success bg-success-soft" },
  patch_applied: { icon: GitBranch, className: "text-accent-ink bg-accent-soft" },
  docker_run: { icon: Timer, className: "text-accent-ink bg-accent-soft" },
  metric_collected: { icon: TrendingUp, className: "text-ink-2 bg-neutral-soft" },
  decision: { icon: Scale, className: "text-ink-2 bg-neutral-soft" },
  checkpoint: { icon: CheckCircle2, className: "text-ink-2 bg-neutral-soft" },
  hpo_trial: { icon: TrendingUp, className: "text-accent-ink bg-accent-soft" },
  replan: { icon: RotateCcw, className: "text-warning bg-warning-soft" },
};

/** Autonomous research timeline — loop checkpoints, not a chat transcript. */
export function ActivityTimeline({
  events,
  showRunLink = false,
}: {
  events: ActivityEvent[];
  showRunLink?: boolean;
}) {
  if (events.length === 0) {
    return (
      <p className="text-[13px] text-muted">No activity recorded yet.</p>
    );
  }
  return (
    <ol className="relative space-y-0">
      {events.map((event, i) => {
        const meta = kindMeta[event.kind];
        const Icon = meta.icon;
        return (
          <li key={event.id} className="relative flex gap-3 pb-4 last:pb-0">
            {i < events.length - 1 && (
              <span aria-hidden="true" className="absolute top-7 bottom-0 left-[11px] w-px bg-line" />
            )}
            <span
              className={`mt-0.5 flex size-[23px] shrink-0 items-center justify-center rounded-full ${meta.className}`}
            >
              <Icon className="size-3" strokeWidth={2} aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <p className="text-[13px] font-medium text-ink">{event.title}</p>
                <time className="font-mono text-[11px] text-faint" dateTime={event.at}>
                  {formatTimestamp(event.at)}
                </time>
              </div>
              {event.detail && (
                <p className="mt-0.5 text-xs leading-relaxed text-muted">{event.detail}</p>
              )}
              {showRunLink && (
                <Link
                  to={`/runs/${event.research_id}`}
                  className="mt-1 inline-block text-xs font-medium text-accent-ink underline-offset-2 hover:underline"
                >
                  View run
                </Link>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
