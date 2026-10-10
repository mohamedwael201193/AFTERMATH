"use client";

import Image from "next/image";
import { Bell, MoonStar, HelpCircle, TrendingDown } from "lucide-react";
import { SectionHeading } from "@/components/landing/SectionHeading";
import { Reveal } from "@/components/landing/Reveal";
import { HandArrow } from "@/components/artwork/Decor";
import { ART } from "@/components/artwork/artAssets";

/** Fraction positions on a 24h ET axis. */
const POS = {
  event: 13, // 03:12 ET
  sessionStart: 39.6, // 09:30 ET
  sessionEnd: 66.7, // 16:00 ET
};

const PROBLEMS = [
  {
    icon: Bell,
    title: "A headline lands at 3 AM",
    text: "News does not wait for the opening bell. By the time cash markets wake up, the story — and the price — may have moved twice.",
  },
  {
    icon: MoonStar,
    title: "The reference is asleep",
    text: "US cash equities quote during session hours. Tokenized equivalents keep trading around the clock on their own liquidity.",
  },
  {
    icon: HelpCircle,
    title: "Signals are incomplete",
    text: "One price moved, the other didn't, and both can't be right. Without fresh evidence, acting is guessing.",
  },
  {
    icon: TrendingDown,
    title: "Acting blind is expensive",
    text: "Thin books, wide spreads, and overnight gaps punish impulsive orders. A wrong entry at 3 AM costs real money by 9:30.",
  },
];

/**
 * The after-hours problem — an illustrated 24-hour timeline showing an
 * event landing while the reference market is asleep.
 */
