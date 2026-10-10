import { cn } from "@/lib/utils";

/**
 * Decorative doodle family — the Seen-style hand-drawn accents that give
 * AFTERMATH its editorial personality. Starbursts, squiggle underlines,
 * annotation arrows, and highlight ovals.
 */

export function Starburst({
  className,
  size = 28,
  color = "#086B32",
}: {
  className?: string;
  size?: number;
  color?: string;
}) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className={className}>
      <path
        d="M16 2.5 l2.6 8.4 8.4 2.6 -8.4 2.6 -2.6 8.4 -2.6-8.4 -8.4-2.6 8.4-2.6 Z"
        fill={color}
        stroke="#171916"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <circle cx="16" cy="13.5" r="1.6" fill="#171916" />
      <circle cx="10.5" cy="19" r="1.2" fill="#171916" />
      <circle cx="21.5" cy="19" r="1.2" fill="#171916" />
    </svg>
  );
}

export function Sparkle({
  className,
  size = 16,
  color = "#C9A227",
}: {
  className?: string;
  size?: number;
  color?: string;
}) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" className={className}>
      <path
        d="M8 1 l1.7 5.3 L15 8 l-5.3 1.7 L8 15 l-1.7-5.3 L1 8 l5.3-1.7 Z"
        fill={color}
        stroke="#171916"
        strokeWidth="1.2"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Squiggle({
  className,
  width = 140,
  color = "#086B32",
}: {
  className?: string;
  width?: number;
  color?: string;
}) {
  return (
    <svg width={width} height={12} viewBox="0 0 140 12" aria-hidden="true" className={className} preserveAspectRatio="none">
      <path
        d="M3 8 c10-8 18-8 28 0 s18 8 28 0 18-8 28 0 18 8 28 0 16-6 22-2"
        fill="none"
        stroke={color}
        strokeWidth="4"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function HandArrow({
  className,
  width = 64,
  flip = false,
  color = "#171916",
}: {
  className?: string;
  width?: number;
  flip?: boolean;
  color?: string;
}) {
  return (
    <svg
      width={width}
      height={width * 0.62}
      viewBox="0 0 64 40"
      aria-hidden="true"
      className={cn(flip && "-scale-x-100", className)}
    >
      <path
        d="M4 30 C14 8 34 4 52 12"
        fill="none"
        stroke={color}
        strokeWidth="3.4"
        strokeLinecap="round"
        strokeDasharray="0.5 7"
      />
      <path
        d="M44 6.5 L54 12.5 L47.5 21.5"
        fill="none"
        stroke={color}
        strokeWidth="3.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function HighlightOval({
  className,
  color = "#C9A227",
}: {
  className?: string;
  color?: string;
}) {
  return (
    <svg viewBox="0 0 220 26" aria-hidden="true" className={cn("h-[0.35em] w-full", className)} preserveAspectRatio="none">
      <path
        d="M6 16 C40 6 70 20 110 13 C150 6 180 18 214 10"
        fill="none"
        stroke={color}
        strokeWidth="9"
        strokeLinecap="round"
        opacity="0.55"
      />
    </svg>
  );
}

/** Circular "rotate" badge used on marquee separators and CTAs. */
export function OrbitBadge({
  className,
  size = 56,
  text = "EVIDENCE FIRST",
}: {
  className?: string;
  size?: number;
  text?: string;
}) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label={text} className={cn("animate-spin-slow", className)}>
      <defs>
        <path id="orbit-badge-path" d="M32 32 m -22 0 a 22 22 0 1 1 44 0 a 22 22 0 1 1 -44 0" />
      </defs>
      <circle cx="32" cy="32" r="30" fill="#FFFEF8" stroke="#171916" strokeWidth="2.4" />
      <circle cx="32" cy="32" r="24.5" fill="none" stroke="#D8D8CA" strokeWidth="1.4" strokeDasharray="2.5 3.5" />
      <text fontSize="8.2" fill="#171916" letterSpacing="1.6" style={{ fontFamily: "var(--font-sans)", fontWeight: 700 }}>
        <textPath href="#orbit-badge-path">{text} · {text} ·</textPath>
      </text>
      <path d="M32 24 l2 5.4 5.4 2 -5.4 2 -2 5.4 -2-5.4 -5.4-2 5.4-2 Z" fill="#086B32" />
    </svg>
  );
}
