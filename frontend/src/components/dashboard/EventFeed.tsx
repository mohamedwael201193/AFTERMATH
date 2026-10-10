"use client";

import { useMemo } from "react";
import { Inbox } from "lucide-react";
import type { MarketEvent } from "@/types/domain";
import { DecisionBadge, CategoryBadge, CompletenessMeter } from "@/components/dashboard/DecisionBadge";
import { TickerIcon } from "@/components/artwork/TickerIcon";
import { instrumentCatalog } from "@/data/instrumentCatalog";
import { formatEt, relativeToNow } from "@/lib/format";
import { useDashboardStore } from "@/lib/dashboardStore";
import { cn } from "@/lib/utils";

/**
 * Event intelligence feed — readable rows with headline, instrument,
 * category, timing, source, evidence completeness, and decision state.
 *
 * Two-line row structure keeps every element readable at every width:
 *   line 1 — ticker icon + headline + decision badge;
 *   line 2 — category, timing, source, and the evidence meter.
 */
export function EventFeed({
  events,
  limit,
  showFilters = true,
}: {
  events: MarketEvent[];
  limit?: number;
  showFilters?: boolean;
}) {
  const search = useDashboardStore((s) => s.searchQuery);
  const selectEvent = useDashboardStore((s) => s.selectEvent);
  const selectedId = useDashboardStore((s) => s.selectedEventId);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return events.filter((e) => {
      if (!q) return true;
      return (
        e.headline.toLowerCase().includes(q) ||
        (e.instrumentSymbol ?? "").toLowerCase().includes(q) ||
        e.category.toLowerCase().includes(q)
      );
    });
  }, [events, search]);

  const shown = limit ? filtered.slice(0, limit) : filtered;

  if (shown.length === 0) {
    return (
      <div className="grid gap-3 rounded-3xl border-2 border-dashed border-line-strong bg-warmwhite px-6 py-10 text-center">
        <Inbox className="mx-auto h-8 w-8 text-ink-soft" aria-hidden="true" />
        <p className="text-sm font-bold text-ink">No events match your filters</p>
        <p className="mx-auto max-w-sm text-sm text-ink-soft">
          {search
            ? `Nothing matches “${search}” in the stored events.`
            : "No stored events match these filters."}
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3">
      {showFilters && (
        <p className="text-xs font-semibold text-ink-soft">
          {filtered.length} event{filtered.length === 1 ? "" : "s"} in the current window
          {search && (
            <>
              {" "}matching “<span className="font-bold text-ink">{search}</span>”
            </>
          )}
        </p>
      )}
      <ul className="grid grid-cols-1 gap-3">
        {shown.map((e) => {
          const symbol = (e.instrumentSymbol || "").replace(/USDT$/i, "");
          const catalog = instrumentCatalog.find((i) => i.symbol === symbol || i.symbol === e.instrumentSymbol);
          const selected = selectedId === e.id;
          return (
            <li key={e.id}>
              <button
                onClick={() => selectEvent(e.id)}
                aria-pressed={selected}
                className={cn(
                  "grid w-full grid-cols-1 gap-2.5 rounded-3xl border-2 px-4 py-4 text-left transition-all sm:px-5",
                  selected
                    ? "border-ink bg-forest-mist shadow-[0_4px_0_rgba(23,25,22,0.85)]"
                    : "border-line bg-warmwhite hover:border-ink hover:shadow-[0_4px_0_rgba(23,25,22,0.85)]"
                )}
              >
                {/* line 1 — identity + verdict */}
                <div className="flex items-start gap-3">
                  {e.instrumentSymbol ? (
                    <TickerIcon symbol={e.instrumentSymbol} kind={catalog?.kind ?? "EQUITY_TOKEN"} size={38} className="shrink-0" />
                  ) : (
                    <span className="inline-flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-xl border-2 border-ink bg-paper text-[10px] font-bold text-ink-soft">
                      EV
                    </span>
                  )}
                  <p
                    className="min-w-0 flex-1 line-clamp-2 text-sm font-bold leading-snug text-ink sm:text-base"
                    title={e.headline}
                  >
                    {e.headline}
                  </p>
                  {e.status === "NEW" ? (
                    <span className="shrink-0 rounded-full border border-line-strong bg-paper px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-ink-soft">
                      Observation
                    </span>
                  ) : (
                    <DecisionBadge state={e.decisionState} className="shrink-0" />
                  )}
                </div>

                {/* line 2 — context + evidence health */}
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 pl-1">
                  <CategoryBadge category={e.category} />
                  <span className="tnum text-[11px] font-semibold text-ink-soft">
                    {formatEt(e.occurredAt, "full")} ET · {relativeToNow(e.occurredAt)}
                  </span>
                  <span className="text-[11px] font-semibold text-ink-soft">
                    {e.source.name}
                  </span>
                  {e.category === "MARKET" ? null : (
                    <CompletenessMeter value={e.evidenceCompleteness} className="ml-auto" />
                  )}
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
