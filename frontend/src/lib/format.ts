import type { DecisionState, Freshness, RiskCheckStatus } from "@/types/domain";

/**
 * Shared formatting and display helpers.
 * Presentation components use these so names, statuses, and numbers stay
 * consistent across the whole application.
 */

/* ── decision states ──────────────────────────────────────────── */

export const DECISION_META: Record<
  DecisionState,
  { label: string; plain: string; tone: "proceed" | "reduce" | "wait" | "reject" | "none" }
> = {
  PROCEED: {
    label: "PROCEED",
    plain: "Evidence is sufficient — a paper trade was executed.",
    tone: "proceed",
  },
  REDUCE: {
    label: "REDUCE",
    plain: "Evidence supports a trade, but only at a smaller size.",
    tone: "reduce",
  },
  WAIT: {
    label: "WAIT",
    plain: "Acting now would mean guessing — the system is waiting for better data.",
    tone: "wait",
  },
  REJECT: {
    label: "REJECT",
    plain: "The evidence does not support a trade. Refusal is the correct outcome.",
    tone: "reject",
  },
  "NO ACTION": {
    label: "NO ACTION",
    plain: "Nothing to trade — and the reason why is recorded.",
    tone: "none",
  },
};

/* ── freshness ────────────────────────────────────────────────── */

export const FRESHNESS_LABELS: Record<Freshness, string> = {
  FRESH: "Fresh",
  AGING: "Aging",
  STALE: "Stale",
};

/* ── risk checks ──────────────────────────────────────────────── */

export const RISK_STATUS_LABELS: Record<RiskCheckStatus, string> = {
  PASS: "Pass",
  WARN: "Caution",
  FAIL: "Block",
};

/* ── numbers ──────────────────────────────────────────────────── */

export function formatUsd(value: number, opts?: { compact?: boolean }): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: opts?.compact ? "compact" : "standard",
    maximumFractionDigits: opts?.compact ? 1 : 2,
    minimumFractionDigits: opts?.compact ? 0 : 2,
  }).format(value);
}

export function formatPct(value: number, withSign = true): string {
  const sign = withSign && value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)} %`;
}

export function formatConfidence(value: number): string {
  return `${Math.round(value * 100)} %`;
}

/* ── time ─────────────────────────────────────────────────────── */

const ET_TIMEZONE = "America/New_York";

/** All preview timestamps render in US Eastern (the market's clock). */
export function formatEt(iso: string, style: "clock" | "full" | "compact" = "clock"): string {
  const d = new Date(iso);
  if (style === "compact") {
    return new Intl.DateTimeFormat("en-US", {
      timeZone: ET_TIMEZONE,
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    }).format(d);
  }
  return new Intl.DateTimeFormat("en-US", {
    timeZone: ET_TIMEZONE,
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    ...(style === "full"
      ? { weekday: "short", month: "short", day: "numeric" }
      : {}),
  }).format(d);
}

export function formatEtDate(iso: string): string {
  const d = new Date(iso);
  return new Intl.DateTimeFormat("en-US", {
    timeZone: ET_TIMEZONE,
    month: "short",
    day: "numeric",
  }).format(d);
}

export function minutesAgo(iso: string, anchorIso: string): number {
  return Math.max(0, Math.round((Date.parse(anchorIso) - Date.parse(iso)) / 60000));
}

export function relativeToNow(iso: string): string {
  return relativeLabel(iso, new Date().toISOString());
}

export function relativeLabel(iso: string, anchorIso: string): string {
  const mins = minutesAgo(iso, anchorIso);
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} h ${mins % 60} min ago`;
  const days = Math.floor(hours / 24);
  return `${days} d ago`;
}

/* ── misc ─────────────────────────────────────────────────────── */

export function truncateMiddle(s: string, head = 4, tail = 4): string {
  if (s.length <= head + tail + 1) return s;
  return `${s.slice(0, head)}…${s.slice(-tail)}`;
}
