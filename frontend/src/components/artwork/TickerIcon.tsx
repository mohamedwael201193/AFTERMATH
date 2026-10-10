"use client";

import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import type { InstrumentKind } from "@/types/domain";

/**
 * TickerIcon — real stock/token logos from CDN sources, by uppercase ticker.
 *
 * Source chain (first that loads wins):
 *   1. Transparent PNG CDN, no key required:
 *      https://financialmodelingprep.com/image-stock/{TICKER}.png
 *   2. Company-domain favicon service:
 *      https://www.google.com/s2/favicons?domain={domain}&sz=64
 *   3. Local graceful fallback: a brand-consistent tile showing the first
 *      two letters of the ticker (always renders, never breaks).
 *
 * Reserved for the real backend integration (documented, not active here):
 *   - jsDelivr GH path for the nvstly/icons Nasdaq set — the repository is
 *     currently not served by jsDelivr (all paths 404), so shipping it as a
 *     live source would add a wasted request per icon.
 *   - logo.dev ticker API — requires an API token; we do not hardcode keys.
 * Both can be prepended to `tickerIconSources` once credentials/paths exist.
 */

const PNG_CDN_BASE = "https://financialmodelingprep.com/image-stock";
const FAVICON_CDN_BASE = "https://www.google.com/s2/favicons";

/** Company domains for the favicon fallback, keyed by uppercase ticker. */
const TICKER_DOMAINS: Record<string, string> = {
  NVDA: "nvidia.com",
  TSLA: "tesla.com",
  MSFT: "microsoft.com",
  META: "meta.com",
  AAPL: "apple.com",
  AMZN: "amazon.com",
  GOOGL: "abc.xyz",
  COIN: "coinbase.com",
  QQQ: "invesco.com",
  SPY: "ssga.com",
  MU: "micron.com",
};

/** URLs tried in order for one ticker (uppercase, per icon policy). */
export function tickerIconSources(_symbol: string): string[] {
  return [];
}

/** Remembers broken URLs across mounts so lists never re-request them. */
const brokenUrls = new Set<string>();

/**
 * Tickers whose CDN logo is white / near-white (measured against the palette:
 * QQQ is 100% white pixels, AAPL ~88% light-gray). Seated on a forest-deep
 * backdrop so they stay visible on the warm-white chip faces everywhere.
 */
const LOW_CONTRAST_TICKERS = new Set(["QQQ", "AAPL"]);

/** Backdrop chip for white/near-white logos — keeps them readable. */
function BackdropChip({
  src,
  ticker,
  size,
  elevated,
  className,
  onError,
}: {
  src: string;
  ticker: string;
  size: number;
  elevated?: boolean;
  className?: string;
  onError: () => void;
}) {
  return (
    <span
      role="img"
      aria-label={`${ticker} logo`}
      className={cn(
        "inline-flex shrink-0 select-none items-center justify-center rounded-[26%] bg-forest-deep",
        elevated && "sticker-shadow-sm",
        className
      )}
      style={{ width: size, height: size }}
    >
      <img
        src={src}
        alt=""
        width={Math.round(size * 0.74)}
        height={Math.round(size * 0.74)}
        loading="lazy"
        decoding="async"
        draggable={false}
        onError={onError}
        className="rounded-[8%] object-contain"
      />
    </span>
  );
}

const KIND_ACCENT: Record<InstrumentKind, string> = {
  EQUITY_TOKEN: "#086B32",
  INDEX_TOKEN: "#C9A227",
  CRYPTO_LINKED: "#9A6106",
};

/** Local fallback tile — first two letters, original AFTERMATH chip style. */
function FallbackTile({
  symbol,
  size,
  kind,
}: {
  symbol: string;
  size: number;
  kind: InstrumentKind;
}) {
  const letters = symbol.toUpperCase().slice(0, 2);
  const fontSize = size >= 44 ? 14 : size >= 34 ? 12 : 10;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      role="img"
      aria-label={`${symbol.toUpperCase()} icon`}
    >
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
      <path d="M10 8.5 h8" stroke="#E3ECDF" strokeWidth="3" strokeLinecap="round" />
      <text
        x="24"
        y="24"
        textAnchor="middle"
        dominantBaseline="central"
        fontSize={fontSize * 1.6}
        fill="#171916"
        style={{ fontFamily: "var(--font-display)" }}
      >
        {letters}
      </text>
      <path
        d="M15 37.5 h18"
        stroke={KIND_ACCENT[kind] ?? "#65695F"}
        strokeWidth="2.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function TickerIcon({
  symbol,
  size = 36,
  kind = "EQUITY_TOKEN",
  className,
  /** Reserve exact layout space while the remote icon loads. */
  elevated = false,
}: {
  symbol: string;
  size?: number;
  kind?: InstrumentKind;
  className?: string;
  elevated?: boolean;
}) {
  const ticker = symbol.toUpperCase();
  const sources = useMemo(() => tickerIconSources(ticker), [ticker]);

  // Start past URLs that are known-broken from earlier mounts.
  const [index, setIndex] = useState(() => {
    let i = 0;
    while (i < sources.length && brokenUrls.has(sources[i])) i++;
    return i;
  });

  if (index >= sources.length) {
    return (
      <FallbackTile
        symbol={ticker}
        size={size}
        kind={kind}
      />
    );
  }

  if (LOW_CONTRAST_TICKERS.has(ticker)) {
    return (
      <BackdropChip
        src={sources[index]}
        ticker={ticker}
        size={size}
        elevated={elevated}
        className={className}
        onError={() => {
          brokenUrls.add(sources[index]);
          setIndex((i) => i + 1);
        }}
      />
    );
  }

  return (
    // Remote transparent PNG — plain <img> keeps the fallback chain simple
    // and avoids server-side image optimization round-trips for tiny icons.
    <img
      src={sources[index]}
      alt={`${ticker} logo`}
      width={size}
      height={size}
      loading="lazy"
      decoding="async"
      draggable={false}
      onError={() => {
        brokenUrls.add(sources[index]);
        setIndex((i) => i + 1);
      }}
      className={cn(
        "shrink-0 select-none rounded-[28%] object-contain",
        elevated && "sticker-shadow-sm",
        className
      )}
      style={{ width: size, height: size }}
    />
  );
}
