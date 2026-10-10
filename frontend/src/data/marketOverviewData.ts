import type { MarketObservation, PriceSeries, PriceSeriesPoint } from "@/types/domain";

/**
 * Market overview data for the preview workspace.
 *
 * Everything here is deterministic: a fixed workspace clock, fixed
 * observations, and a seeded generator for illustrative price series.
 * No value in this file is a live market measurement.
 */

/** Fixed preview workspace clock (Fri 2026-01-09 22:10 UTC · 17:10 ET). */
export const WORKSPACE_ANCHOR = "2026-01-09T22:10:00Z";

export const WORKSPACE_SESSION_LABELS = {
  usCash: "US cash market · closed",
  usCashDetail: "Fri 16:00 ET close · reopens Mon 09:30 ET",
  tokenMarkets: "Tokenized markets · continuous",
  workspace: "Preview workspace · illustrative data",
} as const;

export const marketObservations: MarketObservation[] = [
  { symbol: "NVDA", priceUsd: 189.42, changePct24h: 4.1, observedAt: "2026-01-09T22:08:00Z", freshness: "FRESH", sessionNote: "Tokenized price moving after US cash close" },
  { symbol: "TSLA", priceUsd: 412.8, changePct24h: -1.8, observedAt: "2026-01-09T22:06:00Z", freshness: "FRESH", sessionNote: "Tokenized price drifting after US cash close" },
  { symbol: "MSFT", priceUsd: 448.15, changePct24h: 0.3, observedAt: "2026-01-09T22:06:00Z", freshness: "FRESH", sessionNote: "Quiet after US cash close" },
  { symbol: "META", priceUsd: 638.2, changePct24h: 0.9, observedAt: "2026-01-09T22:07:00Z", freshness: "FRESH", sessionNote: "Quiet after US cash close" },
  { symbol: "AAPL", priceUsd: 241.1, changePct24h: 0.2, observedAt: "2026-01-09T22:05:00Z", freshness: "FRESH", sessionNote: "Quiet after US cash close" },
  { symbol: "AMZN", priceUsd: 229.6, changePct24h: 1.1, observedAt: "2026-01-09T22:07:00Z", freshness: "FRESH", sessionNote: "Post-filing drift stabilizing" },
  { symbol: "GOOGL", priceUsd: 198.45, changePct24h: -0.4, observedAt: "2026-01-09T22:05:00Z", freshness: "FRESH", sessionNote: "Quiet after US cash close" },
  { symbol: "COIN", priceUsd: 281.35, changePct24h: -6.2, observedAt: "2026-01-09T22:09:00Z", freshness: "FRESH", sessionNote: "Sharp move; reference quote lagging" },
  { symbol: "QQQ", priceUsd: 519.9, changePct24h: 0.1, observedAt: "2026-01-09T22:04:00Z", freshness: "AGING", sessionNote: "Reference closed until Monday cash open" },
  { symbol: "SPY", priceUsd: 602.3, changePct24h: 0.1, observedAt: "2026-01-09T22:04:00Z", freshness: "AGING", sessionNote: "Reference closed until Monday cash open" },
  { symbol: "MU", priceUsd: 118.9, changePct24h: -2.4, observedAt: "2026-01-09T22:06:00Z", freshness: "FRESH", sessionNote: "Soft after tariff review headline" },
];

export function findObservation(symbol: string): MarketObservation | null {
  return marketObservations.find((o) => o.symbol === symbol) ?? null;
}

/* ── Deterministic illustrative price series ────────────────────── */

/** Deterministic PRNG so charts render identically on every load. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashString(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

interface SeriesSpec {
  symbol: string;
  basePrice: number;
  /** Volatility as a fraction of price per step. */
  vol: number;
  start: string;
  end: string;
  stepMinutes: number;
  /** Deterministic jumps: ISO time → percent change applied from that point. */
  jumps?: Array<{ at: string; pct: number }>;
  markers: PriceSeries["markers"];
}

function buildSeries(spec: SeriesSpec): PriceSeries {
  const rand = mulberry32(hashString(spec.symbol));
  const startMs = Date.parse(spec.start);
  const endMs = Date.parse(spec.end);
  const stepMs = spec.stepMinutes * 60_000;

  const points: PriceSeriesPoint[] = [];
  // Walk the series with a gentle mean-reverting random walk.
  let price = spec.basePrice;
  const anchor = spec.basePrice;
  let eventActive = false;
  for (let t = startMs; t <= endMs; t += stepMs) {
    const iso = new Date(t).toISOString();

    for (const j of spec.jumps ?? []) {
      if (Date.parse(j.at) <= t && Date.parse(j.at) > t - stepMs) {
        price *= 1 + j.pct / 100;
        eventActive = true;
      }
    }

    // Mean-reverting drift keeps the walk bounded and repeatable in feel.
    const pull = (anchor - price) / anchor * 0.06;
    const noise = (rand() - 0.5) * 2 * spec.vol;
    price = price * (1 + pull + noise);

    points.push({ t: iso, p: Math.round(price * 100) / 100, event: eventActive });
  }

  return { symbol: spec.symbol, points, markers: spec.markers };
}

