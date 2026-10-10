"use client";

import { useMemo, useState } from "react";
import { Filter, X } from "lucide-react";
import type { ActivityRecord, DecisionState, SourceKind } from "@/types/domain";
import { DecisionBadge } from "@/components/dashboard/DecisionBadge";
import { EmptyStateArt } from "@/components/artwork/EmptyStateArt";
import { TickerIcon } from "@/components/artwork/TickerIcon";
import { instrumentCatalog } from "@/data/instrumentCatalog";
import { SOURCE_KIND_LABELS } from "@/data/sources";
import { formatEt, relativeToNow } from "@/lib/format";
import { useDashboardStore } from "@/lib/dashboardStore";
import { cn } from "@/lib/utils";

type OutcomeFilter = "ALL" | DecisionState;
type RangeFilter = "ALL" | "24H" | "48H";
type SourceFilter = "ALL" | SourceKind;
type VerificationFilter = "ALL" | "DIGEST" | "STRUCTURE";

const OUTCOMES: OutcomeFilter[] = ["ALL", "PROCEED", "REDUCE", "WAIT", "REJECT", "NO ACTION"];
const RANGES: { value: RangeFilter; label: string }[] = [
  { value: "24H", label: "Last 24 h" },
  { value: "48H", label: "Last 48 h" },
  { value: "ALL", label: "Whole window" },
];

/**
 * Decision history — compact, filterable, and connected: selecting a row
 * opens the full decision record in the detail panel.
 *
 * Layout rules that keep the table readable at every width:
 *  - the table scrolls horizontally instead of clipping when space is tight;
 *  - the receipt column only renders on very wide screens;
 *  - narrow screens use summary cards instead of the table.
 */
