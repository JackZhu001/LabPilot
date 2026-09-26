import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Page title block: title, description, and meta badges/actions row. */
export function PageHeader({
  title,
  description,
  meta,
  actions,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-8", className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-3xl font-medium tracking-tight text-ink">{title}</h1>
          {description && (
            <p className="mt-3 max-w-[70ch] text-sm leading-relaxed text-muted">
              {description}
            </p>
          )}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
      {meta && <div className="mt-3 flex flex-wrap items-center gap-2">{meta}</div>}
    </div>
  );
}
