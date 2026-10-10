import { cn } from "@/lib/utils";

/**
 * Workflow stage illustrations — the original "How AFTERMATH works" family.
 * One visual language throughout: thick ink outlines, cream fills,
 * forest-green accents, consistent corner rounding.
 */

export function EventGlyph({ className, size = 64 }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="A market event arriving" className={className}>
      {/* motion lines */}
      <path d="M8 22 h7 M6 32 h6 M9 42 h6" stroke="#65695F" strokeWidth="2.6" strokeLinecap="round" />
      {/* bell */}
      <path
        d="M24 16 h26 c2.6 0 4 3 2.2 4.9 l-3.4 3.6 v11.6 c0 7.4-5.2 12.4-11.8 12.4 c-6.6 0-11.8-5-11.8-12.4 V24.5 l-3.4-3.6 C20 19 21.4 16 24 16 Z"
        fill="#FFFEF8" stroke="#171916" strokeWidth="3" strokeLinejoin="round"
      />
      {/* bell shine */}
      <path d="M28 22 v12" stroke="#E3ECDF" strokeWidth="3" strokeLinecap="round" />
      {/* clapper */}
      <circle cx="37" cy="53.4" r="4" fill="#086B32" stroke="#171916" strokeWidth="2.6" />
      {/* lightning badge */}
      <path d="M44.5 8 l-6.4 9.6 h5 l-2.2 8.4 8.4-11.2 h-5.2 Z" fill="#C9A227" stroke="#171916" strokeWidth="2.4" strokeLinejoin="round" />
      {/* handle */}
      <path d="M31 16 c1.6-4.4 8.4-4.4 10 0" fill="none" stroke="#171916" strokeWidth="2.8" strokeLinecap="round" />
    </svg>
  );
}

export function EvidenceGlyph({ className, size = 64 }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="An evidence record with a source and timestamp" className={className}>
      {/* document */}
      <path
        d="M16 10 h24 l8 8 v36 h-32 Z"
        fill="#FFFEF8" stroke="#171916" strokeWidth="3" strokeLinejoin="round"
      />
      <path d="M40 10 v8 h8" fill="none" stroke="#171916" strokeWidth="3" strokeLinejoin="round" />
      {/* text lines */}
      <path d="M22 24 h12 M22 31 h20 M22 38 h16" stroke="#65695F" strokeWidth="2.6" strokeLinecap="round" />
      {/* value line */}
      <path d="M22 45 h8" stroke="#086B32" strokeWidth="2.8" strokeLinecap="round" />
      <circle cx="34.4" cy="45" r="1.7" fill="#086B32" />
      {/* check stamp */}
      <circle cx="47" cy="47" r="9.5" fill="#086B32" stroke="#171916" strokeWidth="2.6" />
      <path d="M43 47 l2.8 3 5-6.4" stroke="#F5F2E7" strokeWidth="2.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      {/* timestamp chip */}
      <rect x="9" y="20" width="10" height="7" rx="2.5" fill="#F5F2E7" stroke="#171916" strokeWidth="2.2" />
      <circle cx="14" cy="23.5" r="1.5" fill="#171916" />
      <path d="M14 23.5 v-2" stroke="#171916" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

export function JudgmentGlyph({ className, size = 64 }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="AI judgment with visible reasoning" className={className}>
      {/* thought bubble */}
      <path
        d="M40 8 c-3.6 0-6.6 2.3-7.7 5.5 c-.7-.2-1.4-.3-2.1-.3 c-4 0-7.2 3.1-7.2 7 c0 .8.1 1.5.4 2.2 c-2.6 1.2-4.4 3.8-4.4 6.8 c0 4.1 3.4 7.5 7.6 7.5 h14.8 c5 0 9-3.9 9-8.8 c0-3.4-2-6.4-4.9-7.9 c.4-1 .6-2 .6-3.1 C46.7 11.3 43.7 8 40 8 Z"
        fill="#F5F2E7" stroke="#171916" strokeWidth="3" strokeLinejoin="round"
      />
      {/* check inside bubble */}
      <path d="M31.5 25.5 l3.4 3.6 6-7.4" stroke="#086B32" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      {/* face */}
      <rect x="14" y="38" width="36" height="20" rx="9" fill="#FFFEF8" stroke="#171916" strokeWidth="3" />
      <circle cx="25" cy="47.5" r="2.4" fill="#171916" />
      <circle cx="39" cy="47.5" r="2.4" fill="#171916" />
      <path d="M28.5 53.5 c2 1.6 5 1.6 7 0" stroke="#171916" strokeWidth="2.6" fill="none" strokeLinecap="round" />
      {/* thought dots */}
      <circle cx="22" cy="33" r="2.4" fill="#FFFEF8" stroke="#171916" strokeWidth="2" />
      <circle cx="16" cy="27" r="1.7" fill="#FFFEF8" stroke="#171916" strokeWidth="2" />
    </svg>
  );
}