const SESSION_MARKERS = [
  { t: "2026-01-09T14:30:00Z", label: "US cash open · 09:30 ET", kind: "SESSION" as const },
  { t: "2026-01-09T21:00:00Z", label: "US cash close · 16:00 ET", kind: "SESSION" as const },
];

const seriesSpecs: SeriesSpec[] = [
  {
    symbol: "NVDA",
    basePrice: 181.4,
    vol: 0.0012,
    start: "2026-01-09T06:00:00Z",
    end: "2026-01-09T22:10:00Z",
    stepMinutes: 15,
    jumps: [{ at: "2026-01-09T21:15:00Z", pct: 4.4 }],
    markers: [
      ...SESSION_MARKERS,
      { t: "2026-01-09T21:16:00Z", label: "Q3 report · 16:16 ET", kind: "EVENT" as const },
    ],
  },
  {
    symbol: "TSLA",
    basePrice: 420.5,
    vol: 0.0016,
    start: "2026-01-09T06:00:00Z",
    end: "2026-01-09T22:10:00Z",
    stepMinutes: 15,
    jumps: [{ at: "2026-01-09T18:05:00Z", pct: -0.9 }],
    markers: [
      ...SESSION_MARKERS,
      { t: "2026-01-09T18:05:00Z", label: "Supply headline · 13:05 ET", kind: "EVENT" as const },
    ],
  },
  {
    symbol: "META",
    basePrice: 632.6,
    vol: 0.0014,
    start: "2026-01-09T06:00:00Z",
    end: "2026-01-09T22:10:00Z",
    stepMinutes: 15,
    jumps: [{ at: "2026-01-09T19:47:00Z", pct: 0.7 }, { at: "2026-01-09T20:15:00Z", pct: -0.5 }],
    markers: [
      ...SESSION_MARKERS,
      { t: "2026-01-09T19:47:00Z", label: "Misleading headline · 14:47 ET", kind: "EVENT" as const },
    ],
  },
  {
    symbol: "COIN",
    basePrice: 299.6,
    vol: 0.0021,
    start: "2026-01-09T06:00:00Z",
    end: "2026-01-09T22:10:00Z",
    stepMinutes: 15,
    jumps: [{ at: "2026-01-09T20:45:00Z", pct: -6.3 }],
    markers: [
      ...SESSION_MARKERS,
      { t: "2026-01-09T20:58:00Z", label: "Reference gap detected · 15:58 ET", kind: "EVENT" as const },
    ],
  },
  {
    symbol: "AMZN",
    basePrice: 227.1,
    vol: 0.0013,
    start: "2026-01-09T06:00:00Z",
    end: "2026-01-09T22:10:00Z",
    stepMinutes: 15,
    jumps: [{ at: "2026-01-09T14:22:00Z", pct: 1.2 }],
    markers: [
      ...SESSION_MARKERS,
      { t: "2026-01-09T14:22:00Z", label: "8-K filing · 09:22 ET", kind: "EVENT" as const },
    ],
  },
  {
    symbol: "QQQ",
    basePrice: 519.4,
    vol: 0.0007,
    start: "2026-01-09T06:00:00Z",
    end: "2026-01-09T22:10:00Z",
    stepMinutes: 15,
    jumps: [{ at: "2026-01-09T13:30:00Z", pct: 0.18 }],
    markers: [
      ...SESSION_MARKERS,
      { t: "2026-01-09T13:30:00Z", label: "CPI print · 08:30 ET", kind: "EVENT" as const },
    ],
  },
  {
    symbol: "MU",
    basePrice: 121.8,
    vol: 0.0018,
    start: "2026-01-09T06:00:00Z",
    end: "2026-01-09T22:10:00Z",
    stepMinutes: 15,
    jumps: [{ at: "2026-01-09T12:31:00Z", pct: -2.1 }],
    markers: [
      ...SESSION_MARKERS,
      { t: "2026-01-09T12:31:00Z", label: "Tariff review headline · 07:31 ET", kind: "EVENT" as const },
    ],
  },
  {
    symbol: "AAPL",
    basePrice: 240.6,
    vol: 0.001,
    start: "2026-01-08T06:00:00Z",
    end: "2026-01-09T22:10:00Z",
    stepMinutes: 30,
    jumps: [{ at: "2026-01-08T21:40:00Z", pct: 0.1 }],
    markers: [
      { t: "2026-01-08T21:00:00Z", label: "US cash close · Thu", kind: "SESSION" as const },
      { t: "2026-01-09T14:30:00Z", label: "US cash open · 09:30 ET", kind: "SESSION" as const },
      { t: "2026-01-09T21:00:00Z", label: "US cash close · 16:00 ET", kind: "SESSION" as const },
      { t: "2026-01-08T21:40:00Z", label: "Dividend record · Thu 16:40 ET", kind: "EVENT" as const },
    ],
  },
];

export const priceSeriesBySymbol: Record<string, PriceSeries> = Object.fromEntries(
  seriesSpecs.map((s) => [s.symbol, buildSeries(s)])
);

export function findPriceSeries(symbol: string): PriceSeries | null {
  return priceSeriesBySymbol[symbol] ?? null;
}
