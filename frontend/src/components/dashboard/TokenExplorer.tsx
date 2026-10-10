"use client";

import { useMemo, useState } from "react";
import { Search, Eye } from "lucide-react";
import type { MarketEvent, MarketObservation } from "@/types/domain";
import { TickerIcon } from "@/components/artwork/TickerIcon";
import { FreshnessDot } from "@/components/artwork/StatusGlyphs";
import { formatPct, formatUsd, FRESHNESS_LABELS } from "@/lib/format";
import { useDashboardStore } from "@/lib/dashboardStore";
import { cn } from "@/lib/utils";

const WHITELIST = [
  ["NVDAUSDT", "NVIDIA"],
  ["TSLAUSDT", "Tesla"],
  ["AAPLUSDT", "Apple"],
  ["AMZNUSDT", "Amazon"],
  ["MSFTUSDT", "Microsoft"],
  ["METAUSDT", "Meta"],
  ["GOOGLUSDT", "Alphabet"],
  ["COINUSDT", "Coinbase"],
  ["MSTRUSDT", "MicroStrategy"],
].map(([symbol, name]) => ({
  symbol,
  name,
  kind: "EQUITY_TOKEN" as const,
  company: name,
  referenceSymbol: symbol.replace(/USDT$/, ""),
  venue: "Bitget USDT perpetual",
}));

function sameSymbol(left: string, right: string): boolean {
  const norm = (value: string) => value.toUpperCase().replace(/USDT$/, "");
  return norm(left) === norm(right);
}

/**
 * Market & token explorer — a searchable grid of representative
 * instruments with the original token visual system. Selecting a token
 * focuses its latest event (when one exists) or opens an asset view.
 */
