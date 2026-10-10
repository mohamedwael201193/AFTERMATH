"use client";

import { Activity, BarChart3, ShieldCheck, Zap } from "lucide-react";
import type { ActivityRecord, MarketEvent, MarketObservation } from "@/types/domain";
import { EventFeed } from "@/components/dashboard/EventFeed";
import { TokenExplorer } from "@/components/dashboard/TokenExplorer";
import { DecisionBadge } from "@/components/dashboard/DecisionBadge";
import { TickerIcon } from "@/components/artwork/TickerIcon";
import { instrumentCatalog } from "@/data/instrumentCatalog";
import { formatEt, relativeToNow } from "@/lib/format";
import type { CycleStatus } from "@/components/dashboard/useDashboardData";
import { useDashboardStore } from "@/lib/dashboardStore";
import { cn } from "@/lib/utils";

function SummaryCard({
  icon: Icon,
  label,
  value,
  hint,
  detail,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  hint: string;
  detail?: React.ReactNode;
}) {
  return (
    <article className="flex h-full min-h-[10.5rem] flex-col rounded-3xl border-2 border-ink bg-warmwhite p-5 shadow-[0_4px_0_rgba(23,25,22,0.85)]">
      <div className="flex items-center gap-3">
        <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border-2 border-ink bg-forest-mist text-forest-deep">
          <Icon className="h-5 w-5" aria-hidden="true" />
        </span>
        <p className="text-xs font-bold uppercase tracking-wide text-ink-soft">{label}</p>
      </div>
      <p className="tnum mt-3 font-display text-[2rem] leading-none text-forest-deep">{value}</p>
      <p className="mt-1.5 text-xs font-semibold text-ink-soft">{hint}</p>
      {detail && <div className="mt-auto pt-3">{detail}</div>}
    </article>
  );
}

