"use client";

import { LandingNav } from "@/components/landing/LandingNav";
import { Hero } from "@/components/landing/Hero";
import { Marquee } from "@/components/landing/Marquee";
import { ProblemSection } from "@/components/landing/ProblemSection";
import { HowItWorks } from "@/components/landing/HowItWorks";
import { Differentiators } from "@/components/landing/Differentiators";
import { ProductPreview } from "@/components/landing/ProductPreview";
import { TrustSection } from "@/components/landing/TrustSection";
import { ClosingCta, LandingFooter } from "@/components/landing/ClosingCta";
import { OrbitBadge } from "@/components/artwork/Decor";

/**
 * The AFTERMATH landing experience — a paper card floating on deep forest
 * green, with the marquee band living on the green frame below the card.
 */
export function LandingPage({ onOpenDashboard }: { onOpenDashboard: () => void }) {
  return (
    <>
      <LandingNav onOpenDashboard={onOpenDashboard} />

      <main>
        <Hero onOpenDashboard={onOpenDashboard} />
        <Marquee />
        <ProblemSection />
        <HowItWorks />
        <Marquee reverse />
        <Differentiators />
        <ProductPreview onOpenDashboard={onOpenDashboard} />
        <TrustSection />
        <ClosingCta onOpenDashboard={onOpenDashboard} />
      </main>

      <LandingFooter />

      {/* rotating badge pinned to the green frame corner */}
      <div className="pointer-events-none absolute bottom-24 right-4 hidden lg:block xl:right-8" aria-hidden="true">
        <OrbitBadge size={64} text="EVIDENCE FIRST" />
      </div>
    </>
  );
}
