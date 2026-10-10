"use client";

import { DecisionGlyph } from "@/components/artwork/StatusGlyphs";
import { cn } from "@/lib/utils";
import type { DecisionState, EventCategory, RiskOutcome } from "@/types/domain";
import { DECISION_META } from "@/lib/format";

const DECISION_TONE: Record<DecisionState, string> = {
  PROCEED: "bg-forest text-paper border-ink",
  REDUCE: "bg-warn text-paper border-ink",
  WAIT: "bg-ink text-paper border-ink",
  REJECT: "bg-risk text-paper border-ink",
  "NO ACTION": "bg-hold text-paper border-ink",
};

const RISK_TONE: Record<RiskOutcome, { cls: string; label: string }> = {
  APPROVED: { cls: "bg-forest-mist text-forest-deep border-forest", label: "Approved" },
  REDUCED: { cls: "bg-warn-soft text-warn border-ink", label: "Reduced" },
  REFUSED: { cls: "bg-risk-soft text-risk border-ink", label: "Refused" },
};

const CATEGORY_META: Record<EventCategory, { label: string; icon: string }> = {
  EARNINGS: { label: "Earnings", icon: "📈" },
  FILING: { label: "Filing", icon: "📄" },
  HEADLINE: { label: "Headline", icon: "🗞️" },
  MACRO: { label: "Macro", icon: "🌍" },
  REFERENCE_GAP: { label: "Reference gap", icon: "⚖️" },
  MARKET: { label: "Market data", icon: "📒" },
};

/** No emoji — tiny SVG category glyph instead. */
function CategoryGlyph({ kind }: { kind: EventCategory }) {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true" className="shrink-0">
      {kind === "EARNINGS" && (
        <g stroke="currentColor" strokeWidth="1.9" fill="none" strokeLinecap="round" strokeLinejoin="round">
          <path d="M2.5 12.5 6 8.5l3 2.6 4.5-6" />
          <path d="M10.5 5h3v3" />
        </g>
      )}
      {kind === "FILING" && (
        <g stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinejoin="round">
          <path d="M3 2 h7 l3 3 v9 H3 Z" />
          <path d="M10 2 v3 h3" />
        </g>
      )}
      {kind === "HEADLINE" && (
        <g stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinejoin="round" strokeLinecap="round">
          <rect x="2.5" y="3.5" width="11" height="9" rx="1.5" />
          <path d="M5 6.5 h6 M5 9 h4" />
        </g>
      )}
      {kind === "MACRO" && (
        <g stroke="currentColor" strokeWidth="1.7" fill="none">
          <circle cx="8" cy="8" r="5.5" />
          <path d="M2.5 8 h11 M8 2.5 c2.5 2.8 2.5 8.2 0 11 c-2.5-2.8-2.5-8.2 0-11" />
        </g>
      )}
      {kind === "REFERENCE_GAP" && (
        <g stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round">
          <path d="M3 6.5 h6" />
          <path d="M9 4.5 l2.5 2 -2.5 2" transform="translate(-1 0)" />
          <path d="M3 10.5 h4" />
          <path d="M11 9 l2 1.5 -2 1.5" />
        </g>
      )}
    </svg>
  );
}

export function DecisionBadge({
  state,
  size = "md",
  className,
}: {
  state: DecisionState;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border-2 font-bold uppercase tracking-wide",
        DECISION_TONE[state],
        size === "sm" && "px-2 py-0.5 text-[10px]",
        size === "md" && "px-2.5 py-1 text-xs",
        size === "lg" && "px-3.5 py-1.5 text-sm",
        className
      )}
    >
      <DecisionGlyph state={state} size={size === "lg" ? 18 : 14} />
      {DECISION_META[state].label}
    </span>
  );
}

export function RiskOutcomeBadge({ outcome }: { outcome: RiskOutcome }) {
  const t = RISK_TONE[outcome];
  return (
    <span className={cn("inline-flex items-center rounded-full border-2 px-2.5 py-1 text-xs font-bold", t.cls)}>
      {t.label}
    </span>
  );
}

export function CategoryBadge({ category }: { category: EventCategory }) {
  void CATEGORY_META;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-line-strong bg-paper px-2.5 py-1 text-[11px] font-bold text-ink-soft">
      <CategoryGlyph kind={category} />
      {CATEGORY_META[category].label}
    </span>
  );
}

/** Evidence completeness meter — always paired with a numeric label. */
export function CompletenessMeter({
  value,
  threshold = 0.9,
  className,
}: {
  value: number;
  threshold?: number;
  className?: string;
}) {
  const pct = Math.round(value * 100);
  const below = value < threshold;
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span
        className="relative block h-2 w-20 overflow-hidden rounded-full border border-ink/60 bg-warmwhite"
        role="meter"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Evidence completeness ${pct} percent`}
      >
        <span
          className={cn("absolute inset-y-0 left-0 rounded-full", below ? "bg-warn" : "bg-forest")}
          style={{ width: `${pct}%` }}
        />
        <span
          className="absolute inset-y-0 w-[2px] bg-ink/70"
          style={{ left: `${threshold * 100}%` }}
          aria-hidden="true"
        />
      </span>
      <span className={cn("tnum text-[11px] font-bold", below ? "text-warn" : "text-forest")}>
        {pct}%
      </span>
    </span>
  );
}
