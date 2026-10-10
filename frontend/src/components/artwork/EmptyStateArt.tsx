import { cn } from "@/lib/utils";

/**
 * Empty-state artwork — a friendly document character searching for
 * evidence that is not there yet. Same visual family as the hero sentinel.
 */
export function EmptyStateArt({
  className,
  width = 200,
}: {
  className?: string;
  width?: number;
}) {
  return (
    <svg
      width={width}
      height={width * 0.72}
      viewBox="0 0 220 160"
      role="img"
      aria-label="A document character searching for missing evidence"
      className={className}
    >
      {/* dashed empty boxes */}
      <g fill="none" stroke="#B9B9A6" strokeWidth="2.4" strokeDasharray="5 6" strokeLinejoin="round">
        <rect x="14" y="24" width="34" height="42" rx="6" />
        <rect x="172" y="34" width="34" height="42" rx="6" />
      </g>
      {/* question marks */}
      <g fill="#65695F" style={{ fontFamily: "var(--font-display)" }}>
        <text x="26" y="18" fontSize="15">?</text>
        <text x="188" y="28" fontSize="12">?</text>
        <text x="150" y="14" fontSize="10">?</text>
      </g>
      {/* document body */}
      <path
        d="M62 26 h84 l14 14 v76 h-98 Z"
        fill="#FFFEF8"
        stroke="#171916"
        strokeWidth="3.4"
        strokeLinejoin="round"
      />
      <path d="M146 26 v14 h14" fill="none" stroke="#171916" strokeWidth="3.4" strokeLinejoin="round" />
      {/* face */}
      <g>
        <circle cx="92" cy="60" r="3" fill="#171916" />
        <circle cx="116" cy="60" r="3" fill="#171916" />
        <path d="M96 70 q8 -5 16 0" fill="none" stroke="#171916" strokeWidth="2.6" strokeLinecap="round" />
      </g>
      {/* body lines */}
      <path d="M76 84 h56 M76 94 h40" stroke="#65695F" strokeWidth="2.6" strokeLinecap="round" />
      {/* magnifying glass */}
      <circle cx="152" cy="104" r="22" fill="#F5F2E7" fillOpacity="0.55" stroke="#171916" strokeWidth="3.4" />
      <circle cx="152" cy="104" r="22" fill="none" stroke="#086B32" strokeWidth="3.4" opacity="0.35" />
      <path d="M167.5 119.5 l14 14" stroke="#171916" strokeWidth="6.5" strokeLinecap="round" />
      <path d="M145 96 l4.5 5 8-10" stroke="#086B32" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      {/* legs */}
      <path d="M84 116 v18 M136 116 v18" stroke="#171916" strokeWidth="3.4" strokeLinecap="round" />
      <path d="M76 136 h16 M128 136 h16" stroke="#171916" strokeWidth="5" strokeLinecap="round" />
    </svg>
  );
}
