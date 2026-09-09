import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  BookOpen,
  ChevronLeft,
  Cpu,
  FileText,
  FlaskConical,
  Gauge,
  Menu,
  Microscope,
  Settings,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/primitives";

function BrandMark({ collapsed }: { collapsed: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <span
        aria-hidden="true"
        className="flex size-7 shrink-0 items-center justify-center rounded-[7px] border border-line-strong bg-surface"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <rect x="0.75" y="0.75" width="12.5" height="12.5" rx="2.5" stroke="currentColor" strokeWidth="1.3" className="text-ink" />
          <circle cx="4.6" cy="4.6" r="1.15" className="fill-accent" />
          <circle cx="9.4" cy="4.6" r="1.15" className="fill-ink-2" />
          <circle cx="4.6" cy="9.4" r="1.15" className="fill-ink-2" />
          <circle cx="9.4" cy="9.4" r="1.15" className="fill-success" />
        </svg>
      </span>
      {!collapsed && (
        <span className="min-w-0">
          <span className="block text-[15px] font-semibold leading-tight tracking-tight text-ink">
            LabPilot
          </span>
          <span className="block truncate text-[10.5px] leading-tight text-faint">
            Autonomous ML Research Agent
          </span>
        </span>
      )}
    </span>
  );
}

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: Gauge },
  { to: "/runs", label: "Research Runs", icon: FlaskConical },
  { to: "/experiments", label: "Experiments", icon: Microscope },
  { to: "/evidence", label: "Evidence", icon: BookOpen, phase: "P5" },
  { to: "/reports", label: "Reports", icon: FileText, phase: "P6" },
];

const BOTTOM_NAV = [
  { to: "/system", label: "System", icon: Cpu },
  { to: "/settings", label: "Settings", icon: Settings },
];

function SidebarNav({
  collapsed,
  onNavigate,
}: {
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const link = (item: (typeof NAV)[number]) => (
    <NavLink
      key={item.to}
      to={item.to}
      onClick={onNavigate}
      title={collapsed ? item.label : undefined}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-2.5 rounded-[6px] px-2.5 py-1.5 text-[13px] font-medium transition-colors",
          isActive
            ? "bg-accent-soft text-accent-ink"
            : "text-ink-2 hover:bg-surface-3 hover:text-ink",
          collapsed && "justify-center px-0",
        )
      }
    >
      <item.icon className="size-4 shrink-0" strokeWidth={1.75} aria-hidden="true" />
      {!collapsed && <span className="truncate">{item.label}</span>}
      {!collapsed && item.phase && (
        <span className="ml-auto rounded-[3px] border border-line-strong px-1 text-[10px] font-medium text-faint">
          {item.phase}
        </span>
      )}
    </NavLink>
  );

  return (
    <>
      <nav aria-label="Primary" className="space-y-0.5">
        {NAV.map((item) => link(item))}
      </nav>
      <nav aria-label="System" className="mt-auto space-y-0.5">
        {BOTTOM_NAV.map((item) => link(item))}
      </nav>
    </>
  );
}

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex h-dvh overflow-hidden bg-bg">
      {/* Desktop sidebar */}
      <aside
        className={cn(
          "hidden shrink-0 flex-col gap-4 border-r border-line bg-surface px-3 py-3.5 transition-[width] lg:flex",
          collapsed ? "w-[56px]" : "w-[216px]",
        )}
      >
        <div className={cn("px-1", collapsed && "flex justify-center px-0")}>
          <BrandMark collapsed={collapsed} />
        </div>
        <SidebarNav collapsed={collapsed} />
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={cn(
            "flex items-center gap-1.5 rounded-[6px] border border-line px-2 py-1.5 text-[11px] font-medium text-muted transition-colors hover:bg-surface-2 hover:text-ink",
            collapsed && "justify-center",
          )}
        >
          <ChevronLeft className={cn("size-3.5 transition-transform", collapsed && "rotate-180")} aria-hidden="true" />
          {!collapsed && "Collapse"}
        </button>
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div
            className="absolute inset-0 bg-ink/20"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <aside className="absolute inset-y-0 left-0 flex w-[248px] flex-col gap-4 border-r border-line bg-surface px-3 py-3.5">
            <div className="flex items-center justify-between px-1">
              <BrandMark collapsed={false} />
              <button
                type="button"
                aria-label="Close navigation"
                onClick={() => setMobileOpen(false)}
                className="rounded p-1 text-muted hover:bg-surface-2 hover:text-ink"
              >
                <X className="size-4" />
              </button>
            </div>
            <SidebarNav collapsed={false} onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center gap-3 border-b border-line bg-surface px-4 lg:px-6">
          <button
            type="button"
            aria-label="Open navigation"
            onClick={() => setMobileOpen(true)}
            className="rounded p-1 text-muted hover:bg-surface-2 hover:text-ink lg:hidden"
          >
            <Menu className="size-4.5" />
          </button>
          <p className="truncate text-[13px] font-medium text-ink-2">
            Research control plane
          </p>
          <div className="ml-auto flex items-center gap-2">
            <Badge variant="outline" title="This frontend runs on typed fixture data; backend integration is planned">
              fixture data
            </Badge>
            <span className="hidden font-mono text-[11px] text-faint sm:block">v0.2.0 · phase 2</span>
          </div>
        </header>
        <main className="min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1200px] px-4 py-5 lg:px-6 lg:py-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
