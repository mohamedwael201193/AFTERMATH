"use client";

import { useMemo } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BrainCircuit,
  ClipboardList,
  FileSearch,
  Gauge,
  ShieldCheck,
  Stamp,
  TrendingUp,
} from "lucide-react";
import type { EventBundle } from "@/types/domain";
import { DecisionBadge, RiskOutcomeBadge, CategoryBadge, CompletenessMeter } from "@/components/dashboard/DecisionBadge";
import { EvidenceCard } from "@/components/evidence/EvidenceCard";
import { ReceiptCard } from "@/components/receipts/ReceiptCard";
import { RiskMark } from "@/components/artwork/StatusGlyphs";
import { TickerIcon } from "@/components/artwork/TickerIcon";
import { PriceEventChart } from "@/components/charts/PriceEventChart";
import { CostBreakdownChart } from "@/components/charts/CostBreakdownChart";
import { useDashboardStore } from "@/lib/dashboardStore";
import { DECISION_META, RISK_STATUS_LABELS, formatConfidence, formatEt, formatPct, formatUsd, relativeToNow } from "@/lib/format";
import { cn } from "@/lib/utils";

function SectionTitle({
  icon: Icon,
  step,
  children,
}: {
  icon: React.ElementType;
  step: string;
  children: React.ReactNode;
}) {
  return (
    <h3 className="flex items-center gap-2.5 text-sm font-bold uppercase tracking-[0.12em] text-ink-soft">
      <span className="inline-flex h-8 w-8 items-center justify-center rounded-xl border-2 border-ink bg-warmwhite text-forest">
        <Icon className="h-4 w-4" aria-hidden="true" />
      </span>
      <span className="tnum text-[10px] font-bold text-line-strong">{step}</span>
      {children}
    </h3>
  );
}

/**
 * The decision detail panel — AFTERMATH's heart.
 * Seven questions, seven plain-language answers.
 */
