"use client";

import Image from "next/image";
import { ShieldX, Lock, FileCheck2, Landmark, Hourglass } from "lucide-react";
import { SectionHeading } from "@/components/landing/SectionHeading";
import { Reveal } from "@/components/landing/Reveal";
import { ART } from "@/components/artwork/artAssets";
import { Sparkle } from "@/components/artwork/Decor";

const PRINCIPLES = [
  {
    icon: ShieldX,
    title: "A refusal is a result",
    text: "When evidence is missing, stale, or contradictory, the correct outcome is an explained refusal — not a forced trade. AFTERMATH treats those refusals as successes and records them like any other decision.",
  },
  {
    icon: Lock,
    title: "The model can't bend the rules",
    text: "Risk limits live in deterministic code, not in a prompt. The AI proposes; the engine disposes. Missing evidence, thin books, or stale prices shrink or block an order regardless of confidence.",
  },
  {
    icon: FileCheck2,
    title: "Receipts outlive the interface",
    text: "Every outcome is written as a receipt with a digest, a signature, and the time AFTERMATH recorded it, chained to the receipt before it. An outsider can check the signature and the chain with the public key. The recorded time is AFTERMATH's own clock, not an external timestamp.",
  },
  {
    icon: Hourglass,
    title: "Paper honesty",
    text: "Simulated fills prove the pipeline works, not that it profits. Results, estimates, and unresolved questions are labeled differently — and nothing in this preview claims to be live trading.",
  },
];

/**
 * Trust and transparency — the honest half of the story, told on a deep
 * forest panel with the risk guardian and receipt artwork.
 */
export function TrustSection() {
  return (
    <section id="trust" className="px-4 py-16 sm:px-8 sm:py-24 lg:px-12">
      <SectionHeading
        eyebrow="Trust & safety"
        title={
          <>
            Built to say
            <span className="text-risk"> no</span>
            <br />
            when the facts say no.
          </>
        }
        aside="why the guardrails matter more than the signals"
        intro="The interesting part of an evidence-governed system is not what it lets you do — it's what it refuses to do, and how it proves that it did."
      />

      <Reveal delay={0.12} className="mt-12">
        <div className="on-forest relative overflow-hidden rounded-[2.5rem] border-2 border-ink bg-forest-deep p-6 shadow-[0_8px_0_rgba(23,25,22,0.9)] sm:p-10">
          {/* faint texture + sparkles */}
          <div className="texture-paper texture-paper--deep absolute inset-0 rounded-[2.5rem]" aria-hidden="true" />
          <Sparkle className="absolute right-8 top-8" size={22} color="#C9A227" />
          <Sparkle className="absolute bottom-10 left-8 hidden sm:block" size={16} color="#4C9A6A" />

          <div className="relative grid gap-10 lg:grid-cols-2">
            {/* left: guardian art + first two principles */}
            <div>
              <div
                className="animate-float-y-soft mx-auto max-w-[300px] sm:max-w-[340px]"
                style={{ filter: "drop-shadow(8px 10px 0 rgba(4,54,28,0.55))" }}
              >
                <Image
                  src={ART.riskGuardian.src}
                  alt={ART.riskGuardian.alt}
                  width={ART.riskGuardian.width}
                  height={ART.riskGuardian.height}
                  loading="lazy"
                  className="h-auto w-full select-none"
                  draggable={false}
                />
              </div>
              <ul className="mt-6 grid gap-5">
                {PRINCIPLES.slice(0, 2).map((p) => (
                  <li key={p.title} className="flex gap-4">
                    <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border-2 border-paper/60 bg-forest text-paper">
                      <p.icon className="h-5 w-5" aria-hidden="true" />
                    </span>
                    <div>
                      <h3 className="text-base font-bold text-paper">{p.title}</h3>
                      <p className="mt-1.5 text-sm leading-relaxed text-paper/80">{p.text}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            {/* right: receipt art + remaining principles */}
            <div className="lg:pt-2">
              <ul className="grid gap-5">
                {PRINCIPLES.slice(2).map((p) => (
                  <li key={p.title} className="flex gap-4">
                    <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border-2 border-paper/60 bg-forest text-paper">
                      <p.icon className="h-5 w-5" aria-hidden="true" />
                    </span>
                    <div>
                      <h3 className="text-base font-bold text-paper">{p.title}</h3>
                      <p className="mt-1.5 text-sm leading-relaxed text-paper/80">{p.text}</p>
                    </div>
                  </li>
                ))}
              </ul>
              <div
                className="animate-float-y mt-8 mx-auto max-w-[240px] sm:max-w-[280px]"
                style={{ filter: "drop-shadow(8px 10px 0 rgba(4,54,28,0.55))" }}
              >
                <Image
                  src={ART.receiptSeal.src}
                  alt={ART.receiptSeal.alt}
                  width={ART.receiptSeal.width}
                  height={ART.receiptSeal.height}
                  loading="lazy"
                  className="h-auto w-full select-none"
                  draggable={false}
                />
              </div>
              <p className="mt-5 flex items-center justify-center gap-2 text-center font-editorial text-lg italic text-paper/85">
                <Landmark className="h-4 w-4 shrink-0" aria-hidden="true" />
                ( decisions you can check without trusting us )
              </p>
            </div>
          </div>
        </div>
      </Reveal>
    </section>
  );
}
