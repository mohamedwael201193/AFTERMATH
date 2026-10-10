import { cn } from "@/lib/utils";
import type { DecisionState, RiskCheckStatus } from "@/types/domain";

/**
 * Status glyph system for decision states and risk checks.
 * Never color-only: every state also carries a text label at render time.
 */

const STATE_STYLE: Record<
  DecisionState,
  { bg: string; fg: string; label: string }
> = {
  PROCEED: { bg: "#086B32", fg: "#F5F2E7", label: "Proceed" },
  REDUCE: { bg: "#9A6106", fg: "#F5F2E7", label: "Reduce" },
  WAIT: { bg: "#171916", fg: "#F5F2E7", label: "Wait" },
  REJECT: { bg: "#B3261E", fg: "#F5F2E7", label: "Reject" },
  "NO ACTION": { bg: "#65695F", fg: "#F5F2E7", label: "No action" },
};

export function DecisionGlyph({
  state,
  size = 24,
  className,
}: {
  state: DecisionState;
  size?: number;
  className?: string;
}) {
  const s = STATE_STYLE[state];
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    role: "img" as const,
    "aria-label": `${s.label} status icon`,
    className,
  };
  const stroke = { stroke: s.fg, strokeWidth: 2.4, fill: "none", strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

  return (
    <svg {...common}>
      <circle cx="12" cy="12" r="10.5" fill={s.bg} stroke="#171916" strokeWidth="1.8" />
      {state === "PROCEED" && (
        <g {...stroke}>
          <path d="M12 16.5 V8" />
          <path d="M8.6 11.2 12 7.8l3.4 3.4" />
        </g>
      )}
      {state === "REDUCE" && (
        <g {...stroke}>
          <path d="M12 7.5 v5.5" />
          <path d="M8.8 10.2 12 13.4l3.2-3.2" />
          <path d="M8.2 16.8 h7.6" />
        </g>
      )}
      {state === "WAIT" && (
        <g {...stroke}>
          <circle cx="12" cy="12" r="5.6" />
          <path d="M12 9.2 V12l2.2 1.6" />
        </g>
      )}
      {state === "REJECT" && (
        <g {...stroke}>
          <path d="M8.8 8.8 l6.4 6.4" />
          <path d="M15.2 8.8 l-6.4 6.4" />
        </g>
      )}
      {state === "NO ACTION" && (
        <g {...stroke}>
          <path d="M8.4 12 h7.2" />
        </g>
      )}
    </svg>
  );
}

/* ── risk check status marks ────────────────────────────────── */

const RISK_STYLE: Record<RiskCheckStatus, { bg: string; fg: string; label: string }> = {
  PASS: { bg: "#086B32", fg: "#F5F2E7", label: "Pass" },
  WARN: { bg: "#C9A227", fg: "#171916", label: "Caution" },
  FAIL: { bg: "#B3261E", fg: "#F5F2E7", label: "Block" },
};

export function RiskMark({
  status,
  size = 20,
  className,
}: {
  status: RiskCheckStatus;
  size?: number;
  className?: string;
}) {
  const s = RISK_STYLE[status];
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      role="img"
      aria-label={`${s.label} check result`}
      className={cn("shrink-0", className)}
    >
      <circle cx="12" cy="12" r="10.5" fill={s.bg} stroke="#171916" strokeWidth="1.8" />
      {status === "PASS" && (
        <path d="M7.8 12.4 l2.8 2.9 5.4-6.6" stroke={s.fg} strokeWidth="2.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      )}
      {status === "WARN" && (
        <g stroke={s.fg} strokeWidth="2.4" fill="none" strokeLinecap="round">
          <path d="M12 7.6 v5" />
          <circle cx="12" cy="16.2" r="0.4" fill={s.fg} />
        </g>
      )}
      {status === "FAIL" && (
        <g stroke={s.fg} strokeWidth="2.6" fill="none" strokeLinecap="round">
          <path d="M12 7.8 v4.6" />
          <circle cx="12" cy="16" r="0.5" fill={s.fg} />
        </g>
      )}
    </svg>
  );
}

export function FreshnessDot({
  freshness,
  className,
}: {
  freshness: "FRESH" | "AGING" | "STALE";
  className?: string;
}) {
  const color =
    freshness === "FRESH" ? "#086B32" : freshness === "AGING" ? "#C9A227" : "#B3261E";
  return (
    <span className={cn("relative inline-flex", className)} aria-hidden="true">
      <span className="absolute inset-0 rounded-full animate-pulse-ring" style={{ background: color, opacity: 0.4 }} />
      <span className="relative inline-block h-2.5 w-2.5 rounded-full border-2 border-ink" style={{ background: color }} />
    </span>
  );
}
