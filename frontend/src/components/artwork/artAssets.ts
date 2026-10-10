/**
 * Registry of generated raster artwork.
 * Dimensions are finalized after chroma-key processing; components read
 * them from here so next/image stays layout-stable.
 */

export interface ArtAsset {
  src: string;
  width: number;
  height: number;
  alt: string;
}

export const ART = {
  sentinel: {
    src: "/artwork/sentinel-hero.keyed.png",
    width: 780,
    height: 1095,
    alt: "The AFTERMATH Evidence Sentinel — an original paper-receipt guardian character holding up a verified evidence receipt",
  },
  riskGuardian: {
    src: "/artwork/risk-guardian.keyed.png",
    width: 640,
    height: 704,
    alt: "An original shield character firmly blocking a red downward arrow — AFTERMATH's deterministic risk controls",
  },
  receiptSeal: {
    src: "/artwork/receipt-seal.keyed.png",
    width: 520,
    height: 555,
    alt: "An original receipt character with a wax seal and checkmark badge — AFTERMATH's auditable decision records",
  },
  evidenceFlow: {
    src: "/artwork/evidence-flow.keyed.png",
    width: 900,
    height: 503,
    alt: "Original document characters carrying evidence toward a decision — how AFTERMATH builds its evidence record",
  },
  emptySearch: {
    src: "/artwork/empty-search.keyed.png",
    width: 560,
    height: 576,
    alt: "An original document character searching with a magnifying glass — nothing to show yet",
  },
  afterHours: {
    src: "/artwork/after-hours.keyed.png",
    width: 900,
    height: 543,
    alt: "An original alarmed clock character watching a price gap under a night sky — after-hours market risk",
  },
} as const satisfies Record<string, ArtAsset>;
