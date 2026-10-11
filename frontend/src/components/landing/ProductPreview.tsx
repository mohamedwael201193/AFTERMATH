"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowRight, Pause, Play, Check } from "lucide-react";
import type { EventBundle } from "@/types/domain";
import { previewDataProvider } from "@/services";
import { SectionHeading } from "@/components/landing/SectionHeading";
import { Reveal } from "@/components/landing/Reveal";
import { DecisionGlyph, RiskMark, FreshnessDot } from "@/components/artwork/StatusGlyphs";
import { TickerIcon } from "@/components/artwork/TickerIcon";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { formatEt, formatUsd, formatConfidence } from "@/lib/format";

const STEPS = [
  { id: 0, label: "Event", hint: "what happened" },
  { id: 1, label: "Evidence", hint: "what supports it" },
  { id: 2, label: "Judgment", hint: "what the AI decided" },
  { id: 3, label: "Risk", hint: "what could go wrong" },
  { id: 4, label: "Outcome", hint: "what happened next" },
] as const;

/**
 * The product in action — a sample event walked through the real pipeline
 * stages, rendered from the actual preview data provider. Explicitly an
 * illustrative preview; never presented as verified live trading.
 */
export function ProductPreview({ onOpenDashboard }: { onOpenDashboard: () => void }) {
  const [bundle, setBundle] = useState<EventBundle | null>(null);
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let alive = true;
    previewDataProvider.getEventBundle("EV-1001").then((b) => {
      if (alive) setBundle(b);
    });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (timer.current) clearInterval(timer.current);
    if (playing) {
      timer.current = setInterval(() => {
        setStep((s) => (s + 1) % STEPS.length);
      }, 2600);
    }
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [playing]);

  const ev = bundle?.event;
  const decision = bundle?.decision;
  const risk = bundle?.risk;
  const execution = bundle?.execution;
  const receipt = bundle?.receipt;
  const evidence = bundle?.evidence ?? [];

  return (
    <section className="px-4 py-16 sm:px-8 sm:py-24 lg:px-12">
      <SectionHeading
        eyebrow="The product in action"
        title={
          <>
            Watch one event
            <br />
            become one decision.
          </>
        }
        aside="a sample event, walked end to end"
        intro="This is the actual product surface — an illustrative event moving through evidence, judgment, risk, and an auditable outcome. Values are preview data, clearly labeled as such."
      />

      <Reveal delay={0.1} className="mt-12">
        <div className="mx-auto max-w-5xl overflow-hidden rounded-[2rem] border-2 border-ink bg-warmwhite shadow-[0_8px_0_rgba(23,25,22,0.9)]">
          {/* window bar */}
          <div className="flex items-center gap-3 border-b-2 border-ink bg-paper px-4 py-3 sm:px-6">
            <span className="flex gap-1.5" aria-hidden="true">
              <span className="h-3 w-3 rounded-full border border-ink bg-risk-soft" />
              <span className="h-3 w-3 rounded-full border border-ink bg-warn-soft" />
              <span className="h-3 w-3 rounded-full border border-ink bg-forest-mist" />
            </span>
            <span className="ml-2 truncate rounded-full border border-line-strong bg-warmwhite px-3 py-1 text-[11px] font-semibold text-ink-soft">
              Preview workspace · illustrative data · EV-1001
            </span>
            <button
              onClick={() => setPlaying((p) => !p)}
              aria-pressed={playing}
              className="ml-auto inline-flex items-center gap-1.5 rounded-full border-2 border-ink bg-warmwhite px-3 py-1 text-xs font-bold text-ink transition-colors hover:bg-forest-mist"
            >
              {playing ? (
                <>
                  <Pause className="h-3.5 w-3.5" aria-hidden="true" /> Pause
                </>
              ) : (
                <>
                  <Play className="h-3.5 w-3.5" aria-hidden="true" /> Play
                </>
              )}
            </button>
          </div>

          <div className="grid lg:grid-cols-[240px_1fr]">
            {/* stepper */}
            <nav
              aria-label="Pipeline stages"
              className="flex gap-2 overflow-x-auto border-b-2 border-line bg-paper p-4 scroll-slim lg:flex-col lg:overflow-visible lg:border-b-0 lg:border-r-2 lg:p-5"
            >
              {STEPS.map((s) => (
                <button
                  key={s.id}
                  onClick={() => setStep(s.id)}
                  aria-current={step === s.id ? "step" : undefined}
                  className={cn(
                    "flex shrink-0 items-center gap-3 rounded-2xl border-2 px-3.5 py-2.5 text-left transition-all lg:w-full",
                    step === s.id
                      ? "border-ink bg-forest text-paper shadow-[0_3px_0_rgba(23,25,22,0.85)]"
                      : "border-line bg-warmwhite text-ink hover:border-ink"
                  )}
                >
                  <span
                    className={cn(
                      "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 text-xs font-bold",
                      step === s.id ? "border-paper/60 bg-paper/15 text-paper" : "border-ink bg-forest-mist text-forest-deep"
                    )}
                  >
                    {s.id + 1}
                  </span>
                  <span className="whitespace-nowrap">
                    <span className="block text-sm font-bold leading-tight">{s.label}</span>
                    <span className={cn("block text-[11px] leading-tight", step === s.id ? "text-paper/75" : "text-ink-soft")}>
                      {s.hint}
                    </span>
                  </span>
                </button>
              ))}
            </nav>

            {/* stage content */}
            <div className="min-h-[320px] p-5 sm:p-7" aria-live="polite">
              {!bundle && (
                <div className="flex h-full min-h-[260px] items-center justify-center text-sm font-semibold text-ink-soft">
                  <span className="flex items-center gap-2">
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-ink-soft border-t-ink" aria-hidden="true" />
                    Loading the sample record…
                  </span>
                </div>
              )}

              {bundle && step === 0 && ev && (
                <div>
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="inline-flex shrink-0 items-center justify-center rounded-full border-2 border-ink bg-warmwhite sticker-shadow-sm" style={{ width: 52, height: 52 }}>
                      <TickerIcon symbol="NVDA" kind="EQUITY_TOKEN" size={34} />
                    </span>
                    <div>
                      <p className="text-xs font-bold uppercase tracking-[0.14em] text-ink-soft">
                        Earnings · {formatEt(ev.occurredAt, "full")} ET
                      </p>
                      <h3 className="mt-1 max-w-xl text-lg font-bold leading-snug text-ink sm:text-xl">
                        {ev.headline}
                      </h3>
                    </div>
                  </div>
                  <p className="mt-4 max-w-2xl text-sm leading-relaxed text-ink-soft sm:text-base">
                    {ev.summary}
                  </p>
                  <div className="mt-5 flex flex-wrap gap-2 text-xs font-semibold">
                    <span className="rounded-full border border-line-strong bg-paper px-3 py-1.5 text-ink-soft">
                      Source · {ev.source.name}
                    </span>
                    <span className="rounded-full border border-line-strong bg-paper px-3 py-1.5 text-ink-soft tnum">
                      Evidence completeness · 0.94
                    </span>
                  </div>
                </div>
              )}

              {bundle && step === 1 && (
                <ul className="grid gap-3">
                  {evidence.slice(0, 3).map((e) => (
                    <li key={e.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-2xl border-2 border-line bg-paper px-4 py-3">
                      <FreshnessDot freshness={e.freshness} />
                      <span className="text-sm font-bold text-ink">{e.label}</span>
                      <span className="text-sm font-semibold text-forest tnum">{e.value}</span>
                      <span className="ml-auto text-[11px] font-semibold text-ink-soft">
                        {e.source.name} · {formatEt(e.capturedAt)} ET
                      </span>
                    </li>
                  ))}
                  <li className="mt-1 text-xs text-ink-soft">
                    + {evidence.length - 3} more records in the dashboard — each with source,
                    timestamp, units, and why it matters.
                  </li>
                </ul>
              )}

              {bundle && step === 2 && decision && (
                <div>
                  <div className="flex items-center gap-4 rounded-3xl border-2 border-ink bg-forest-mist p-5 shadow-[0_4px_0_rgba(23,25,22,0.85)]">
                    <DecisionGlyph state={decision.state} size={44} />
                    <div>
                      <p className="font-display text-xl uppercase tracking-tight text-forest-deep">
                        {decision.state}
                      </p>
                      <p className="text-sm font-semibold text-ink-soft tnum">
                        Confidence · {formatConfidence(decision.confidence)}
                      </p>
                    </div>
                  </div>
                  <p className="mt-4 max-w-2xl text-sm leading-relaxed text-ink sm:text-base">
                    {decision.plainLanguage}
                  </p>
                  {decision.proposedAction && (
                    <p className="mt-3 inline-flex items-center gap-2 rounded-full border-2 border-ink bg-warmwhite px-4 py-2 text-sm font-bold text-ink tnum">
                      Proposed · {decision.proposedAction.side} {decision.proposedAction.sizeTokens}{" "}
                      {decision.proposedAction.symbol} · ≈ {formatUsd(decision.proposedAction.notionalUsd)}
                    </p>
                  )}
                </div>
              )}

              {bundle && step === 3 && risk && (
                <div>
                  <p className="text-sm font-bold uppercase tracking-[0.14em] text-ink-soft">
                    Deterministic checks · the AI cannot overrule these
                  </p>
                  <ul className="mt-4 grid gap-2.5">
                    {risk.checks.slice(0, 4).map((c) => (
                      <li key={c.id} className="flex items-center gap-3 rounded-2xl border-2 border-line bg-paper px-4 py-3">
                        <RiskMark status={c.status} size={22} />
                        <span className="text-sm font-bold text-ink">{c.label}</span>
                        <span className="ml-auto text-[11px] font-semibold text-ink-soft tnum">
                          {c.observed}
                        </span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-4 text-sm text-ink-soft">
                    Full risk detail — including limits and what was observed —
                    is one click away in the dashboard.
                  </p>
                </div>
              )}

              {bundle && step === 4 && execution && receipt && (
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="rounded-3xl border-2 border-ink bg-warmwhite p-5 shadow-[0_4px_0_rgba(23,25,22,0.85)]">
                    <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.14em] text-ink-soft">
                      <Check className="h-4 w-4 text-forest" aria-hidden="true" /> Paper outcome
                    </p>
                    <p className="mt-3 flex items-center gap-2.5 font-display text-2xl uppercase text-forest tnum">
                      <TickerIcon symbol={execution.symbol} kind="EQUITY_TOKEN" size={30} />
                      Filled
                    </p>
                    <p className="mt-1 text-sm text-ink-soft tnum">
                      {execution.filledTokens} {execution.symbol} @ {formatUsd(execution.avgPriceUsd ?? 0)}
                    </p>
                    <p className="mt-3 text-xs text-ink-soft tnum">
                      Est. costs {formatUsd(execution.totalCostUsd)} · fee {formatUsd(execution.feeUsd)} · slippage {formatUsd(execution.slippageUsd)}
                    </p>
                  </div>
                  <div className="rounded-3xl border-2 border-ink bg-paper p-5 shadow-[0_4px_0_rgba(23,25,22,0.85)]">
                    <p className="text-xs font-bold uppercase tracking-[0.14em] text-ink-soft">
                      Receipt · simulated presentation
                    </p>
                    <p className="mt-3 font-mono text-sm font-bold tracking-wide text-forest-deep tnum">
                      {receipt.digestPreview}
                    </p>
                    <p className="mt-2 text-xs leading-relaxed text-ink-soft">
                      In production, the digest and Ed25519 signature can be checked
                      outside AFTERMATH with the published public key. Receipts are not
                      externally timestamped.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* footer CTA */}
          <div className="flex flex-wrap items-center gap-3 border-t-2 border-ink bg-forest px-5 py-4 sm:px-7">
            <p className="text-sm font-semibold text-paper/90">
              Explore the full record — evidence, reasoning, limits, receipt — in the dashboard.
            </p>
            <Button
              onClick={onOpenDashboard}
              className="ml-auto h-10 gap-1.5 rounded-full bg-paper px-5 text-sm font-bold text-forest-deep shadow-[0_3px_0_rgba(23,25,22,0.9)] transition-transform hover:-translate-y-0.5"
            >
              Open dashboard
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Button>
          </div>
        </div>
      </Reveal>
    </section>
  );
}
