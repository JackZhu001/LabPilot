import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatMetric(value: number | null | undefined, digits = 4): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(digits);
}

export function formatDelta(value: number | null | undefined, digits = 4): string {
  if (value === null || value === undefined) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}`;
}

/** Absolute metric delta expressed in percentage points, for tooltips/copy. */
export function deltaAsPercentagePoints(value: number): string {
  const pp = value * 100;
  const sign = pp > 0 ? "+" : "";
  const digits = Math.abs(pp) < 1 ? 2 : 2;
  return `${sign}${pp.toFixed(digits)} percentage points`;
}

export function formatRuntime(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)} ms`;
  if (seconds < 90) return `${seconds.toFixed(2)} s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

export function shortSha(sha: string, length = 7): string {
  return sha.length <= length ? sha : `${sha.slice(0, length)}…`;
}

export function shortId(id: string, length = 8): string {
  return `${id.slice(0, length)}…`;
}

const dateFmt = new Intl.DateTimeFormat("en", {
  month: "short",
  day: "numeric",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "UTC",
  hour12: false,
});

export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return "—";
  return `${dateFmt.format(new Date(iso))} UTC`;
}

export function formatClock(iso: string): string {
  return `${new Date(iso).toISOString().slice(11, 19)}Z`;
}