export function TokenExplorer({
  observations,
  events,
}: {
  observations: MarketObservation[];
  events: MarketEvent[];
}) {
  const search = useDashboardStore((s) => s.searchQuery);
  const setSearch = useDashboardStore((s) => s.setSearch);
  const selectEvent = useDashboardStore((s) => s.selectEvent);
  const [focusedSymbol, setFocusedSymbol] = useState<string | null>(null);

  const entries = useMemo(() => {
    const q = search.trim().toLowerCase();
    return WHITELIST
      .map((i) => ({
        instrument: i,
        observation: observations.find((o) => sameSymbol(o.symbol, i.symbol)) ?? null,
        latestEvent:
          events.find((e) => e.instrumentSymbol && sameSymbol(e.instrumentSymbol, i.symbol)) ?? null,
      }))
      .filter(({ instrument }) => {
        if (!q) return true;
        return (
          instrument.symbol.toLowerCase().includes(q) ||
          instrument.name.toLowerCase().includes(q) ||
          (instrument.company ?? "").toLowerCase().includes(q)
        );
      });
  }, [observations, events, search]);

  const focused = focusedSymbol
    ? entries.find((e) => e.instrument.symbol === focusedSymbol)
    : null;

  return (
    <div className="grid grid-cols-1 gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[220px] flex-1">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-soft" aria-hidden="true" />
          <label htmlFor="token-search" className="sr-only">
            Search instruments by symbol, name, or company
          </label>
          <input
            id="token-search"
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search symbols, names, companies…"
            className="h-11 w-full rounded-full border-2 border-ink bg-warmwhite pl-10 pr-4 text-sm font-semibold text-ink placeholder:text-ink-soft/70 focus-visible:outline-forest"
          />
        </div>
        <p className="text-xs font-semibold text-ink-soft">
          {entries.length} of {WHITELIST.length} whitelist instruments · stored snapshots only
        </p>
      </div>

      <ul className="grid grid-cols-1 gap-3 [scroll-margin-top:5rem] @min-[28rem]:grid-cols-2 @min-[60rem]:grid-cols-3">
        {entries.map(({ instrument, observation, latestEvent }) => {
          const open = focusedSymbol === instrument.symbol;
          return (
            <li key={instrument.symbol} className="h-full">
              <button
                onClick={() => setFocusedSymbol(open ? null : instrument.symbol)}
                aria-expanded={open}
                className={cn(
                  "@container grid h-full w-full grid-cols-1 gap-3 rounded-3xl border-2 bg-warmwhite px-4 py-4 text-left transition-all",
                  open
                    ? "border-ink bg-forest-mist shadow-[0_4px_0_rgba(23,25,22,0.85)]"
                    : "border-line hover:border-ink hover:shadow-[0_4px_0_rgba(23,25,22,0.85)]"
                )}
              >
                <div className="flex items-center gap-3">
                  <TickerIcon symbol={instrument.symbol} kind={instrument.kind} size={42} />
                  <div className="min-w-0 flex-1">
                    <p
                      className="truncate text-sm font-bold text-ink"
                      title={instrument.name}
                    >
                      {instrument.name}
                    </p>
                    <p
                      className="truncate text-[11px] font-semibold text-ink-soft"
                      title={instrument.company ?? instrument.venue}
                    >
                      {instrument.company ?? instrument.venue}
                    </p>
                  </div>
                  <span className="ml-auto hidden shrink-0 items-center gap-1.5 rounded-full border border-line-strong bg-paper px-2 py-1 text-[10px] font-bold text-ink-soft @min-[15rem]:inline-flex">
                    {instrument.kind === "EQUITY_TOKEN" ? "Equity" : instrument.kind === "INDEX_TOKEN" ? "Index" : "Linked"}
                  </span>
                </div>

                {observation && (
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                    <span className="tnum font-bold text-ink">{formatUsd(observation.priceUsd)}</span>
                    <span className={cn("tnum text-xs font-bold", observation.changePct24h == null ? "text-ink-soft" : observation.changePct24h >= 0 ? "text-forest" : "text-risk")}>
                      {observation.changePct24h == null ? "24h n/a" : formatPct(observation.changePct24h)}
                    </span>
                    <span className="inline-flex items-center gap-1.5 text-[10px] font-bold text-ink-soft">
                      <FreshnessDot freshness={observation.freshness} />
                      {FRESHNESS_LABELS[observation.freshness]}
                    </span>
                  </div>
                )}

                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full border border-line-strong bg-paper px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-ink-soft">
                    Observation only
                  </span>
                  <span className="text-[11px] font-semibold text-ink-soft">
                    {latestEvent ? "Stored market row" : "No stored observation"}
                  </span>
                </div>
              </button>

              {open && (
                <div className="mt-2 grid gap-2.5 rounded-3xl border-2 border-dashed border-line-strong bg-paper px-4 py-4">
                  <dl className="grid gap-x-4 gap-y-1.5 text-xs">
                    <div className="flex gap-2">
                      <dt className="font-bold uppercase tracking-wide text-ink-soft">Reference</dt>
                      <dd className="font-semibold text-ink">{instrument.referenceSymbol ?? "—"}</dd>
                    </div>
                    <div className="flex gap-2">
                      <dt className="font-bold uppercase tracking-wide text-ink-soft">Venue</dt>
                      <dd className="font-semibold text-ink">{instrument.venue}</dd>
                    </div>
                    {observation && (
                      <div className="flex gap-2">
                        <dt className="font-bold uppercase tracking-wide text-ink-soft">Observed</dt>
                        <dd className="font-semibold text-ink">{observation.sessionNote}</dd>
                      </div>
                    )}
                  </dl>
                  <p className="text-xs leading-relaxed text-ink-soft">
                    Whitelist identity only. This card does not carry a decision.
                  </p>
                  {latestEvent ? (
                    <button
                      onClick={() => {
                        selectEvent(latestEvent.id);
                        setFocusedSymbol(null);
                      }}
                      className="inline-flex items-center justify-center gap-2 rounded-full border-2 border-ink bg-forest px-4 py-2 text-xs font-bold text-paper shadow-[0_3px_0_rgba(23,25,22,0.85)] transition-transform hover:-translate-y-0.5"
                    >
                      <Eye className="h-3.5 w-3.5" aria-hidden="true" />
                      Inspect latest event
                    </button>
                  ) : (
                    <p className="text-xs font-semibold text-ink-soft">
                      No stored observation for this symbol.
                    </p>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {entries.length === 0 && (
        <div className="rounded-3xl border-2 border-dashed border-line-strong bg-warmwhite px-6 py-10 text-center">
          <p className="text-sm font-bold text-ink">No instruments match “{search}”</p>
          <button
            onClick={() => setSearch("")}
            className="mt-2 rounded-full border-2 border-ink bg-warmwhite px-4 py-1.5 text-xs font-bold text-ink hover:bg-forest-mist"
          >
            Clear search
          </button>
        </div>
      )}

      {focused && (
        <p className="sr-only" aria-live="polite">
          Focused instrument: {focused.instrument.symbol}
        </p>
      )}
    </div>
  );
}
