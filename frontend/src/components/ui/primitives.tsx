import { useState, type ReactNode } from "react";
import { Check, Copy, Inbox } from "lucide-react";
import { cn, shortSha } from "@/lib/utils";

/* ---------- Panel ---------- */

export function Panel({
  title,
  actions,
  children,
  className,
  bodyClassName,
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section
      className={cn(
        "rounded-panel border border-line bg-surface",
        className,
      )}
    >
      {(title || actions) && (
        <header className="flex min-h-11 items-center justify-between gap-3 border-b border-line px-4 py-2">
          <h2 className="text-[13px] font-semibold tracking-wide text-ink">{title}</h2>
          {actions && <div className="flex items-center gap-1.5">{actions}</div>}
        </header>
      )}
      <div className={cn("p-4", bodyClassName)}>{children}</div>
    </section>
  );
}

/* ---------- Badge ---------- */

const badgeVariants = {
  neutral: "bg-neutral-soft text-ink-2 border-transparent",
  accent: "bg-accent-soft text-accent-ink border-transparent",
  success: "bg-success-soft text-success border-transparent",
  warning: "bg-warning-soft text-warning border-transparent",
  danger: "bg-danger-soft text-danger border-transparent",
  outline: "bg-transparent text-muted border-line-strong",
} as const;

export function Badge({
  variant = "neutral",
  icon,
  title,
  children,
  className,
}: {
  variant?: keyof typeof badgeVariants;
  icon?: ReactNode;
  title?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1 rounded-[4px] border px-1.5 py-px text-[11px] font-medium leading-4 tracking-wide whitespace-nowrap",
        badgeVariants[variant],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  );
}

/* ---------- Skeleton ---------- */

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded bg-surface-3", className)} />;
}

export function PanelSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="rounded-panel border border-line bg-surface">
      <div className="border-b border-line px-4 py-3">
        <Skeleton className="h-3.5 w-40" />
      </div>
      <div className="space-y-2.5 p-4">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className={cn("h-4", i % 3 === 2 ? "w-2/3" : "w-full")} />
        ))}
      </div>
    </div>
  );
}

export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="rounded-panel border border-line bg-surface">
      <div className="space-y-2.5 p-4">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-7 w-full" />
        ))}
      </div>
    </div>
  );
}

/* ---------- Empty state ---------- */

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode;
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-panel border border-dashed border-line-strong bg-surface-2/50 px-6 py-10 text-center",
        className,
      )}
    >
      <div className="text-faint" aria-hidden="true">
        {icon ?? <Inbox className="size-6" strokeWidth={1.5} />}
      </div>
      <p className="text-sm font-medium text-ink">{title}</p>
      <p className="max-w-[46ch] text-[13px] leading-relaxed text-muted">{description}</p>
      {action && <div className="mt-1.5">{action}</div>}
    </div>
  );
}

/* ---------- Error state ---------- */

export function ErrorState({
  title,
  message,
  onRetry,
}: {
  title: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="rounded-panel border border-danger/30 bg-danger-soft/40 px-4 py-3"
    >
      <p className="text-sm font-medium text-danger">{title}</p>
      <p className="mt-0.5 text-[13px] text-ink-2">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 rounded-[4px] border border-line-strong px-2 py-1 text-xs font-medium text-ink transition-colors hover:bg-surface-3"
        >
          Retry
        </button>
      )}
    </div>
  );
}

/* ---------- Copy button ---------- */

export function CopyButton({
  value,
  label,
  className,
}: {
  value: string;
  label?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      aria-label={`Copy ${label ?? "value"}`}
      title={`Copy ${label ?? "value"}: ${value}`}
      onClick={(e) => {
        e.stopPropagation();
        navigator.clipboard?.writeText(value).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        });
      }}
      className={cn(
        "inline-flex items-center gap-1 rounded p-0.5 text-faint transition-colors hover:bg-surface-3 hover:text-ink",
        className,
      )}
    >
      {copied ? (
        <Check className="size-3 text-success" aria-hidden="true" />
      ) : (
        <Copy className="size-3" aria-hidden="true" />
      )}
    </button>
  );
}

/* ---------- Mono value ---------- */

export function MonoValue({
  children,
  truncate,
  className,
}: {
  children: ReactNode;
  truncate?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "font-mono text-xs text-ink-2",
        truncate && "truncate",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function ShaValue({ sha, className }: { sha: string; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1", className)}>
      <MonoValue>{shortSha(sha)}</MonoValue>
      <CopyButton value={sha} label="commit SHA" />
    </span>
  );
}

/* ---------- Key/value grid ---------- */

export function KeyValue({
  items,
  columns = 2,
  className,
}: {
  items: { key: string; value: ReactNode }[];
  columns?: 1 | 2 | 3;
  className?: string;
}) {
  return (
    <dl
      className={cn(
        "grid gap-x-6 gap-y-0",
        columns === 1 && "grid-cols-1",
        columns === 2 && "grid-cols-1 sm:grid-cols-2",
        columns === 3 && "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3",
        className,
      )}
    >
      {items.map((item) => (
        <div
          key={item.key}
          className="flex items-baseline justify-between gap-4 border-b border-line/70 py-1.5 last:border-b-0"
        >
          <dt className="shrink-0 text-xs text-muted">{item.key}</dt>
          <dd className="min-w-0 truncate text-right text-[13px] font-medium text-ink">
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/* ---------- Section heading inside pages ---------- */

export function SectionTitle({ children, hint }: { children: ReactNode; hint?: string }) {
  return (
    <div className="mb-2.5 flex items-baseline gap-2">
      <h3 className="text-[13px] font-semibold tracking-wide text-ink">{children}</h3>
      {hint && <span className="text-xs text-faint">{hint}</span>}
    </div>
  );
}