export function DecisionDetail({ bundle }: { bundle: EventBundle }) {
  const detailedRisk = useDashboardStore((s) => s.settings.detailedRisk);
  const { event, instrument, observation, evidence, decision, risk, execution, receipt, priceSeries } = bundle;

  const concerns = useMemo(() => {
    const list: Array<{ tone: "warn" | "risk"; text: string }> = [];
    for (const e of evidence) {
      if (e.verification === "CONFLICTING")
        list.push({ tone: "warn", text: `Conflicting records on “${e.label}” — the story and its source disagree.` });
      if (e.verification === "UNVERIFIED")
        list.push({ tone: "warn", text: `“${e.label}” is unverified — no primary record confirms it yet.` });
      if (e.freshness === "STALE")
        list.push({ tone: "risk", text: `“${e.label}” is stale (${formatEt(e.capturedAt)} ET) — too old to trade against.` });
    }
    for (const c of risk.checks) {
      if (c.status === "FAIL")
        list.push({ tone: "risk", text: `${c.label}: ${c.detail} Observed ${c.observed ?? "n/a"} against ${c.limit ?? "its limit"}.` });
      else if (c.status === "WARN")
        list.push({ tone: "warn", text: `${c.label}: ${c.observed ?? "noted"} — within tolerance only marginally.` });
    }
    return list;
  }, [evidence, risk]);

  return (
    <div className="grid grid-cols-1 gap-6">
      {/* ── header ─────────────────────────────────────────── */}
      <header className="grid grid-cols-1 gap-4">
        <div className="flex flex-wrap items-start gap-3">
          {instrument && (
            <TickerIcon symbol={instrument.symbol} kind={instrument.kind} size={46} elevated />
          )}
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <CategoryBadge category={event.category} />
              <span className="tnum text-xs font-bold text-ink-soft">
                {formatEt(event.occurredAt, "full")} ET · {relativeToNow(event.occurredAt)}
              </span>
            </div>
            <h2 className="mt-2 text-xl font-bold leading-snug text-ink sm:text-2xl">
              {event.headline}
            </h2>
            <p className="mt-1 text-xs font-semibold text-ink-soft">
              {instrument?.name ?? "No instrument"} · {event.source.name}
            </p>
          </div>
          <DecisionBadge state={decision.state} size="lg" className="ml-auto" />
        </div>

        {observation && (
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-2xl border-2 border-line bg-paper px-4 py-2.5 text-sm">
            <span className="tnum font-bold text-ink">
              {observation.symbol}{" "}
              <span className="text-base">{formatUsd(observation.priceUsd)}</span>
            </span>
            <span className={cn("tnum font-bold", observation.changePct24h == null ? "text-ink-soft" : observation.changePct24h >= 0 ? "text-forest" : "text-risk")}>
              {observation.changePct24h == null ? "24h change not in this snapshot" : `${formatPct(observation.changePct24h)} · 24h`}
            </span>
            <span className="text-xs font-semibold text-ink-soft">
              observed {formatEt(observation.observedAt)} ET · {observation.sessionNote}
            </span>
            <CompletenessMeter value={event.evidenceCompleteness} className="ml-auto" />
          </div>
        )}
      </header>

      {/* ── 1 · what happened ──────────────────────────────── */}
      <section className="grid grid-cols-1 gap-3">
        <SectionTitle icon={ClipboardList} step="01">What happened?</SectionTitle>
        <p className="rounded-3xl border-2 border-line bg-warmwhite px-5 py-4 text-sm leading-relaxed text-ink sm:text-base">
          {event.summary}
        </p>
      </section>

      {/* ── 2 · evidence ───────────────────────────────────── */}
      <section className="grid grid-cols-1 gap-3">
        <SectionTitle icon={FileSearch} step="02">What evidence supports it?</SectionTitle>
        <div className="grid grid-cols-1 gap-2.5">
          {evidence.map((e, i) => (
            <EvidenceCard key={e.id} record={e} defaultOpen={i === 0 && detailedRisk} />
          ))}
        </div>
        <p className="text-xs text-ink-soft">
          Stored evidence for this record, with its source, timestamp, units, and freshness.
          A cycle refusal does not turn this list into a model decision.
        </p>
      </section>

      {/* ── 3 · the decision ───────────────────────────────── */}
      <section className="grid grid-cols-1 gap-3">
        <SectionTitle icon={BrainCircuit} step="03">
          {decision.modelCalled === false ? "MODEL NOT CALLED — PRE-MODEL REFUSAL" : "What did the AI decide?"}
        </SectionTitle>
        <div className="overflow-hidden rounded-3xl border-2 border-ink bg-warmwhite shadow-[0_4px_0_rgba(23,25,22,0.85)]">
          <div className="flex flex-wrap items-center gap-4 border-b-2 border-line bg-paper px-5 py-4">
            <DecisionBadge state={decision.state} size="lg" />
            {decision.modelCalled === false ? (
              <p className="text-sm font-semibold text-ink-soft">No model confidence — the model was not called.</p>
            ) : (
            <div className="min-w-[160px] flex-1">
              <div className="flex items-center justify-between text-xs font-bold text-ink-soft">
                <span>Model-stated confidence</span>
                <span className="tnum text-ink">{formatConfidence(decision.confidence)}</span>
              </div>
              <div
                className="mt-1.5 h-3 overflow-hidden rounded-full border-2 border-ink bg-paper"
                role="meter"
                aria-valuenow={Math.round(decision.confidence * 100)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`Model confidence ${formatConfidence(decision.confidence)}`}
              >
                <div
                  className={cn(
                    "h-full rounded-full transition-all",
                    decision.confidence >= 0.7 ? "bg-forest" : decision.confidence >= 0.45 ? "bg-warn" : "bg-risk"
                  )}
                  style={{ width: `${decision.confidence * 100}%` }}
                />
              </div>
            </div>
            )}
            {decision.proposedAction && (
              <span className="tnum inline-flex items-center gap-2 rounded-full border-2 border-ink bg-forest-mist px-3.5 py-1.5 text-sm font-bold text-forest-deep">
                <TrendingUp className="h-4 w-4" aria-hidden="true" />
                {decision.proposedAction.side} {decision.proposedAction.sizeTokens}{" "}
                {decision.proposedAction.symbol} · ≈ {formatUsd(decision.proposedAction.notionalUsd)}
              </span>
            )}
          </div>
          <div className="grid grid-cols-1 gap-4 px-5 py-4">
            <p className="text-sm leading-relaxed text-ink sm:text-base">
              {decision.plainLanguage}
            </p>
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-ink-soft">Reasoning</p>
              <ul className="mt-2 grid gap-2">
                {decision.reasoning.map((r, i) => (
                  <li key={i} className="flex gap-2.5 text-sm leading-relaxed text-ink">
                    <span className="tnum mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-ink bg-paper text-[10px] font-bold text-ink-soft">
                      {i + 1}
                    </span>
                    {r}
                  </li>
                ))}
              </ul>
            </div>
            {decision.invalidationConditions.length > 0 && (
              <div className="rounded-2xl border-2 border-dashed border-line-strong bg-paper px-4 py-3">
                <p className="text-xs font-bold uppercase tracking-wide text-ink-soft">
                  What would change its mind
                </p>
                <ul className="mt-1.5 grid gap-1.5">
                  {decision.invalidationConditions.map((c, i) => (
                    <li key={i} className="flex gap-2 text-sm leading-relaxed text-ink-soft">
                      <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-forest" aria-hidden="true" />
                      {c}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* ── 4 · what could go wrong ────────────────────────── */}
      <section className="grid grid-cols-1 gap-3">
        <SectionTitle icon={AlertTriangle} step="04">What could go wrong?</SectionTitle>
        {concerns.length === 0 ? (
          <p className="rounded-3xl border-2 border-forest bg-forest-mist px-5 py-4 text-sm leading-relaxed text-forest-deep">
            {decision.modelCalled === false
              ? "The governor was not called. This observation has no risk verdict."
              : "No open concerns recorded: every evidence record is confirmed and fresh, and all risk observations sit inside their limits."}
          </p>
        ) : (
          <ul className="grid grid-cols-1 gap-2.5">
            {concerns.map((c, i) => (
              <li
                key={i}
                className={cn(
                  "flex gap-3 rounded-2xl border-2 px-4 py-3 text-sm leading-relaxed",
                  c.tone === "risk"
                    ? "border-ink bg-risk-soft text-ink"
                    : "border-warn bg-warn-soft text-ink"
                )}
              >
                <AlertTriangle
                  className={cn("mt-0.5 h-4 w-4 shrink-0", c.tone === "risk" ? "text-risk" : "text-warn")}
                  aria-hidden="true"
                />
                {c.text}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ── 5 · risk engine ────────────────────────────────── */}
      <section className="grid grid-cols-1 gap-3">
        <SectionTitle icon={ShieldCheck} step="05">What does the risk engine say?</SectionTitle>
        <div className="overflow-hidden rounded-3xl border-2 border-ink bg-warmwhite shadow-[0_4px_0_rgba(23,25,22,0.85)]">
          <div className="flex flex-wrap items-center gap-3 border-b-2 border-line bg-paper px-5 py-3.5">
            <RiskOutcomeBadge outcome={risk.outcome} />
            {risk.sizeMultiplier !== null && (
              <span className="tnum rounded-full border-2 border-ink bg-warn-soft px-2.5 py-1 text-xs font-bold text-warn">
                Size cut to {Math.round(risk.sizeMultiplier * 100)}%
              </span>
            )}
            <span className="ml-auto text-[10px] font-bold uppercase tracking-wide text-ink-soft">
              Deterministic · the AI cannot overrule
            </span>
          </div>
          <p className="px-5 pt-4 text-sm leading-relaxed text-ink">{risk.plainLanguage}</p>
          <ul className="grid grid-cols-1 gap-2 px-5 py-4">
            {risk.checks.map((c) => (
              <li key={c.id} className="rounded-2xl border-2 border-line bg-paper px-4 py-3">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <RiskMark status={c.status} size={22} />
                  <span className="text-sm font-bold text-ink">{c.label}</span>
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide",
                      c.status === "PASS" && "bg-forest-mist text-forest-deep",
                      c.status === "WARN" && "bg-warn-soft text-warn",
                      c.status === "FAIL" && "bg-risk-soft text-risk"
                    )}
                  >
                    {RISK_STATUS_LABELS[c.status]}
                  </span>
                  <span className="tnum ml-auto text-[11px] font-semibold text-ink-soft">
                    {c.observed ?? "—"} / {c.limit ?? "—"}
                  </span>
                </div>
                {(detailedRisk || c.status !== "PASS") && (
                  <p className="mt-2 text-xs leading-relaxed text-ink-soft">{c.detail}</p>
                )}
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* ── 6 · what happened next ─────────────────────────── */}
      <section className="grid grid-cols-1 gap-3">
        <SectionTitle icon={Gauge} step="06">What happened next?</SectionTitle>
        {/* single column: this tree always renders inside the ~440–500px
            decision panel (or the mobile drawer), never a full-width main */}
        <div className="grid grid-cols-1 gap-4">
          <div className="rounded-3xl border-2 border-ink bg-warmwhite p-5 shadow-[0_4px_0_rgba(23,25,22,0.85)]">
            <p className="text-xs font-bold uppercase tracking-wide text-ink-soft">
              Paper execution · {formatEt(execution.executedAt, "full")} ET
            </p>
            {execution.kind === "FILL" ? (
              <>
                <p className="tnum mt-3 font-display text-3xl uppercase text-forest">
                  {execution.filledTokens} {execution.symbol} filled
                </p>
                <p className="tnum mt-1 text-sm font-semibold text-ink-soft">
                  avg {formatUsd(execution.avgPriceUsd ?? 0)} · {execution.side}
                </p>
                <dl className="tnum mt-4 grid grid-cols-3 gap-2 text-center">
                  <div className="rounded-xl border-2 border-line bg-paper px-2 py-2">
                    <dt className="text-[10px] font-bold uppercase text-ink-soft">Fee</dt>
                    <dd className="text-sm font-bold text-ink">{formatUsd(execution.feeUsd)}</dd>
                  </div>
                  <div className="rounded-xl border-2 border-line bg-paper px-2 py-2">
                    <dt className="text-[10px] font-bold uppercase text-ink-soft">Slippage</dt>
                    <dd className="text-sm font-bold text-ink">{formatUsd(execution.slippageUsd)}</dd>
                  </div>
                  <div className="rounded-xl border-2 border-forest bg-forest-mist px-2 py-2">
                    <dt className="text-[10px] font-bold uppercase text-forest-deep">Est. total cost</dt>
                    <dd className="text-sm font-bold text-forest-deep">{formatUsd(execution.totalCostUsd)}</dd>
                  </div>
                </dl>
                {execution.costBreakdown.length > 0 && (
                  <div className="mt-4">
                    <p className="text-[10px] font-bold uppercase tracking-wide text-ink-soft">
                      Estimated cost breakdown
                    </p>
                    <CostBreakdownChart costs={execution.costBreakdown} height={140} />
                  </div>
                )}
              </>
            ) : (
              <>
                <p className="mt-3 font-display text-3xl uppercase text-ink">
                  {execution.kind === "REFUSAL" ? "Refused" : "No order"}
                </p>
                <p className="mt-1 text-sm font-semibold text-ink-soft">
                  {execution.kind === "REFUSAL" ? "The risk engine blocked execution." : "Nothing to execute."}
                </p>
              </>
            )}
            <p className="mt-4 rounded-2xl border-2 border-dashed border-line-strong bg-paper px-4 py-3 text-xs leading-relaxed text-ink-soft">
              {execution.note}
            </p>
          </div>

          {priceSeries && priceSeries.points.length >= 2 ? (
            <div className="overflow-hidden rounded-3xl border-2 border-ink bg-warmwhite shadow-[0_4px_0_rgba(23,25,22,0.85)]">
              <p className="border-b-2 border-line bg-paper px-5 py-3 text-xs font-bold uppercase tracking-wide text-ink-soft">
                {instrument?.symbol} price · event markers
              </p>
              <div className="px-3 py-4">
                <PriceEventChart series={priceSeries} compact />
                <ul className="mt-2 grid grid-cols-1 gap-1 px-2">
                  {priceSeries.markers.map((m) => (
                    <li key={m.t + m.label} className="flex items-center gap-2 text-[11px] font-semibold text-ink-soft">
                      <span
                        className={cn(
                          "h-2.5 w-2.5 rounded-full border border-ink",
                          m.kind === "EVENT" ? "bg-gold" : "bg-warmwhite"
                        )}
                        aria-hidden="true"
                      />
                      <span className="tnum">{formatEt(m.t, "full")} ET</span>
                      <span>{m.label}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : (
            <p className="rounded-3xl border-2 border-dashed border-line-strong bg-paper px-5 py-4 text-sm font-semibold text-ink-soft">
              INSUFFICIENT_DATA. One stored price is not a history.
            </p>
          )}
        </div>
      </section>

      {/* ── 7 · verification ───────────────────────────────── */}
      <section className="grid grid-cols-1 gap-3">
        <SectionTitle icon={Stamp} step="07">Can the result be verified?</SectionTitle>
        <ReceiptCard receipt={receipt} />
        <p className="text-xs text-ink-soft">
          {DECISION_META[decision.state].plain}
        </p>
      </section>
    </div>
  );
}
