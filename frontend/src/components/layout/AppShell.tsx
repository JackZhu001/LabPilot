import { useI18n } from "@/i18n";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
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
  Sun,
  Moon,
  Languages,
  Pause,
  Play,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/primitives";

function BrandMark({ collapsed }: { collapsed: boolean }) {
  const { t } = useI18n();
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
            {t("Autonomous ML Research Agent")}</span>
        </span>
      )}
    </span>
  );
}

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: Gauge },
  { to: "/runs", label: "Research Runs", icon: FlaskConical },
  { to: "/experiments", label: "Experiments", icon: Microscope },
  { to: "/evidence", label: "Evidence", icon: BookOpen },
  { to: "/reports", label: "Reports", icon: FileText },
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
  const { t } = useI18n();
  const link = (item: (typeof NAV)[number]) => (
    <NavLink
      key={item.to}
      to={item.to}
      onClick={onNavigate}
      title={collapsed ? t(item.label) : undefined}
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
      {!collapsed && <span className="truncate">{t(item.label)}</span>}

    </NavLink>
  );

  return (
    <>
      <nav aria-label={t("Primary")} className="space-y-0.5">
        {NAV.map((item) => link(item))}
      </nav>
      <nav aria-label={t("System")} className="mt-auto space-y-0.5">
        {BOTTOM_NAV.map((item) => link(item))}
      </nav>
    </>
  );
}

export function AppShell() {
  const { t, locale, setLocale } = useI18n();
  const location = useLocation();
  const [motion, setMotion] = useState(() => {
    try { return localStorage.getItem("labpilot-motion") !== "off"; } catch { return true; }
  });
  useEffect(() => {
    document.documentElement.dataset.motion = motion ? "on" : "off";
    try { localStorage.setItem("labpilot-motion", motion ? "on" : "off"); } catch { /* Storage is optional. */ }
  }, [motion]);
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem("labpilot-theme") ?? "dark"; } catch { return "dark"; }
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("labpilot-theme", theme); } catch { /* Storage is optional. */ }
  }, [theme]);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex h-dvh overflow-hidden bg-bg">
      {/* Desktop sidebar */}
      <aside
        className={cn(
          "app-sidebar hidden shrink-0 flex-col gap-4 border-r border-line px-4 py-7 transition-[width] lg:flex",
          collapsed ? "w-[72px]" : "w-[232px]",
        )}
      >
        <div className={cn("px-1", collapsed && "flex justify-center px-0")}>
          <BrandMark collapsed={collapsed} />
        </div>
        <SidebarNav collapsed={collapsed} />
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          aria-label={collapsed ? t("Expand sidebar") : t("Collapse sidebar")}
          className={cn(
            "flex items-center gap-1.5 rounded-[6px] border border-line px-2 py-1.5 text-[11px] font-medium text-muted transition-colors hover:bg-surface-2 hover:text-ink",
            collapsed && "justify-center",
          )}
        >
          <ChevronLeft className={cn("size-3.5 transition-transform", collapsed && "rotate-180")} aria-hidden="true" />
          {!collapsed && t("Collapse")}
        </button>
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label={t("Navigation")}>
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
                aria-label={t("Close navigation")}
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
        <header className="app-topbar flex h-16 shrink-0 items-center gap-3 border-b border-line px-5 lg:px-10">
          <button
            type="button"
            aria-label={t("Open navigation")}
            onClick={() => setMobileOpen(true)}
            className="rounded p-1 text-muted hover:bg-surface-2 hover:text-ink lg:hidden"
          >
            <Menu className="size-4.5" />
          </button>
          <p className="truncate text-[13px] font-medium text-ink-2">
            {t("Workspace / Research")}</p>
          <div className="ml-auto flex items-center gap-1 sm:gap-3">
            <button type="button" className="header-control" aria-label={locale === "zh" ? "Switch to English" : "切换为中文"} onClick={() => setLocale(locale === "zh" ? "en" : "zh")}>
              <Languages size={16} /><span>{locale === "zh" ? "EN" : "中文"}</span>
            </button>
            <button type="button" className="header-control" aria-label={t(motion ? "Pause all animations" : "Enable animations")} aria-pressed={!motion} onClick={() => setMotion(!motion)}>
              {motion ? <Pause size={16} /> : <Play size={16} />}
            </button>
            <button type="button" className="header-control" aria-label={t(theme === "dark" ? "Switch to light theme" : "Switch to dark theme")} onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
              {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <Badge variant="outline" title={import.meta.env.VITE_LABPILOT_USE_MOCKS === "true" ? t("Typed fixture data") : t("SQLite research API")}>
              {import.meta.env.VITE_LABPILOT_USE_MOCKS === "true" ? t("fixture data") : t("live data")}
            </Badge>
          </div>
        </header>
        <main className="min-w-0 flex-1 overflow-y-auto">
          <div key={location.pathname} className="page-content mx-auto w-full max-w-[1440px] px-5 py-7 lg:px-10 lg:py-9">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
