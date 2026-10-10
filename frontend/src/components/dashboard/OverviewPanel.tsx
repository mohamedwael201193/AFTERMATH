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

const SUMMARY = [
  {
    icon: Zap,
    label: "Events in window",
    hint: "detected in the last ~36 hours",
  },
  {
    icon: BarChart3,
    label: "Decisions recorded",
    hint: "every one auditable",
  },
  {
    icon: Activity,
    label: "Paper fills",
    hint: "with estimated costs",
  },
  {
    icon: ShieldCheck,
    label: "Risk blocks",
    hint: "refusals as designed",
  },
] as const;

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

/** Decision-state distribution bar (never color-only — labeled below). */
function DistributionBar({ events }: { events: MarketEvent[] }) {
  const counts = events.reduce<Record<string, number>>((acc, e) => {
    acc[e.decisionState] = (acc[e.decisionState] ?? 0) + 1;
    return acc;
  }, {});
  const order = ["PROCEED", "REDUCE", "WAIT", "REJECT", "NO ACTION"] as const;
  const tones: Record<string, string> = {
    PROCEED: "bg-forest",
    REDUCE: "bg-warn",
    WAIT: "bg-ink",
    REJECT: "bg-risk",
    "NO ACTION": "bg-hold",
  };
  const total = events.length || 1;
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-full border-2 border-ink bg-paper" aria-hidden="true">
        {order.map((k) =>
          counts[k] ? (
            <div key={k} className={cn(tones[k])} style={{ width: `${(counts[k] / total) * 100}%` }} />
          ) : null
        )}
      </div>
      <ul className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1">
        {order.map((k) => (
          <li key={k} className="flex items-center gap-1.5 whitespace-nowrap text-[10px] font-bold text-ink-soft">
            <span className={cn("h-2 w-2 shrink-0 rounded-full border border-ink", tones[k])} aria-hidden="true" />
            {k} · {counts[k] ?? 0}
          </li>
        ))}
      </ul>
    </div>
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
          label="Events in window"
          value={String(events.length)}
          hint={`latest ${events[0] ? relativeToNow(events[0].occurredAt) : "—"}`}
          detail={
            <p className="text-[11px] font-semibold text-ink-soft">
              {events.filter((e) => e.status === "REVIEWING").length} reviewing ·{" "}
              {events.filter((e) => e.status === "RESOLVED").length} resolved
            </p>
          }
        />
        <SummaryCard
          icon={BarChart3}
          label="Decisions recorded"
          value={String(cycle?.decisionCount ?? 0)}
          hint="paper-cycle decisions, not one per symbol"
          detail={<DistributionBar events={activity.map((row) => ({ decisionState: row.decisionState } as MarketEvent))} />}
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
          label="Risk blocks"
          value={String(cycle?.refusalCount ?? blocks.length)}
          hint={cycle?.stale ? "last cycle is older than 2 hours" : cycle?.reason || "refusals as designed"}
          detail={
            <p className="text-[11px] font-semibold text-ink-soft">
              Missing evidence, stale data, or unsupported claims
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
              Recent events
            </h3>
            <span className="min-w-0 text-[11px] font-semibold text-ink-soft">
              select one to open its full decision record
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
