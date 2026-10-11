"use client";

import { useMemo } from "react";
import { ReceiptText } from "lucide-react";
import type { ActivityRecord } from "@/types/domain";
import { CostBreakdownChart } from "@/components/charts/CostBreakdownChart";
import { TickerIcon } from "@/components/artwork/TickerIcon";
import { instrumentCatalog } from "@/data/instrumentCatalog";
import { formatEt, formatUsd } from "@/lib/format";
import { useDashboardStore } from "@/lib/dashboardStore";
import type { CycleStatus } from "@/components/dashboard/useDashboardData";
import { shownCount } from "@/services/liveDataProvider";
import { cn } from "@/lib/utils";

/**
 * Paper activity ledger — fills, refusals, and waits with their notes and
 * estimated costs. The honest book: what was simulated, what was blocked,
 * and why.
 */
export function ActivityPanel({ activity, cycle = null }: { activity: ActivityRecord[]; cycle?: CycleStatus | null }) {
  const selectEvent = useDashboardStore((s) => s.selectEvent);

  const paperFills = cycle?.paperFills;
  const preModelRefusals = cycle?.preModelRefusals;
  const riskRefusals = cycle?.riskRefusals;
  const scheduledCycles = cycle?.scheduledCycles;
  const llmDecisions = cycle?.llmDecisions;
  const hasFills = typeof paperFills === "number" && paperFills > 0;
  const combinedCosts = useMemo(
    () => [
      { label: "Exchange fees", usd: 0 },
      { label: "Slippage", usd: 0 },
    ],
    []
  );
  const counterCells = [
    { label: "Scheduled cycles", value: shownCount(scheduledCycles), tone: "text-ink" },
    { label: "Pre-model refusals", value: shownCount(preModelRefusals), tone: "text-ink" },
    { label: "LLM decisions", value: shownCount(llmDecisions), tone: "text-forest-deep" },
    { label: "Risk refusals", value: shownCount(riskRefusals), tone: "text-risk" },
    { label: "Paper fills", value: shownCount(paperFills), tone: "text-forest-deep" },
  ];

  return (
    <div className="grid grid-cols-1 gap-6">
      <section className="grid grid-cols-1 gap-4 rounded-3xl border-2 border-ink bg-warmwhite p-5 shadow-[0_4px_0_rgba(23,25,22,0.85)] sm:p-6 @min-[46rem]:grid-cols-[minmax(0,1fr)_320px]">
        <div>
          <h3 className="text-sm font-bold uppercase tracking-wide text-ink-soft">
            The paper book — what actually happened
          </h3>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-ink-soft">
            Scheduled cycles {shownCount(scheduledCycles)}. Pre-model refusals {shownCount(preModelRefusals)}. LLM decisions{" "}
            {shownCount(llmDecisions)}. Risk refusals {shownCount(riskRefusals)}. Paper fills {shownCount(paperFills)}. A pre-model refusal is not a governor block.
            {paperFills === 0 ? " Zero paper fills are not a profit result." : ""} Costs stay INSUFFICIENT_DATA until a graded fill is stored.
          </p>
          <dl className="tnum mt-4 grid grid-cols-2 gap-3 text-center @min-[28rem]:grid-cols-3 @min-[60rem]:grid-cols-6">
            {counterCells.map((cell) => (
              <div key={cell.label} className="rounded-2xl border-2 border-line bg-paper px-3 py-3">
                <dt className="text-[10px] font-bold uppercase text-ink-soft">{cell.label}</dt>
                <dd className={cn("mt-1 font-display text-2xl", cell.tone)}>{cell.value}</dd>
              </div>
            ))}
            <div className="rounded-2xl border-2 border-forest bg-forest-mist px-3 py-3">
              <dt className="text-[10px] font-bold uppercase text-forest-deep">Costs</dt>
              <dd className="mt-1 font-display text-lg text-forest-deep">
                {hasFills ? formatUsd(combinedCosts[0].usd + combinedCosts[1].usd) : "INSUFFICIENT_DATA"}
              </dd>
            </div>
          </dl>
        </div>
        <div className="rounded-3xl border-2 border-line bg-paper p-4">
          <p className="text-xs font-bold uppercase tracking-wide text-ink-soft">
            Estimated cost structure (fills)
          </p>
          {hasFills ? (
            <CostBreakdownChart costs={combinedCosts} height={170} />
          ) : (
            <p className="mt-6 text-sm font-semibold text-ink-soft">INSUFFICIENT_DATA — no graded fill is stored.</p>
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