export function OverviewPanel({
  events,
  observations,
  activity,
  cycle,
}: {
  events: MarketEvent[];
  observations: MarketObservation[];
  activity: ActivityRecord[];
  cycle: CycleStatus | null;
}) {
  const selectEvent = useDashboardStore((s) => s.selectEvent);

  const fills = activity.filter((a) => a.execution === "FILLED");
  const blocks = activity.filter((a) => a.riskOutcome === "REFUSED");

  const recentActivity = activity.slice(0, 5);

  return (
    <div className="grid grid-cols-1 gap-6">
      {/* summary cards — container queries: columns follow the real available
          width, so the grid stays comfortable whether the decision panel is
          open (main squeezed) or closed (main full width) */}
      <div className="grid grid-cols-1 gap-4 [scroll-margin-top:5rem] @min-[28rem]:grid-cols-2 @min-[60rem]:grid-cols-4">
        <SummaryCard
          icon={Zap}
          label="Stored books"
          value={String(cycle?.eventCount ?? events.length)}
          hint="order books, not filings or decisions"
          detail={
            <p className="text-[11px] font-semibold text-ink-soft">
              {observations.length} symbols · latest {events[0] ? relativeToNow(events[0].occurredAt) : "—"}
            </p>
          }
        />
        <SummaryCard
          icon={BarChart3}
          label="Decisions recorded"
          value={String(cycle?.decisionCount ?? 0)}
          hint="paper-cycle decisions, not one per symbol"
          detail={
            <p className="text-[11px] font-semibold text-ink-soft">
              Latest cycle: {cycle?.reason || "none"}. This bar is not a catalogue of symbol decisions.
            </p>
          }
        />
        <SummaryCard
          icon={Activity}
          label="Paper fills"
          value={String(cycle?.fillCount ?? fills.length)}
          hint={cycle?.evaluationStatus || (fills.length ? "fills recorded on the ledger" : "INSUFFICIENT_DATA")}
          detail={
            <p className="text-[11px] font-semibold text-ink-soft">
              {fills.map((f) => f.instrumentSymbol).join(" · ")} — estimates, not profits
            </p>
          }
        />
        <SummaryCard
          icon={ShieldCheck}
          label={cycle?.reason === "no_qualifying_event" ? "Pre-model refusal" : "Risk blocks"}
          value={String(cycle?.refusalCount ?? blocks.length)}
          hint={cycle?.stale ? "last cycle is older than 2 hours" : cycle?.reason || "refusals as designed"}
          detail={
            <p className="text-[11px] font-semibold text-ink-soft">
              {cycle?.reason === "no_qualifying_event"
                ? "The model and the governor were not called. This is not a risk-block."
                : "Missing evidence, stale data, or unsupported claims"}
            </p>
          }
        />
      </div>

      <section className="rounded-3xl border-2 border-ink bg-paper px-5 py-4">
        <h3 className="text-sm font-bold uppercase tracking-wide text-ink">Price history</h3>
        <p className="mt-1 text-sm text-ink-soft">
          INSUFFICIENT_DATA. The service stores the latest order book, not a performance series.
        </p>
      </section>

      {/* recent events + recent activity */}
      <div className="grid grid-cols-1 gap-6 @min-[46rem]:grid-cols-2">
        <section className="grid grid-cols-1 gap-3 content-start">
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
            <h3 className="text-sm font-bold uppercase tracking-wide text-ink-soft">
              Recent observations
            </h3>
            <span className="min-w-0 text-[11px] font-semibold text-ink-soft">
              stored books, not filings or model decisions
            </span>
          </div>
          <EventFeed events={events} limit={4} showFilters={false} />
        </section>

        <section className="grid grid-cols-1 gap-3 content-start">
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
            <h3 className="text-sm font-bold uppercase tracking-wide text-ink-soft">
              Recent paper activity
            </h3>
          </div>
          <ul className="grid grid-cols-1 gap-2.5">
            {recentActivity.map((a) => {
              const cat = instrumentCatalog.find((i) => i.symbol === a.instrumentSymbol);
              return (
                <li key={a.eventId}>
                  <button
                    onClick={() => selectEvent(a.eventId)}
                    className="flex w-full items-center gap-x-3 gap-y-1.5 rounded-2xl border-2 border-line bg-warmwhite px-4 py-3 text-left transition-colors hover:border-ink"
                  >
                    <TickerIcon symbol={a.instrumentSymbol} kind={cat?.kind ?? "EQUITY_TOKEN"} size={28} />
                    <span className="min-w-0 flex-1 line-clamp-1 text-xs font-semibold text-ink" title={a.headline}>
                      {a.headline}
                    </span>
                  <span
                    className={cn(
                      "shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide",
                      a.execution === "FILLED"
                        ? "border-forest bg-forest-mist text-forest-deep"
                        : a.execution === "REFUSED"
                          ? "border-ink bg-risk-soft text-risk"
                          : "border-line-strong bg-paper text-ink-soft"
                    )}
                  >
                    {a.execution === "FILLED" ? "Filled" : a.execution === "REFUSED" ? "Refused" : "No order"}
                  </span>
                  <span className="tnum hidden shrink-0 text-[10px] font-semibold text-ink-soft sm:block">
                    {formatEt(a.occurredAt, "full")} ET · {relativeToNow(a.occurredAt)}
                  </span>
                </button>
              </li>
            );
            })}
          </ul>
          <p className="text-[11px] font-semibold text-ink-soft">
            Fills are simulated with estimated costs. Refusals are recorded outcomes,
            not failures.
          </p>
        </section>
      </div>

      {/* token explorer */}
      <section className="grid grid-cols-1 gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-bold uppercase tracking-wide text-ink-soft">
            Market explorer
          </h3>
          <span className="text-[11px] font-semibold text-ink-soft">
            whitelist instruments · price only when a book snapshot is stored
          </span>
        </div>
        <TokenExplorer observations={observations} events={events} />
      </section>
    </div>
  );
}