export function RiskGlyph({ className, size = 64 }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="Deterministic risk controls guarding the decision" className={className}>
      {/* shield */}
      <path
        d="M32 7 l19 6.5 v13.8 C51 39 43 48.5 32 54 C21 48.5 13 39 13 27.3 V13.5 Z"
        fill="#FFFEF8" stroke="#171916" strokeWidth="3" strokeLinejoin="round"
      />
      {/* shield inner line */}
      <path d="M32 13.5 l13 4.6 v9.4 C45 36.5 39.4 43.4 32 47.4 Z" fill="#E3ECDF" stroke="#171916" strokeWidth="2.2" strokeLinejoin="round" />
      {/* gate barrier arm across */}
      <g transform="rotate(-32 32 30)">
        <rect x="10" y="27.5" width="44" height="8" rx="3.4" fill="#F5F2E7" stroke="#171916" strokeWidth="2.8" />
        <path d="M17 27.5 l6 8 M27 27.5 l6 8 M37 27.5 l6 8" stroke="#B3261E" strokeWidth="3" strokeLinecap="round" />
      </g>
      {/* barrier post */}
      <rect x="48.5" y="22" width="6" height="26" rx="3" fill="#65695F" stroke="#171916" strokeWidth="2.6" />
      <circle cx="51.5" cy="27.5" r="2.6" fill="#F5F2E7" stroke="#171916" strokeWidth="2" />
    </svg>
  );
}

export function PaperGlyph({ className, size = 64 }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="Paper execution ticket with visible costs" className={className}>
      {/* ticket */}
      <rect x="12" y="12" width="40" height="40" rx="6" fill="#FFFEF8" stroke="#171916" strokeWidth="3" />
      {/* perforation */}
      <path d="M12 40 h40" stroke="#171916" strokeWidth="2.4" strokeDasharray="1 6" strokeLinecap="round" />
      {/* ticket lines */}
      <path d="M19 20 h16 M19 27 h22" stroke="#65695F" strokeWidth="2.6" strokeLinecap="round" />
      {/* numbers */}
      <path d="M19 33 h9" stroke="#086B32" strokeWidth="2.8" strokeLinecap="round" />
      <rect x="33" y="30" width="12" height="6.5" rx="2" fill="#E3ECDF" stroke="#171916" strokeWidth="2" />
      {/* stub stamp */}
      <rect x="18" y="44" width="28" height="7" rx="3.5" fill="#086B32" stroke="#171916" strokeWidth="2.2" />
      <path d="M23 47.5 h6 M33 47.5 h6" stroke="#F5F2E7" strokeWidth="2" strokeLinecap="round" />
      {/* cost coin */}
      <circle cx="53" cy="18" r="7" fill="#C9A227" stroke="#171916" strokeWidth="2.6" />
      <path d="M50.5 18 h5 M53 15.5 v5" stroke="#171916" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function ReceiptGlyph({ className, size = 64 }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label="A signed, independently checkable receipt" className={className}>
      {/* receipt with zigzag bottom */}
      <path
        d="M18 8 h28 v42 l-4.7 4 -4.6-4 -4.7 4 -4.7-4 -4.6 4 -4.7-4 -4.7 4 -4.6-4 -4.7 4 Z"
        fill="#FFFEF8" stroke="#171916" strokeWidth="3" strokeLinejoin="round"
      />
      {/* receipt lines */}
      <path d="M24 18 h16 M24 25 h16 M24 32 h10" stroke="#65695F" strokeWidth="2.6" strokeLinecap="round" />
      {/* digest dashes */}
      <path d="M24 39 h4 M31 39 h4 M38 39 h4" stroke="#086B32" strokeWidth="2.6" strokeLinecap="round" />
      {/* wax seal */}
      <circle cx="47" cy="45" r="10.5" fill="#086B32" stroke="#171916" strokeWidth="2.8" />
      <circle cx="47" cy="45" r="6.4" fill="none" stroke="#F5F2E7" strokeWidth="1.8" strokeDasharray="2.2 2.6" />
      <path d="M44 45 l2.4 2.6 4.2-5.2" stroke="#F5F2E7" strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      {/* ribbon */}
      <path d="M43 54 l-2.6 7 3.4-2 2.4 3 Z" fill="#C9A227" stroke="#171916" strokeWidth="2" strokeLinejoin="round" />
      {/* verified spark */}
      <path d="M15 14 l1.4 3 3 1.4 -3 1.4 -1.4 3 -1.4-3 -3-1.4 3-1.4 Z" fill="#C9A227" stroke="#171916" strokeWidth="1.6" strokeLinejoin="round" />
    </svg>
  );
}

export const WORKFLOW_GLYPHS = {
  event: EventGlyph,
  evidence: EvidenceGlyph,
  judgment: JudgmentGlyph,
  risk: RiskGlyph,
  paper: PaperGlyph,
  receipt: ReceiptGlyph,
} as const;
