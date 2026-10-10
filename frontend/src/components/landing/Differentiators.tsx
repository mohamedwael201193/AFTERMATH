"use client";

import {
  FileSearch,
  ShieldAlert,
  SlidersHorizontal,
  Ticket,
  Fingerprint,
  Scale,
} from "lucide-react";
import { SectionHeading } from "@/components/landing/SectionHeading";
import { Reveal } from "@/components/landing/Reveal";

const FEATURES = [
  {
    icon: FileSearch,
    title: "Verified evidence",
    text: "Claims are tied to traceable source records — with timestamps, units, and freshness you can inspect yourself.",
    accent: "forest",
  },
  {
    icon: ShieldAlert,
    title: "Adversarial checks",
    text: "Suspicious headlines and unsupported numbers can lower confidence or kill a decision before any order exists.",
    accent: "cream",
  },
  {
    icon: SlidersHorizontal,
    title: "Independent risk controls",
    text: "A deterministic engine owns the limits. The language model suggests; it can never overrule.",
    accent: "cream",
  },
  {
    icon: Ticket,
    title: "Transparent paper execution",
    text: "Fills, fees, and slippage are estimated in the open. Refusals are recorded with the exact check that failed.",
    accent: "forest",
  },
  {
    icon: Fingerprint,
    title: "Verifiable records",
    text: "Every outcome becomes a receipt — a structure designed to be checked independently, outside this interface.",
    accent: "cream",
  },
  {
    icon: Scale,
    title: "Honest evaluation",
    text: "Observed results, estimates, and open questions are labeled differently. Nothing dresses up as proven profit.",
    accent: "cream",
  },
] as const;

/**
 * What makes AFTERMATH different — six real mechanisms, no invented badges
 * or benchmark claims. Two forest cards break the grid rhythm.
 */
export function Differentiators() {
  return (
    <section className="px-4 py-16 sm:px-8 sm:py-24 lg:px-12">
      <SectionHeading
        eyebrow="The difference"
        title={
          <>
            Not another signal.
            <br />
            A chain of proof.
          </>
        }
        aside="what actually makes the system different"
        intro="Most tools show you a direction and hope you trust it. AFTERMATH shows you the evidence, the reasoning, the limits that bind it, and the receipt that remains."
      />

      <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((f, i) => (
          <Reveal key={f.title} delay={0.07 * i}>
            <article
              className={
                f.accent === "forest"
                  ? "group h-full rounded-3xl border-2 border-ink bg-forest p-6 text-paper shadow-[0_5px_0_rgba(23,25,22,0.9)] transition-transform duration-200 hover:-translate-y-1"
                  : "group h-full rounded-3xl border-2 border-ink bg-warmwhite p-6 shadow-[0_5px_0_rgba(23,25,22,0.9)] transition-transform duration-200 hover:-translate-y-1"
              }
            >
              <span
                className={
                  f.accent === "forest"
                    ? "inline-flex h-11 w-11 items-center justify-center rounded-2xl border-2 border-paper/70 bg-forest-deep text-paper"
                    : "inline-flex h-11 w-11 items-center justify-center rounded-2xl border-2 border-ink bg-forest-mist text-forest-deep"
                }
              >
                <f.icon className="h-5 w-5" aria-hidden="true" />
              </span>
              <h3
                className={
                  f.accent === "forest"
                    ? "mt-4 text-lg font-bold leading-snug text-paper"
                    : "mt-4 text-lg font-bold leading-snug text-ink"
                }
              >
                {f.title}
              </h3>
              <p
                className={
                  f.accent === "forest"
                    ? "mt-2 text-sm leading-relaxed text-paper/85"
                    : "mt-2 text-sm leading-relaxed text-ink-soft"
                }
              >
                {f.text}
              </p>
            </article>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
