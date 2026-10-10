"use client";

import { Sparkle } from "@/components/artwork/Decor";

const PHRASES = [
  "Evidence first",
  "Uncertainty is visible",
  "Risk is deterministic",
  "Every decision is auditable",
  "Paper execution before unsupported claims",
  "A refusal is a result",
];

/**
 * Product-story marquee — a seamless green band with cream editorial type.
 * Pauses on hover/focus; hidden from screen readers as decorative.
 */
export function Marquee({ reverse = false }: { reverse?: boolean }) {
  const row = (ariaHidden: boolean) => (
    <div
      aria-hidden={ariaHidden}
      className="flex shrink-0 items-center gap-8 pr-8"
    >
      {PHRASES.map((p) => (
        <span key={p} className="flex items-center gap-8 whitespace-nowrap">
          <span className="font-editorial text-lg italic text-paper sm:text-xl">
            {p}
          </span>
          <Sparkle size={15} color="#C9A227" />
        </span>
      ))}
    </div>
  );

  return (
    <div
      className="marquee-track relative flex overflow-hidden border-y-2 border-ink bg-forest py-3"
      style={{
        animation: `${reverse ? "marquee-reverse" : "marquee"} 42s linear infinite`,
      }}
    >
      {row(true)}
      {row(true)}
      {/* screen-reader accessible static list */}
      <ul className="sr-only">
        {PHRASES.map((p) => (
          <li key={p}>{p}</li>
        ))}
      </ul>
    </div>
  );
}
