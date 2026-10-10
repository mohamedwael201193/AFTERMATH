"use client";

import Image from "next/image";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowDown, LayoutDashboard, MoonStar } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ART } from "@/components/artwork/artAssets";
import { TickerIcon } from "@/components/artwork/TickerIcon";
import type { InstrumentKind } from "@/types/domain";
import { Starburst, Sparkle, Squiggle } from "@/components/artwork/Decor";
import { HighlightOval } from "@/components/artwork/Decor";

/** A small floating evidence snippet chip (original SVG). */
function EvidenceChip({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-xl border-2 border-ink bg-warmwhite px-2.5 py-1.5 sticker-shadow-sm">
      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
        <path d="M3 2 h7 l3 3 v9 H3 Z" fill="#FFFEF8" stroke="#171916" strokeWidth="1.7" strokeLinejoin="round" />
        <path d="M5.5 7 h4 M5.5 9.5 h4" stroke="#65695F" strokeWidth="1.4" strokeLinecap="round" />
        <circle cx="11.4" cy="11" r="3.4" fill="#086B32" stroke="#171916" strokeWidth="1.4" />
        <path d="M10.1 11 l.9 1 1.6-2" stroke="#F5F2E7" strokeWidth="1.1" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="text-[11px] font-bold tracking-tight text-ink">{label}</span>
    </span>
  );
}

/** Real-logo token badge — the same ticker icons the dashboard uses,
    seated in the original AFTERMATH sticker-chip language. */
function LogoChip({
  symbol,
  kind,
  size = 40,
}: {
  symbol: string;
  kind: InstrumentKind;
  size?: number;
}) {
  return (
    <span
      title={`${symbol} · representative instrument (illustrative)`}
      className="inline-flex shrink-0 items-center justify-center rounded-full border-2 border-ink bg-warmwhite sticker-shadow-sm"
      style={{ width: size, height: size }}
    >
      <TickerIcon symbol={symbol} kind={kind} size={Math.round(size * 0.64)} />
    </span>
  );
}

/** Representative tokens shown on the landing page. */
const REPRESENTATIVE_TOKENS: Array<{ symbol: string; kind: InstrumentKind }> = [
  { symbol: "NVDA", kind: "EQUITY_TOKEN" },
  { symbol: "TSLA", kind: "EQUITY_TOKEN" },
  { symbol: "META", kind: "EQUITY_TOKEN" },
  { symbol: "AMZN", kind: "EQUITY_TOKEN" },
  { symbol: "COIN", kind: "EQUITY_TOKEN" },
  { symbol: "QQQ", kind: "INDEX_TOKEN" },
];

/** Mini receipt chip — echoes the product's auditable records. */
function ReceiptChip() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-xl border-2 border-ink bg-forest px-2.5 py-1.5 sticker-shadow-sm">
      <svg width="16" height="18" viewBox="0 0 16 18" aria-hidden="true">
        <path d="M2 1 h12 v13 l-2-1.6 -2 1.6 -2-1.6 -2 1.6 -2-1.6 -2 1.6 Z" fill="#FFFEF8" stroke="#171916" strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M5 5 h6 M5 8 h6 M5 10.5 h3" stroke="#086B32" strokeWidth="1.3" strokeLinecap="round" />
      </svg>
      <span className="text-[11px] font-bold tracking-tight text-paper">SIGNED</span>
    </span>
  );
}

