import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

type DiffLine = {
  kind: "header" | "hunk" | "context" | "add" | "remove";
  text: string;
};

function parseDiff(diff: string): DiffLine[] {
  return diff.split("\n").filter(Boolean).map((line) => {
    if (line.startsWith("---") || line.startsWith("+++")) {
      return { kind: "header", text: line };
    }
    if (line.startsWith("@@")) return { kind: "hunk", text: line };
    if (line.startsWith("+")) return { kind: "add", text: line.slice(1) };
    if (line.startsWith("-")) return { kind: "remove", text: line.slice(1) };
    return { kind: "context", text: line.startsWith(" ") ? line.slice(1) : line };
  });
}

const lineClass: Record<DiffLine["kind"], string> = {
  header: "text-accent-ink bg-accent-soft/60",
  hunk: "text-accent-ink bg-accent-soft/30",
  context: "text-ink-2",
  add: "bg-success-soft text-success",
  remove: "bg-danger-soft text-danger",
};

const linePrefix: Record<DiffLine["kind"], string> = {
  header: "",
  hunk: "",
  context: " ",
  add: "+",
  remove: "-",
};

/** Readable unified-diff viewer with collapse for long diffs. */
export function CodeDiff({
  diff,
  collapsedLines = 12,
  className,
  title,
}: {
  diff: string;
  collapsedLines?: number;
  className?: string;
  title?: string;
}) {
  const lines = useMemo(() => parseDiff(diff), [diff]);
  const [expanded, setExpanded] = useState(false);
  const collapsible = lines.length > collapsedLines;
  const visible = expanded || !collapsible ? lines : lines.slice(0, collapsedLines);

  if (!diff.trim()) {
    return (
      <p className={cn("text-[13px] text-muted", className)}>
        No code changes were recorded for this execution.
      </p>
    );
  }

  return (
    <div className={cn("overflow-hidden rounded-[6px] border border-line bg-surface-2", className)}>
      {title && (
        <div className="border-b border-line bg-surface px-3 py-1.5 font-mono text-xs text-muted">
          {title}
        </div>
      )}
      <pre className="overflow-x-auto p-0 font-mono text-xs leading-5">
        <code>
          {visible.map((line, i) => (
            <span key={i} className={cn("block px-3", lineClass[line.kind])}>
              {linePrefix[line.kind]}
              {line.text || "\u00A0"}
            </span>
          ))}
        </code>
      </pre>
      {collapsible && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="flex w-full items-center gap-1.5 border-t border-line bg-surface px-3 py-1.5 text-xs font-medium text-accent-ink transition-colors hover:bg-surface-2"
        >
          {expanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
          {expanded ? "Collapse diff" : `Show full diff (${lines.length} lines)`}
        </button>
      )}
    </div>
  );
}
