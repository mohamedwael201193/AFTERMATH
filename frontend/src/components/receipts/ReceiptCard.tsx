"use client";

import { useEffect, useState } from "react";
import { Copy, Check, Fingerprint, Clock3 } from "lucide-react";
import type { SignedReceipt } from "@/types/domain";
import { RECEIPT_VERIFICATION_LABELS } from "@/services/receiptVerification";
import { dataProvider } from "@/services";
import { formatEt } from "@/lib/format";
import { cn } from "@/lib/utils";
import { toast } from "@/hooks/use-toast";

/**
 * Illustrative receipt presentation. The interface deliberately
 * distinguishes a simulated receipt from a cryptographic verification —
 * the explanation text comes from the provider boundary.
 */
export function ReceiptCard({ receipt }: { receipt: SignedReceipt }) {
  const [copied, setCopied] = useState(false);
  const [explanation, setExplanation] = useState<string | null>(null);
  const meta = RECEIPT_VERIFICATION_LABELS[receipt.verification];

  useEffect(() => {
    let alive = true;
    dataProvider.explainVerification(receipt).then((text) => {
      if (alive) setExplanation(text);
    });
    return () => {
      alive = false;
    };
  }, [receipt]);

  const copyDigest = async () => {
    try {
      await navigator.clipboard.writeText(receipt.digestPreview.replace(/\s+/g, ""));
      setCopied(true);
      toast({
        title: "Digest copied",
        description: "Illustrative digest copied to your clipboard.",
      });
      setTimeout(() => setCopied(false), 1800);
    } catch {
      toast({
        title: "Copy failed",
        description: "Your browser blocked clipboard access.",
        variant: "destructive",
      });
    }
  };

  return (
    <article className="overflow-hidden rounded-3xl border-2 border-ink bg-warmwhite shadow-[0_4px_0_rgba(23,25,22,0.85)]">
      <div className="flex flex-wrap items-center gap-3 border-b-2 border-dashed border-line-strong bg-paper px-5 py-3">
        <Fingerprint className="h-5 w-5 text-forest" aria-hidden="true" />
        <h4 className="text-sm font-bold uppercase tracking-wide text-ink">
          Decision receipt
        </h4>
        <span
          className={cn(
            "ml-auto inline-flex items-center rounded-full border-2 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide",
            meta.tone === "positive"
              ? "border-forest bg-forest-mist text-forest-deep"
              : "border-ink bg-hold-soft text-ink-soft"
          )}
        >
          {meta.label}
        </span>
      </div>

      <div className="grid gap-4 px-5 py-4">
        {receipt.verification !== "UNAVAILABLE" && (
        <div className="flex flex-wrap items-center gap-3">
          <code className="tnum rounded-xl border-2 border-ink bg-forest-deep px-3.5 py-2 font-mono text-sm font-bold tracking-widest text-paper">
            {receipt.digestPreview}
          </code>
          <button
            onClick={copyDigest}
            aria-label="Copy digest"
            className="inline-flex h-10 w-10 items-center justify-center rounded-xl border-2 border-ink bg-warmwhite text-ink transition-colors hover:bg-forest-mist"
          >
            {copied ? (
              <Check className="h-4 w-4 text-forest" aria-hidden="true" />
            ) : (
              <Copy className="h-4 w-4" aria-hidden="true" />
            )}
          </button>
        </div>
        )}

        {receipt.verification === "UNAVAILABLE" ? (
          <p className="text-sm font-semibold text-ink-soft">No receipt is attached, so there is no signature algorithm or timestamp authority for this row.</p>
        ) : (
        <dl className="grid gap-x-6 gap-y-2 text-xs sm:grid-cols-2">
          <div className="flex gap-2">
            <dt className="shrink-0 font-bold uppercase tracking-wide text-ink-soft">Algorithm</dt>
            <dd className="font-semibold text-ink">{receipt.algorithm}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="shrink-0 font-bold uppercase tracking-wide text-ink-soft">Timestamp</dt>
            <dd className="tnum inline-flex items-center gap-1 font-semibold text-ink">
              <Clock3 className="h-3.5 w-3.5 text-ink-soft" aria-hidden="true" />
              {formatEt(receipt.createdAt, "full")} ET
            </dd>
          </div>
          <div className="flex gap-2 sm:col-span-2">
            <dt className="shrink-0 font-bold uppercase tracking-wide text-ink-soft">Authority</dt>
            <dd className="font-semibold text-ink">{receipt.timestampAuthority}</dd>
          </div>
          <div className="flex flex-wrap gap-2 sm:col-span-2">
            <dt className="shrink-0 font-bold uppercase tracking-wide text-ink-soft">Fields</dt>
            <dd className="flex flex-wrap gap-1.5">
              {receipt.fieldsIncluded.map((f) => (
                <span
                  key={f}
                  className="rounded-full border border-line-strong bg-paper px-2 py-0.5 font-semibold text-ink-soft"
                >
                  {f}
                </span>
              ))}
            </dd>
          </div>
        </dl>
        )}

        <p
          className={cn(
            "rounded-2xl border-2 px-4 py-3 text-xs leading-relaxed",
            meta.tone === "positive"
              ? "border-forest bg-forest-mist text-forest-deep"
              : "border-line-strong bg-paper text-ink-soft"
          )}
        >
          {explanation ?? "Loading verification notes…"}
        </p>
      </div>
    </article>
  );
}
