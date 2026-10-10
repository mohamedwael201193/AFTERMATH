"use client";

import { useMemo } from "react";
import { ReceiptText } from "lucide-react";
import type { ActivityRecord } from "@/types/domain";
import { CostBreakdownChart } from "@/components/charts/CostBreakdownChart";
import { TickerIcon } from "@/components/artwork/TickerIcon";
import { instrumentCatalog } from "@/data/instrumentCatalog";
import { formatEt, formatUsd } from "@/lib/format";
import { useDashboardStore } from "@/lib/dashboardStore";
import { cn } from "@/lib/utils";

/**
 * Paper activity ledger — fills, refusals, and waits with their notes and
 * estimated costs. The honest book: what was simulated, what was blocked,
 * and why.
 */
export function ActivityPanel({ activity }: { activity: ActivityRecord[] }) {
  const selectEvent = useDashboardStore((s) => s.selectEvent);

  const fills = activity.filter((a) => a.execution === "FILLED");
  const refusals = activity.filter((a) => a.execution === "REFUSED");
  const combinedCosts = useMemo(
    () => [
      { label: "Exchange fees", usd: 0 },
      { label: "Slippage", usd: 0 },
    ],
    []
  );

  return (
    <div className="grid grid-cols-1 gap-6">
      <section className="grid grid-cols-1 gap-4 rounded-3xl border-2 border-ink bg-warmwhite p-5 shadow-[0_4px_0_rgba(23,25,22,0.85)] sm:p-6 @min-[46rem]:grid-cols-[minmax(0,1fr)_320px]">
        <div>
          <h3 className="text-sm font-bold uppercase tracking-wide text-ink-soft">
            The paper book — what actually happened
          </h3>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-ink-soft">
            {fills.length} stored paper {fills.length === 1 ? "fill" : "fills"} and {refusals.length} recorded{" "}
            {refusals.length === 1 ? "refusal" : "refusals"}. Zero fills are not a profit result. Costs stay
            INSUFFICIENT_DATA until a graded fill is stored.
          </p>
          <dl className="tnum mt-4 grid grid-cols-3 gap-3 text-center">
            <div className="rounded-2xl border-2 border-line bg-paper px-3 py-3">
              <dt className="text-[10px] font-bold uppercase text-ink-soft">Fills</dt>
              <dd className="mt-1 font-display text-2xl text-forest-deep">{fills.length}</dd>
            </div>
            <div className="rounded-2xl border-2 border-line bg-paper px-3 py-3">
              <dt className="text-[10px] font-bold uppercase text-ink-soft">Order refusals</dt>
              <dd className="mt-1 font-display text-2xl text-risk">
                {refusals.length}
              </dd>
            </div>
            <div className="rounded-2xl border-2 border-forest bg-forest-mist px-3 py-3">
              <dt className="text-[10px] font-bold uppercase text-forest-deep">Costs</dt>
              <dd className="mt-1 font-display text-lg text-forest-deep">
                {fills.length === 0 ? "INSUFFICIENT_DATA" : formatUsd(combinedCosts[0].usd + combinedCosts[1].usd)}
              </dd>
            </div>
          </dl>
        </div>
        <div className="rounded-3xl border-2 border-line bg-paper p-4">
          <p className="text-xs font-bold uppercase tracking-wide text-ink-soft">
            Estimated cost structure (fills)
          </p>
          {fills.length === 0 ? (
            <p className="mt-6 text-sm font-semibold text-ink-soft">INSUFFICIENT_DATA — no graded fill is stored.</p>
          ) : (
            <CostBreakdownChart costs={combinedCosts} height={170} />
          )}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-3">
        <h3 className="text-sm font-bold uppercase tracking-wide text-ink-soft">
          Execution ledger
        </h3>
        <ol className="grid grid-cols-1 gap-3">
          {activity.map((a) => {
            return (
              <li key={a.eventId}>
                <button
                  onClick={() => selectEvent(a.eventId)}
                  className={cn(
                    "grid w-full grid-cols-1 gap-3 rounded-3xl border-2 bg-warmwhite px-4 py-4 text-left transition-all hover:border-ink sm:px-5",
                    a.execution === "FILLED" ? "border-line" : a.execution === "REFUSED" ? "border-warn/60" : "border-line"
                  )}
                >
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                    <span
                      className={cn(
                        "inline-flex shrink-0 items-center gap-1.5 rounded-full border-2 border-ink px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide",
                        a.execution === "FILLED"
                          ? "bg-forest text-paper"
                          : a.execution === "REFUSED"
                            ? "bg-warn text-paper"
                            : "bg-hold text-paper"
                      )}
                    >
                      {a.execution === "FILLED" ? "Paper fill" : a.execution === "REFUSED" ? "Refused" : "No order"}
                    </span>
                    <span className="flex shrink-0 items-center gap-2">
                      <TickerIcon
                        symbol={a.instrumentSymbol || "CYCLE"}
                        kind={instrumentCatalog.find((i) => i.symbol === a.instrumentSymbol)?.kind ?? "EQUITY_TOKEN"}
                        size={24}
                      />
                      <span className="tnum text-xs font-bold text-ink">{a.instrumentSymbol || "Cycle"}</span>
                    </span>
                    <span className="min-w-0 flex-1 truncate text-xs font-semibold text-ink-soft" title={a.headline}>
                      {a.headline}
                    </span>
                    <span className="tnum shrink-0 text-[10px] font-semibold text-ink-soft">
                      {formatEt(a.occurredAt, "full")} ET
                    </span>
                  </div>
                  <p className="flex items-center gap-2 text-[10px] font-bold text-ink-soft">
                    <ReceiptText className="h-3.5 w-3.5" aria-hidden="true" />
                    <span className="tnum font-mono">{a.receiptDigest ?? "—"}</span>
                    <span className="ml-auto font-semibold uppercase tracking-wide">
                      Open full record →
                    </span>
                  </p>
                </button>
              </li>
            );
          })}
        </ol>
      </section>
    </div>
  );
}
