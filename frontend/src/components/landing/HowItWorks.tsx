"use client";

import { SectionHeading } from "@/components/landing/SectionHeading";
import { Reveal } from "@/components/landing/Reveal";
import {
  EventGlyph,
  EvidenceGlyph,
  JudgmentGlyph,
  RiskGlyph,
  PaperGlyph,
  ReceiptGlyph,
} from "@/components/artwork/WorkflowGlyphs";

const STAGES = [
  {
    glyph: EventGlyph,
    step: "01",
    title: "An event lands",
    text: "A headline, filing, or price shock arrives — at any hour — and gets tied to one verified instrument.",
  },
  {
    glyph: EvidenceGlyph,
    step: "02",
    title: "Evidence is captured",
    text: "Every important fact is recorded with its source, timestamp, value, units, and freshness. Nothing is invented.",
  },
  {
    glyph: JudgmentGlyph,
    step: "03",
    title: "The model is gated",
    text: "A model is called only after a qualifying event and a usable book pass the evidence gate. Otherwise the cycle records a refusal and does not invent a decision.",
  },
  {
    glyph: RiskGlyph,
    step: "04",
    title: "Risk checks it",
    text: "A deterministic engine re-checks freshness, depth, costs, and limits. It can shrink or refuse — the AI cannot overrule it.",
  },
  {
    glyph: PaperGlyph,
    step: "05",
    title: "Paper, not promises",
    text: "Approved orders are simulated with visible costs and fills. Refusals are recorded with their reasons.",
  },
  {
    glyph: ReceiptGlyph,
    step: "06",
    title: "A receipt remains",
    text: "Each outcome becomes an auditable record that could be independently checked outside AFTERMATH.",
  },
];

/**
 * How AFTERMATH works — the six-stage workflow, revealed in sequence as
 * the user scrolls, with a dashed path connecting the stages.
 */
export function HowItWorks() {
  return (
    <section id="how-it-works" className="relative px-4 py-16 sm:px-8 sm:py-24 lg:px-12">
      <SectionHeading
        eyebrow="How it works"
        title={
          <>
            One workflow,
            <br />
            six honest steps.
          </>
        }
        aside="event → evidence → judgment → risk → paper result → receipt"
        align="center"
        intro="No hidden pipeline. Every stage leaves a record, and every record can be inspected in the dashboard."
      />

      <div className="relative mt-12 sm:mt-16">
        {/* connecting dashed path (desktop) */}
        <svg
          aria-hidden="true"
          className="pointer-events-none absolute left-0 right-0 top-16 hidden h-8 w-full lg:block"
          viewBox="0 0 1000 20"
          preserveAspectRatio="none"
        >
          <path
            d="M60 10 C 220 -6, 320 26, 500 10 C 680 -6, 780 26, 940 10"
            fill="none"
            stroke="#B9B9A6"
            strokeWidth="2.5"
            strokeDasharray="8 10"
            strokeLinecap="round"
          />
        </svg>

        <ol className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 lg:gap-6">
          {STAGES.map((stage, i) => (
            <Reveal key={stage.step} delay={0.1 * i}>
              <li className="group relative h-full rounded-3xl border-2 border-ink bg-warmwhite p-6 shadow-[0_5px_0_rgba(23,25,22,0.9)] transition-all duration-200 hover:-translate-y-1 hover:shadow-[0_8px_0_rgba(23,25,22,0.9)]">
                <div className="flex items-start justify-between gap-4">
                  <stage.glyph
                    size={64}
                    className="transition-transform duration-300 group-hover:-rotate-3 group-hover:scale-105"
                  />
                  <span className="font-display text-2xl text-line-strong transition-colors group-hover:text-forest-soft">
                    {stage.step}
                  </span>
                </div>
                <h3 className="mt-5 text-lg font-bold leading-snug text-ink">
                  {stage.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-soft">
                  {stage.text}
                </p>
              </li>
            </Reveal>
          ))}
        </ol>
      </div>

      <Reveal delay={0.15} className="mt-10 text-center">
        <p className="mx-auto max-w-xl font-editorial text-lg italic text-ink-soft">
          If the evidence isn't there, the workflow ends at step four —
          with an explained refusal instead of a forced trade.
        </p>
      </Reveal>
    </section>
  );
}
