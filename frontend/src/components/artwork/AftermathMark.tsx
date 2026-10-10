import { cn } from "@/lib/utils";

/**
 * AFTERMATH brand marks.
 * Original typographic wordmark + the "verified A" badge glyph.
 */

export function AftermathBadge({
  className,
  size = 40,
}: {
  className?: string;
  size?: number;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label="AFTERMATH badge"
      className={className}
    >
      <rect x="2" y="2" width="60" height="60" rx="16" fill="#064D27" />
      <path
        d="M32 12 L45 52 H38.5 L36 44 H28 L25.5 52 H19 Z M30 37.5 H34 L32 29.5 Z"
        fill="#F5F2E7"
      />
      <path d="M22 18 h20" stroke="#086B32" strokeWidth="3" strokeLinecap="round" />
      <circle cx="48" cy="20" r="5" fill="#086B32" />
      <path
        d="M46 20 l1.6 1.6 2.6-3"
        stroke="#F5F2E7"
        strokeWidth="1.6"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function AftermathWordmark({
  className,
  on = "cream",
  withBadge = true,
}: {
  className?: string;
  /** Background the wordmark sits on. */
  on?: "cream" | "forest";
  withBadge?: boolean;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2.5 select-none", className)}>
      {withBadge && (
        <AftermathBadge
          size={34}
          className={cn(
            "shrink-0 rounded-[10px]",
            on === "cream" ? "sticker-shadow-sm" : "ring-2 ring-paper/70"
          )}
        />
      )}
      <span
        className={cn(
          "font-display leading-none tracking-[-0.02em] text-[1.05rem]",
          on === "cream" ? "text-ink type-shadow-soft" : "text-paper type-shadow"
        )}
        style={{ textShadow: on === "forest" ? "3px 3px 0 rgba(4,54,28,0.55)" : undefined }}
      >
        AFTERMATH
      </span>
    </span>
  );
}
