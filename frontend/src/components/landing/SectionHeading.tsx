"use client";

import { cn } from "@/lib/utils";
import { Starburst } from "@/components/artwork/Decor";
import { Reveal } from "@/components/landing/Reveal";

/**
 * Shared landing section heading — display type, serif editorial aside,
 * and the starburst eyebrow that ties sections together.
 */
export function SectionHeading({
  eyebrow,
  title,
  aside,
  intro,
  align = "left",
  className,
}: {
  eyebrow: string;
  title: React.ReactNode;
  aside?: string;
  intro?: string;
  align?: "left" | "center";
  className?: string;
}) {
  return (
    <Reveal className={cn("max-w-3xl", align === "center" && "mx-auto text-center", className)}>
      <div
        className={cn(
          "inline-flex items-center gap-2 rounded-full border-2 border-ink bg-warmwhite px-3.5 py-1.5",
          align === "center" && "mx-auto"
        )}
      >
        <Starburst size={17} />
        <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-ink sm:text-xs">
          {eyebrow}
        </span>
      </div>
      <h2 className="mt-5 font-display uppercase leading-[0.95] tracking-[-0.015em] text-forest-deep text-[clamp(2.1rem,6vw,3.9rem)]">
        {title}
      </h2>
      {aside && (
        <p className="mt-4 font-editorial text-xl italic text-ink-soft sm:text-2xl">
          ( {aside} )
        </p>
      )}
      {intro && (
        <p className={cn("mt-4 max-w-2xl text-base leading-relaxed text-ink sm:text-lg", align === "center" && "mx-auto")}>
          {intro}
        </p>
      )}
    </Reveal>
  );
}