export function ProblemSection() {
  return (
    <section id="product" className="px-4 py-16 sm:px-8 sm:py-24 lg:px-12">
      <div className="grid items-start gap-10 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <SectionHeading
            eyebrow="The problem"
            title={
              <>
                The market closed.
                <br />
                Your exposure
                <span className="text-forest-soft"> didn't.</span>
              </>
            }
            aside="tokenized stocks trade while the reference sleeps"
            intro="Tokenized US stocks and their perpetual cousins change price around the clock — including nights and weekends, when the underlying equity market quotes nothing at all."
          />
        </div>
        <Reveal delay={0.15} className="lg:col-span-5">
          <div className="relative mx-auto max-w-sm lg:mt-2">
            <div
              className="animate-float-y-soft"
              style={{ filter: "drop-shadow(8px 10px 0 rgba(23,25,22,0.22))" }}
            >
              <Image
                src={ART.afterHours.src}
                alt={ART.afterHours.alt}
                width={ART.afterHours.width}
                height={ART.afterHours.height}
                className="h-auto w-full select-none"
                loading="lazy"
                draggable={false}
              />
            </div>
          </div>
        </Reveal>
      </div>

      {/* 24-hour timeline */}
      <Reveal delay={0.1} className="mt-12 sm:mt-16">
        <figure className="overflow-hidden rounded-3xl border-2 border-ink bg-warmwhite shadow-[0_6px_0_rgba(23,25,22,0.9)]">
          <div className="relative h-64 sm:h-72 lg:h-80">
            {/* SVG scene: night shades, session band, price path with gap */}
            <svg
              className="absolute inset-0 h-full w-full"
              viewBox="0 0 1000 320"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              {/* night zones */}
              <rect x="0" y="0" width={POS.sessionStart * 10} height="320" fill="#EFECE0" />
              <rect x={POS.sessionEnd * 10} y="0" width={1000 - POS.sessionEnd * 10} height="320" fill="#EFECE0" />
              {/* stars in night zones */}
              <g fill="#B9B9A6">
                <circle cx="60" cy="46" r="3" /><circle cx="150" cy="30" r="2.2" /><circle cx="250" cy="60" r="2.6" />
                <circle cx="860" cy="40" r="2.6" /><circle cx="930" cy="66" r="3" /><circle cx="975" cy="34" r="2.2" />
              </g>
              {/* cash session band */}
              <rect
                x={POS.sessionStart * 10}
                y="0"
                width={(POS.sessionEnd - POS.sessionStart) * 10}
                height="320"
                fill="#E3ECDF"
                stroke="#086B32"
                strokeWidth="2"
                strokeDasharray="6 6"
              />
              {/* horizontal gridlines */}
              {[70, 120, 170, 220].map((y) => (
                <line key={y} x1="0" x2="1000" y1={y} y2={y} stroke="#D8D8CA" strokeWidth="1" strokeDasharray="2 6" />
              ))}
              {/* reference close + reopen dashed verticals */}
              <line x1={POS.sessionEnd * 10} x2={POS.sessionEnd * 10} y1="30" y2="290" stroke="#65695F" strokeWidth="2" strokeDasharray="7 7" />
              <line x1={POS.sessionStart * 10} x2={POS.sessionStart * 10} y1="30" y2="290" stroke="#086B32" strokeWidth="2" strokeDasharray="7 7" />
              {/* tokenized price path: calm night, jumps at event, keeps moving after close */}
              <path
                d="M0 200 C 40 196, 70 206, 110 199 C 130 196, 132 194, 134 193 L 135 190
                   L 136 150 C 160 142, 190 156, 230 148 C 280 140, 330 152, 380 144
                   C 420 138, 450 146, 480 140 C 500 136, 520 132, 540 138
                   C 580 148, 620 158, 667 152 L 668 152
                   C 700 146, 740 158, 790 150 C 840 143, 890 156, 1000 148"
                fill="none"
                stroke="#086B32"
                strokeWidth="5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              {/* the gap: reference frozen at close vs token price now */}
              <line x1="668" x2="668" y1="152" y2="238" stroke="#B3261E" strokeWidth="4" strokeDasharray="8 6" />
              <path d="M668 152 l-7 10 h14 Z" fill="#B3261E" />
              <path d="M668 238 l-7 -10 h14 Z" fill="#B3261E" />
              {/* event marker */}
              <line x1="135" x2="135" y1="60" y2="190" stroke="#171916" strokeWidth="3" strokeDasharray="5 6" />
              <circle cx="135" cy="150" r="9" fill="#C9A227" stroke="#171916" strokeWidth="3" />
            </svg>

            {/* HTML annotations (real text, responsive) */}
            <div className="pointer-events-none absolute inset-0 text-[11px] font-bold sm:text-xs">
              <div className="absolute left-[4%] top-3 flex items-center gap-1.5 rounded-full border border-line-strong bg-paper px-2.5 py-1 text-ink-soft">
                <MoonStar className="h-3.5 w-3.5" aria-hidden="true" /> Night session · token only
              </div>
              <div className="absolute top-3 hidden -translate-x-1/2 items-center gap-1.5 rounded-full border-2 border-forest bg-warmwhite px-2.5 py-1 text-forest-deep sm:flex" style={{ left: "45%" }}>
                US cash session · 09:30–16:00 ET
              </div>
              <div className="absolute left-[14%] top-[16%] max-w-[10rem] -translate-x-1/2 rounded-2xl border-2 border-ink bg-warn-soft px-3 py-2 text-center shadow-[0_3px_0_rgba(23,25,22,0.85)]">
                <span className="block tnum">03:12 ET</span>
                <span className="font-semibold text-ink-soft">headline lands — no reference quote</span>
              </div>
              <div className="absolute right-[8%] top-[38%] max-w-[9.5rem] rounded-2xl border-2 border-ink bg-risk-soft px-3 py-2 text-center shadow-[0_3px_0_rgba(23,25,22,0.85)]">
                <span className="block text-risk">Overnight gap</span>
                <span className="font-semibold text-ink-soft">token drifted from the frozen close</span>
              </div>
              <div className="absolute bottom-3 left-3 rounded-full border border-line-strong bg-paper px-2.5 py-1 text-ink-soft">
                Tokenized price · moves 24/7
              </div>
            </div>
          </div>
          <figcaption className="border-t-2 border-line bg-paper px-4 py-3 text-xs text-ink-soft sm:px-6">
            An illustrative 24-hour timeline in US Eastern time. The green path is the
            tokenized instrument; the dashed red span is the gap that opens while the
            reference market is closed.
          </figcaption>
        </figure>
      </Reveal>

      {/* problem cards */}
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {PROBLEMS.map((p, i) => (
          <Reveal key={p.title} delay={0.08 * i}>
            <article className="group h-full rounded-3xl border-2 border-ink bg-warmwhite p-5 shadow-[0_4px_0_rgba(23,25,22,0.9)] transition-transform duration-200 hover:-translate-y-1">
              <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl border-2 border-ink bg-forest-mist text-forest-deep">
                <p.icon className="h-5 w-5" aria-hidden="true" />
              </span>
              <h3 className="mt-4 text-base font-bold leading-snug text-ink">{p.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-soft">{p.text}</p>
            </article>
          </Reveal>
        ))}
      </div>

      <Reveal delay={0.1} className="mt-8 flex items-center gap-3">
        <HandArrow width={54} className="hidden sm:block" />
        <p className="font-editorial text-lg italic text-ink-soft">
          This is the gap AFTERMATH was built to govern.
        </p>
      </Reveal>
    </section>
  );
}