export function HistoryPanel({ activity }: { activity: ActivityRecord[] }) {
  const selectEvent = useDashboardStore((s) => s.selectEvent);
  const panelOpen = !!useDashboardStore((s) => s.selectedEventId);
  const [outcome, setOutcome] = useState<OutcomeFilter>("ALL");
  const [range, setRange] = useState<RangeFilter>("ALL");
  const [source, setSource] = useState<SourceFilter>("ALL");
  const [verification, setVerification] = useState<VerificationFilter>("ALL");

  const rows = useMemo(() => {
    return activity.filter((a) => {
      if (outcome !== "ALL" && a.decisionState !== outcome) return false;
      if (source !== "ALL" && a.sourceKind !== source) return false;
      if (verification === "DIGEST" && !a.receiptDigest) return false;
      if (verification === "STRUCTURE" && !a.receiptDigest) return false;
      if (range !== "ALL") {
        const hours = range === "24H" ? 24 : 48;
        const ageH = (Date.now() - Date.parse(a.occurredAt)) / 3600000;
        if (ageH > hours) return false;
      }
      return true;
    });
  }, [activity, outcome, range, source, verification]);

  const anyFilter =
    outcome !== "ALL" || range !== "ALL" || source !== "ALL" || verification !== "ALL";

  const reset = () => {
    setOutcome("ALL");
    setRange("ALL");
    setSource("ALL");
    setVerification("ALL");
  };

  return (
    <div className="grid grid-cols-1 gap-4">
      {/* filters */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-3xl border-2 border-line bg-paper px-4 py-3.5">
        <span className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-ink-soft">
          <Filter className="h-3.5 w-3.5" aria-hidden="true" /> Filters
        </span>

        <fieldset className="flex flex-wrap items-center gap-1.5">
          <legend className="sr-only">Filter by outcome</legend>
          {OUTCOMES.map((o) => (
            <button
              key={o}
              onClick={() => setOutcome(o)}
              aria-pressed={outcome === o}
              className={cn(
                "inline-flex h-8 items-center rounded-full border-2 px-3 text-[11px] font-bold whitespace-nowrap transition-colors",
                outcome === o
                  ? "border-ink bg-forest text-paper"
                  : "border-line-strong bg-warmwhite text-ink-soft hover:border-ink hover:text-ink"
              )}
            >
              {o === "ALL" ? "All outcomes" : o}
            </button>
          ))}
        </fieldset>

        <label className="flex items-center gap-2 text-xs font-bold text-ink-soft">
          <span className="uppercase tracking-wide">Date</span>
          <select
            value={range}
            onChange={(e) => setRange(e.target.value as RangeFilter)}
            className="h-8 rounded-full border-2 border-line-strong bg-warmwhite px-2.5 text-[11px] font-bold text-ink focus-visible:outline-forest"
          >
            {RANGES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        </label>

        <label className="flex items-center gap-2 text-xs font-bold text-ink-soft">
          <span className="uppercase tracking-wide">Source</span>
          <select
            value={source}
            onChange={(e) => setSource(e.target.value as SourceFilter)}
            className="h-8 max-w-[9.5rem] rounded-full border-2 border-line-strong bg-warmwhite px-2.5 text-[11px] font-bold text-ink focus-visible:outline-forest"
          >
            <option value="ALL">All sources</option>
            {Object.entries(SOURCE_KIND_LABELS).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>

        <label className="flex items-center gap-2 text-xs font-bold text-ink-soft">
          <span className="uppercase tracking-wide">Receipt</span>
          <select
            value={verification}
            onChange={(e) => setVerification(e.target.value as VerificationFilter)}
            className="h-8 rounded-full border-2 border-line-strong bg-warmwhite px-2.5 text-[11px] font-bold text-ink focus-visible:outline-forest"
          >
            <option value="ALL">Any</option>
            <option value="DIGEST">Has digest</option>
            <option value="STRUCTURE">Structure verified</option>
          </select>
        </label>

        {anyFilter && (
          <button
            onClick={reset}
            className="ml-auto inline-flex h-8 items-center gap-1 rounded-full border-2 border-ink bg-warmwhite px-3 text-[11px] font-bold text-ink transition-colors hover:bg-forest-mist"
          >
            <X className="h-3 w-3" aria-hidden="true" /> Clear
          </button>
        )}
      </div>

      <p className="text-xs font-semibold text-ink-soft" aria-live="polite">
        {rows.length} of {activity.length} records shown
      </p>

      {rows.length === 0 ? (
        <div className="grid place-items-center gap-3 rounded-3xl border-2 border-dashed border-line-strong bg-warmwhite px-6 py-12 text-center">
          <EmptyStateArt width={170} />
          <p className="text-sm font-bold text-ink">No decisions match these filters</p>
          <p className="max-w-sm text-sm text-ink-soft">
            The evidence for this combination isn't in the window — clear a filter
            or widen the date range to find it.
          </p>
          <button
            onClick={reset}
            className="rounded-full border-2 border-ink bg-warmwhite px-4 py-1.5 text-xs font-bold text-ink hover:bg-forest-mist"
          >
            Clear filters
          </button>
        </div>
      ) : (
        <>
          {/* wide-screen table */}
          <div className="hidden overflow-x-auto rounded-3xl border-2 border-ink bg-warmwhite shadow-[0_4px_0_rgba(23,25,22,0.85)] scroll-slim lg:block">
            <table
              className={cn(
                "w-full table-auto border-collapse text-left text-sm",
                panelOpen ? "min-w-[460px]" : "min-w-[620px]"
              )}
            >
              <caption className="sr-only">
                Decision history — select a row to open its full record
              </caption>
              <thead>
                <tr className="border-b-2 border-ink bg-paper text-[11px] font-bold uppercase tracking-wider text-ink-soft">
                  <th scope="col" className="whitespace-nowrap px-4 py-3">When</th>
                  <th scope="col" className="whitespace-nowrap px-3 py-3">Asset</th>
                  <th
                    scope="col"
                    className={cn(
                      "px-3 py-3",
                      // The open record already shows the headline — free the width.
                      panelOpen && "hidden 2xl:table-cell"
                    )}
                  >
                    Event
                  </th>
                  <th scope="col" className="whitespace-nowrap px-3 py-3">Decision</th>
                  <th scope="col" className="whitespace-nowrap px-3 py-3 @max-[32rem]:hidden">Risk</th>
                  <th scope="col" className="whitespace-nowrap px-3 py-3">Execution</th>
                  <th scope="col" className="hidden whitespace-nowrap px-4 py-3 2xl:table-cell">
                    Receipt
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((a) => {
                  const catalog = instrumentCatalog.find((i) => i.symbol === a.instrumentSymbol);
                  return (
                    <tr
                      key={a.eventId}
                      tabIndex={0}
                      role="button"
                      aria-label={`Open decision record for ${a.headline}`}
                      onClick={() => selectEvent(a.eventId)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          selectEvent(a.eventId);
                        }
                      }}
                      className="cursor-pointer border-b border-line align-middle transition-colors last:border-0 hover:bg-forest-mist/60 focus-visible:bg-forest-mist/60 focus-visible:outline-none"
                    >
                      <td className="whitespace-nowrap px-3 py-3">
                        <span className="tnum block text-xs font-bold text-ink">
                          {formatEt(a.occurredAt, "compact")}
                        </span>
                        <span className="tnum block text-[10px] font-semibold text-ink-soft">
                          {relativeToNow(a.occurredAt)}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-3">
                        <span className="flex items-center gap-1.5">
                          <TickerIcon
                            symbol={a.instrumentSymbol}
                            kind={catalog?.kind ?? "EQUITY_TOKEN"}
                            size={26}
                          />
                          <span className="text-xs font-bold text-ink">{a.instrumentSymbol}</span>
                        </span>
                      </td>
                      <td className={cn("max-w-[20rem] px-3 py-3", panelOpen && "hidden 2xl:table-cell")}>
                        <span
                          className="block truncate text-xs font-semibold text-ink"
                          title={a.headline}
                        >
                          {a.headline}
                        </span>
                        <span className="text-[10px] font-semibold text-ink-soft">
                          {SOURCE_KIND_LABELS[a.sourceKind]}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-3">
                        <DecisionBadge state={a.decisionState} size="sm" />
                      </td>
                      {/* risk column folds away when the decision panel squeezes
                          the table — the open record already shows full risk detail */}
                      <td className="whitespace-nowrap px-3 py-3 @max-[32rem]:hidden">
                        <span
                          className={cn(
                            "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide",
                            a.riskOutcome === "APPROVED" && "border-forest bg-forest-mist text-forest-deep",
                            a.riskOutcome === "REDUCED" && "border-ink bg-warn-soft text-warn",
                            a.riskOutcome === "REFUSED" && "border-ink bg-risk-soft text-risk"
                          )}
                        >
                          {a.riskOutcome}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 text-xs font-bold text-ink">
                        {a.execution === "FILLED" ? "Paper fill" : a.execution === "REFUSED" ? "Refused" : "No order"}
                      </td>
                      <td className="hidden whitespace-nowrap px-4 py-3 font-mono text-[11px] font-bold text-forest-deep tnum 2xl:table-cell">
                        {a.receiptDigest ?? "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* narrow-screen cards */}
          <ul className="grid grid-cols-1 gap-3 lg:hidden">
            {rows.map((a) => {
              const catalog = instrumentCatalog.find((i) => i.symbol === a.instrumentSymbol);
              return (
                <li key={a.eventId}>
                  <button
                    onClick={() => selectEvent(a.eventId)}
                    className="grid w-full grid-cols-1 gap-2.5 rounded-3xl border-2 border-line bg-warmwhite px-4 py-3.5 text-left transition-colors hover:border-ink"
                  >
                    <div className="flex items-center gap-2.5">
                      <TickerIcon symbol={a.instrumentSymbol} kind={catalog?.kind ?? "EQUITY_TOKEN"} size={30} />
                      <span className="tnum text-xs font-bold text-ink">{a.instrumentSymbol}</span>
                      <DecisionBadge state={a.decisionState} size="sm" />
                      <span className="tnum ml-auto text-[10px] font-semibold text-ink-soft">
                        {formatEt(a.occurredAt, "full")} ET
                      </span>
                    </div>
                    <p className="line-clamp-2 text-xs font-semibold leading-snug text-ink">
                      {a.headline}
                    </p>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] font-bold text-ink-soft">
                      <span className="rounded-full border border-line-strong bg-paper px-2 py-0.5">
                        Risk: {a.riskOutcome}
                      </span>
                      <span className="rounded-full border border-line-strong bg-paper px-2 py-0.5">
                        {a.execution === "FILLED" ? "paper fill" : a.execution === "REFUSED" ? "refused" : "no order"}
                      </span>
                      <span className="tnum font-mono">{a.receiptDigest ?? "no digest"}</span>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}