/** Orbit ring with upright chips — chips counter-rotate the ring spin. */
function OrbitRing({
  chips,
  size,
  duration,
  reverse = false,
  className,
}: {
  chips: React.ReactNode[];
  size: string;
  duration: number;
  reverse?: boolean;
  className?: string;
}) {
  const count = chips.length;
  return (
    <div
      aria-hidden="true"
      className={`pointer-events-none absolute ${size} ${className ?? ""}`}
      style={{
        inset: "-9%",
        animation: `orbit ${duration}s linear infinite${reverse ? " reverse" : ""}`,
      }}
    >
      {chips.map((chip, i) => {
        const angle = (360 / count) * i - 60;
        const rad = (angle * Math.PI) / 180;
        const left = 50 + 50 * Math.cos(rad);
        const top = 50 + 50 * Math.sin(rad);
        return (
          <div
            key={i}
            className="absolute"
            style={{
              left: `${left}%`,
              top: `${top}%`,
              transform: "translate(-50%, -50%)",
            }}
          >
            <div
              style={{
                animation: `orbit ${duration}s linear infinite${reverse ? "" : " reverse"}`,
              }}
            >
              <div className="animate-float-y-soft" style={{ ["--tilt" as string]: `${(i % 3) - 1}deg` }}>
                {chip}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function Hero({
  onOpenDashboard,
}: {
  onOpenDashboard: () => void;
}) {
  const reduce = useReducedMotion();

  return (
    <section id="top" className="relative overflow-x-guard px-4 pb-14 pt-8 sm:px-8 sm:pb-20 sm:pt-12 lg:px-12">
      {/* dashed orbit guides behind the art */}
      <svg
        aria-hidden="true"
        className="pointer-events-none absolute right-[-8%] top-[6%] hidden h-[560px] w-[560px] opacity-60 lg:block"
        viewBox="0 0 100 100"
      >
        <circle cx="50" cy="50" r="46" fill="none" stroke="#B9B9A6" strokeWidth="0.5" strokeDasharray="1.5 2.5" />
        <circle cx="50" cy="50" r="34" fill="none" stroke="#D8D8CA" strokeWidth="0.5" strokeDasharray="1 2" />
      </svg>

      <div className="relative grid items-center gap-10 lg:grid-cols-12 lg:gap-4">
        {/* ── copy column ─────────────────────────────────────── */}
        <div className="relative z-10 lg:col-span-7 lg:pr-6">
          <motion.div
            initial={reduce ? false : { opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            className="inline-flex items-center gap-2 rounded-full border-2 border-ink bg-warmwhite px-3.5 py-1.5"
          >
            <Starburst size={18} />
            <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-ink sm:text-xs">
              Evidence-governed trading intelligence
            </span>
          </motion.div>

          <h1 className="mt-5 font-display uppercase leading-[0.88] tracking-[-0.02em] text-forest">
            <motion.span
              className="block text-[clamp(3.4rem,10.5vw,7.6rem)]"
              initial={reduce ? false : { opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
            >
              Markets
            </motion.span>
            <motion.span
              className="relative block w-fit text-[clamp(3.4rem,10.5vw,7.6rem)] text-ink"
              initial={reduce ? false : { opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.16, ease: [0.16, 1, 0.3, 1] }}
            >
              never
              <HighlightOval className="absolute -bottom-2 left-0 w-[min(100%,5.6em)]" color="#C9A227" />
            </motion.span>
            <motion.span
              className="block text-[clamp(3.4rem,10.5vw,7.6rem)]"
              initial={reduce ? false : { opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.24, ease: [0.16, 1, 0.3, 1] }}
            >
              sleep<span className="text-forest-soft">.</span>
              <Sparkle className="ml-2 inline-block h-[0.35em] w-[0.35em] align-baseline" color="#086B32" />
            </motion.span>
          </h1>

          <motion.p
            initial={reduce ? false : { opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.34, ease: [0.16, 1, 0.3, 1] }}
            className="mt-6 font-editorial text-xl italic text-ink-soft sm:text-2xl"
          >
            ( evidence should never be guessed )
          </motion.p>

          <motion.p
            initial={reduce ? false : { opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.42, ease: [0.16, 1, 0.3, 1] }}
            className="mt-4 max-w-lg text-base leading-relaxed text-ink sm:text-lg"
          >
            AFTERMATH connects market events, verifiable evidence, AI reasoning,
            deterministic risk controls, and auditable paper execution into one
            transparent workflow — built for tokenized US stocks and their
            perpetual cousins.
          </motion.p>

          <motion.div
            initial={reduce ? false : { opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}
            className="mt-8 flex flex-wrap items-center gap-3"
          >
            <Button
              onClick={onOpenDashboard}
              className="group h-12 gap-2 rounded-full border-2 border-ink bg-forest px-6 text-base font-bold text-paper shadow-[0_5px_0_rgba(23,25,22,0.9)] transition-all hover:-translate-y-0.5 hover:bg-forest-deep hover:shadow-[0_7px_0_rgba(23,25,22,0.9)] active:translate-y-0.5 active:shadow-[0_2px_0_rgba(23,25,22,0.9)] sm:px-7"
            >
              <LayoutDashboard className="h-5 w-5" aria-hidden="true" />
              Open the dashboard
            </Button>
            <a
              href="#how-it-works"
              className="inline-flex h-12 items-center gap-2 rounded-full border-2 border-ink bg-warmwhite px-6 text-base font-bold text-ink shadow-[0_5px_0_rgba(23,25,22,0.9)] transition-all hover:-translate-y-0.5 hover:bg-paper hover:shadow-[0_7px_0_rgba(23,25,22,0.9)] active:translate-y-0.5 active:shadow-[0_2px_0_rgba(23,25,22,0.9)]"
            >
              See how it works
              <ArrowDown className="h-4 w-4" aria-hidden="true" />
            </a>
          </motion.div>

          <motion.div
            initial={reduce ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.8, delay: 0.62 }}
            className="mt-8 flex flex-wrap items-center gap-2 text-xs font-semibold"
          >
            <span className="inline-flex items-center gap-1.5 rounded-full border border-line-strong bg-paper px-3 py-1.5 text-ink-soft">
              <span className="h-2 w-2 rounded-full bg-warn" aria-hidden="true" />
              Preview workspace · illustrative data
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-line-strong bg-paper px-3 py-1.5 text-ink-soft">
              <MoonStar className="h-3.5 w-3.5 text-forest" aria-hidden="true" />
              US cash market closed · tokenized markets open
            </span>
          </motion.div>

          {/* representative token badges — the real ticker logos, same source
              chain as the dashboard */}
          <motion.div
            initial={reduce ? false : { opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.72 }}
            className="mt-5 flex flex-wrap items-center gap-x-3 gap-y-2"
          >
            <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-ink-soft">
              Representative tokens
            </span>
            <span className="flex flex-wrap items-center gap-2">
              {REPRESENTATIVE_TOKENS.map((t) => (
                <LogoChip key={t.symbol} symbol={t.symbol} kind={t.kind} size={36} />
              ))}
              <span className="text-[11px] font-bold text-ink-soft">+5</span>
            </span>
          </motion.div>
        </div>

        {/* ── sentinel column ─────────────────────────────────── */}
        <div className="relative mx-auto w-full max-w-[340px] sm:max-w-[420px] lg:col-span-5 lg:-ml-10 lg:max-w-none">
          <motion.div
            initial={reduce ? false : { opacity: 0, scale: 0.86, rotate: 2 }}
            animate={{ opacity: 1, scale: 1, rotate: -2 }}
            transition={{ type: "spring", stiffness: 60, damping: 12, delay: 0.2 }}
            className="relative aspect-[3/4] w-full"
          >
            {/* orbit rings */}
            <OrbitRing
              size="aspect-square"
              duration={30}
              chips={[
                <LogoChip key="nvda" symbol="NVDA" kind="EQUITY_TOKEN" size={48} />,
                <EvidenceChip key="ev" label="8-K filed" />,
                <ReceiptChip key="rc" />,
              ]}
            />
            <OrbitRing
              size="aspect-square"
              duration={48}
              reverse
              className="hidden sm:block"
              chips={[
                <LogoChip key="tsla" symbol="TSLA" kind="EQUITY_TOKEN" size={38} />,
                <LogoChip key="coin" symbol="COIN" kind="EQUITY_TOKEN" size={38} />,
                <Starburst key="sb" size={26} color="#C9A227" />,
                <Sparkle key="sp" size={22} color="#086B32" />,
              ]}
            />

            {/* the Evidence Sentinel */}
            <div className="absolute inset-0 flex items-center justify-center">
              <div
                className="animate-float-y w-[86%]"
                style={{ filter: "drop-shadow(10px 12px 0 rgba(23,25,22,0.28))" }}
              >
                <Image
                  src={ART.sentinel.src}
                  alt={ART.sentinel.alt}
                  width={ART.sentinel.width}
                  height={ART.sentinel.height}
                  priority
                  className="h-auto w-full select-none"
                  draggable={false}
                />
              </div>
            </div>
          </motion.div>

          {/* hand-drawn anchor note */}
          <motion.div
            initial={reduce ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.9, duration: 0.6 }}
            className="absolute -bottom-3 left-1/2 hidden -translate-x-1/2 items-center gap-2 lg:flex"
          >
            <Squiggle width={70} color="#65695F" />
            <span className="text-[11px] font-bold uppercase tracking-[0.14em] text-ink-soft">
              The Evidence Sentinel
            </span>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
