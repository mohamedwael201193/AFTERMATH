"use client";

import { useState } from "react";
import { ChevronDown, ShieldQuestion, ShieldCheck, ShieldAlert } from "lucide-react";
import type { EvidenceRecord } from "@/types/domain";
import { FreshnessDot } from "@/components/artwork/StatusGlyphs";
import { FRESHNESS_LABELS, formatEt, relativeToNow } from "@/lib/format";
import { cn } from "@/lib/utils";

const VERIFICATION_META = {
  SOURCE_CONFIRMED: {
    icon: ShieldCheck,
    cls: "border-forest bg-forest-mist text-forest-deep",
    label: "Source confirmed",
  },
  UNVERIFIED: {
    icon: ShieldQuestion,
    cls: "border-line-strong bg-paper text-ink-soft",
    label: "Unverified",
  },
  CONFLICTING: {
    icon: ShieldAlert,
    cls: "border-ink bg-warn-soft text-warn",
    label: "Conflicting",
  },
} as const;

/**
 * One evidence record — source, timestamp, value with units, freshness,
 * and why it matters. The atom of AFTERMATH's trust model.
 */
export function EvidenceCard({
  record,
  defaultOpen = false,
}: {
  record: EvidenceRecord;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const v = VERIFICATION_META[record.verification];
  const freshnessTone =
    record.freshness === "FRESH"
      ? "text-forest"
      : record.freshness === "AGING"
        ? "text-warn"
        : "text-risk";

  return (
    <article
      className={cn(
        "rounded-2xl border-2 bg-warmwhite transition-colors",
        record.verification === "CONFLICTING"
          ? "border-warn"
          : "border-line hover:border-ink"
      )}
    >
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3 text-left"
      >
        <FreshnessDot freshness={record.freshness} />
        <span className="text-sm font-bold text-ink">{record.label}</span>
        <span className="tnum text-sm font-bold text-forest">{record.value}</span>
        <span
          className={cn(
            "ml-auto inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide",
            v.cls
          )}
        >
          <v.icon className="h-3 w-3" aria-hidden="true" />
          {v.label}
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-ink-soft transition-transform",
            open && "rotate-180"
          )}
          aria-hidden="true"
        />
      </button>

      <div
        className={cn(
          "grid overflow-hidden transition-all duration-300",
          open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
        )}
      >
        <div className="min-h-0">
          <dl className="grid gap-x-6 gap-y-2 border-t-2 border-line bg-paper px-4 py-3 text-xs sm:grid-cols-2">
            <div className="flex gap-2">
              <dt className="shrink-0 font-bold uppercase tracking-wide text-ink-soft">Source</dt>
              <dd className="font-semibold text-ink">{record.source.name}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="shrink-0 font-bold uppercase tracking-wide text-ink-soft">Captured</dt>
              <dd className="tnum font-semibold text-ink">
                {formatEt(record.capturedAt, "full")} ET
                <span className="ml-1 font-normal text-ink-soft">
                  · {relativeToNow(record.capturedAt)}
                </span>
              </dd>
            </div>
            <div className="flex gap-2">
              <dt className="shrink-0 font-bold uppercase tracking-wide text-ink-soft">Freshness</dt>
              <dd className={cn("font-bold", freshnessTone)}>{FRESHNESS_LABELS[record.freshness]}</dd>
            </div>
            {record.unit && (
              <div className="flex gap-2">
                <dt className="shrink-0 font-bold uppercase tracking-wide text-ink-soft">Units</dt>
                <dd className="font-semibold text-ink">{record.unit}</dd>
              </div>
            )}
            <div className="flex gap-2 sm:col-span-2">
              <dt className="shrink-0 font-bold uppercase tracking-wide text-ink-soft">
                Why it matters
              </dt>
              <dd className="leading-relaxed text-ink-soft">{record.whyItMatters}</dd>
            </div>
          </dl>
        </div>
      </div>
    </article>
  );
}
