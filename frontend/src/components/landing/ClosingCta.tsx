"use client";

import Image from "next/image";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Reveal } from "@/components/landing/Reveal";
import { Starburst } from "@/components/artwork/Decor";
import { AftermathWordmark } from "@/components/artwork/AftermathMark";
import { ART } from "@/components/artwork/artAssets";

/** Closing CTA — one bold statement, one action. */
export function ClosingCta({ onOpenDashboard }: { onOpenDashboard: () => void }) {
  return (
    <section className="relative overflow-x-guard px-4 pb-20 pt-8 sm:px-8 sm:pb-28 sm:pt-12 lg:px-12">
      <Starburst className="absolute left-[6%] top-6 hidden lg:block" size={34} />
      <Starburst className="absolute bottom-10 right-[10%] hidden rotate-12 lg:block" size={26} color="#C9A227" />

      <Reveal className="relative">
        <div className="relative rounded-[2.5rem] border-2 border-ink bg-warmwhite px-6 py-14 text-center shadow-[0_8px_0_rgba(23,25,22,0.9)] sm:px-12 sm:py-20">
          <p className="font-editorial text-xl italic text-ink-soft sm:text-2xl">
            ( every signal has a story )
          </p>
          <h2 className="mx-auto mt-4 max-w-3xl font-display uppercase leading-[0.92] tracking-[-0.02em] text-forest text-[clamp(2.4rem,7.5vw,5rem)]">
            See what the
            <br />
            evidence says<span className="text-forest-soft">.</span>
          </h2>
          <p className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-ink sm:text-lg">
            Open the preview workspace and walk a real decision end to end —
            from the event, through the evidence, to the signed receipt.
          </p>
          <div className="mt-9 flex justify-center">
            <Button
              onClick={onOpenDashboard}
              className="group h-14 gap-2.5 rounded-full border-2 border-ink bg-forest px-8 text-base font-bold text-paper shadow-[0_6px_0_rgba(23,25,22,0.9)] transition-all hover:-translate-y-0.5 hover:bg-forest-deep hover:shadow-[0_8px_0_rgba(23,25,22,0.9)] active:translate-y-0.5 active:shadow-[0_2px_0_rgba(23,25,22,0.9)] sm:px-10 sm:text-lg"
            >
              Open the dashboard
              <ArrowRight className="h-5 w-5 transition-transform group-hover:translate-x-1" aria-hidden="true" />
            </Button>
          </div>

          {/* sentinel peeking over the card edge */}
          <div
            className="pointer-events-none absolute -bottom-14 -right-6 hidden w-44 rotate-3 sm:block lg:-right-10 lg:w-52"
            style={{ filter: "drop-shadow(7px 9px 0 rgba(23,25,22,0.25))" }}
            aria-hidden="true"
          >
            <Image
              src={ART.sentinel.src}
              alt=""
              width={ART.sentinel.width}
              height={ART.sentinel.height}
              loading="lazy"
              className="h-auto w-full select-none"
              draggable={false}
            />
          </div>
        </div>
      </Reveal>
    </section>
  );
}

/** Compact, intentional footer. */
export function LandingFooter() {
  return (
    <footer className="mt-auto border-t-2 border-line bg-paper px-4 py-6 sm:px-8 lg:px-12">
      <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
        <AftermathWordmark />
        <nav aria-label="Footer" className="flex flex-wrap gap-x-5 gap-y-2 text-sm font-semibold text-ink-soft">
          <a href="#product" className="transition-colors hover:text-forest">Product</a>
          <a href="#how-it-works" className="transition-colors hover:text-forest">How it works</a>
          <a href="#trust" className="transition-colors hover:text-forest">Trust & safety</a>
          <a href="/paper-trading-log" className="transition-colors hover:text-forest">Paper log</a>
        </nav>
        <p className="text-xs leading-relaxed text-ink-soft sm:max-w-xs sm:text-right">
          Preview workspace — all events, prices, decisions, and receipts are
          illustrative. Not investment advice.
        </p>
      </div>
      <p className="mt-4 border-t border-line pt-3 text-center text-xs text-ink-soft/80">
        © 2026 AFTERMATH · Evidence-governed trading intelligence
      </p>
    </footer>
  );
}
