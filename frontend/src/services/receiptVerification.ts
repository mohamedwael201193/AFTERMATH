import type { ReceiptVerification, SignedReceipt } from "@/types/domain";

/**
 * Receipt verification display logic.
 *
 * Key product rule: the interface must clearly distinguish a simulated
 * receipt presentation from an actual cryptographically verified receipt.
 * These helpers keep that language consistent everywhere receipts render.
 */

export const RECEIPT_VERIFICATION_LABELS: Record<
  ReceiptVerification,
  { label: string; tone: "neutral" | "positive"; caption: string }
> = {
  UNAVAILABLE: {
    label: "No receipt",
    tone: "neutral",
    caption: "No signed receipt is attached to this row.",
  },
  UNVERIFIED_PREVIEW: {
    label: "Simulated presentation",
    tone: "neutral",
    caption: "Not a cryptographic verification.",
  },
  STRUCTURE_VERIFIED: {
    label: "Structure verified · preview",
    tone: "positive",
    caption: "Fields present and consistent — still not a cryptographic verification.",
  },
  UNCONFIRMED: {
    label: "Signature verified · anchor unconfirmed",
    tone: "neutral",
    caption: "The receipt signature checked out. A missing or unconfirmed OpenTimestamps anchor is not a Bitcoin timestamp.",
  },
  SIGNATURE_VERIFIED: {
    label: "Signature verified",
    tone: "positive",
    caption: "The production public key verified this receipt.",
  },
};

export async function explainReceipt(receipt: SignedReceipt): Promise<string> {
  if (receipt.verification === "UNCONFIRMED") {
    return "The production public key verified the signature. The OpenTimestamps anchor is still pending, so this is not a confirmed external timestamp.";
  }
  if (receipt.verification === "SIGNATURE_VERIFIED") {
    return "The production public key verified the signature.";
  }
  if (receipt.verification === "UNAVAILABLE") {
    return "No signed production receipt is attached to this row.";
  }
  return "This presentation was not checked against the production verifier.";
}
