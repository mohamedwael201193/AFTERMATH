import { cn } from "@/lib/utils";
import type { InstrumentKind } from "@/types/domain";

/**
 * Original token visual system.
 *
 * Every instrument in the catalog renders through the same chip language:
 * a thick-ink rounded square, warm-white face, Archivo Black symbol, and a
 * small kind accent (reference tick for equity tokens, bars for index
 * tokens). No plain text grid, no generic crypto logos.
 */

const KIND_ACCENT: Record<InstrumentKind, { label: string; color: string }> = {
  EQUITY_TOKEN: { label: "equity token", color: "#086B32" },
  INDEX_TOKEN: { label: "index token", color: "#C9A227" },
  CRYPTO_LINKED: { label: "crypto-linked", color: "#9A6106" },
};

export function TokenIcon({
  symbol,
  kind,
  size = 44,
  className,
  elevated = false,
}: {
  symbol: string;
  kind: InstrumentKind;
  size?: number;
  className?: string;
  elevated?: boolean;
}) {
  const accent = KIND_ACCENT[kind];
  const fontSize = symbol.length >= 5 ? 9.5 : symbol.length === 4 ? 11 : 13.5;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      role="img"
      aria-label={`${symbol} ${accent.label} icon`}
      className={cn(elevated && "sticker-shadow-sm", className)}
    >
      {/* face */}
      <rect
        x="3.5"
        y="3.5"
        width="41"
        height="41"
        rx="13"
        fill="#FFFEF8"
        stroke="#171916"
        strokeWidth="2.6"
      />
      {/* top-left paper highlight */}
      <path
        d="M10 8.5 h8"
        stroke="#E3ECDF"
        strokeWidth="3"
        strokeLinecap="round"
      />
      {/* symbol */}
      <text
        x="24"
        y="27"
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={fontSize}
        fill="#171916"
        style={{ fontFamily: "var(--font-display)" }}
      >
        {symbol}
      </text>
      {/* kind accent */}
      {kind === "EQUITY_TOKEN" && (
        <g>
          <path
            d="M13.5 36.5 h6"
            stroke={accent.color}
            strokeWidth="2.6"
            strokeLinecap="round"
          />
          <path
            d="M23 36.5 h11.5"
            stroke="#D8D8CA"
            strokeWidth="2.6"
            strokeLinecap="round"
          />
          <circle cx="35" cy="36.5" r="1.9" fill={accent.color} />
        </g>
      )}
      {kind === "INDEX_TOKEN" && (
        <g fill={accent.color}>
          <rect x="17.5" y="33" width="3.4" height="7" rx="1.2" />
          <rect x="22.3" y="30.5" width="3.4" height="9.5" rx="1.2" />
          <rect x="27.1" y="34.5" width="3.4" height="5.5" rx="1.2" />
        </g>
      )}
      {kind === "CRYPTO_LINKED" && (
        <g stroke={accent.color} strokeWidth="2.2" fill="none" strokeLinecap="round">
          <circle cx="19.5" cy="36.5" r="2.6" />
          <circle cx="28.5" cy="36.5" r="2.6" />
          <path d="M21.8 36.5 h4.4" />
        </g>
      )}
    </svg>
  );
}

/** Small circular token for orbits and dense lists. */
export function TokenDot({
  symbol,
  size = 34,
  tone = "cream",
  className,
}: {
  symbol: string;
  size?: number;
  tone?: "cream" | "forest";
  className?: string;
}) {
  const fontSize = symbol.length >= 5 ? 7.5 : symbol.length === 4 ? 9 : 10.5;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 36 36"
      role="img"
      aria-label={`${symbol} token`}
      className={className}
    >
      <circle
        cx="18"
        cy="18"
        r="15.5"
        fill={tone === "cream" ? "#FFFEF8" : "#064D27"}
        stroke="#171916"
        strokeWidth="2.4"
      />
      <circle cx="18" cy="18" r="11" fill="none" stroke={tone === "cream" ? "#E3ECDF" : "#0A5A2D"} strokeWidth="1.4" strokeDasharray="2.4 3" />
      <text
        x="18"
        y="18.6"
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={fontSize}
        fill={tone === "cream" ? "#171916" : "#F5F2E7"}
        style={{ fontFamily: "var(--font-display)" }}
      >
        {symbol}
      </text>
    </svg>
  );
}
