import type { SourceIdentity } from "@/types/domain";

/**
 * Source identities referenced across the preview workspace.
 * A later real provider would map these to actual endpoints and credentials.
 */

export const SOURCES = {
  globalWire: {
    id: "src-wire",
    name: "Global Market Wire",
    kind: "NEWS_WIRE",
    trust: "SECONDARY",
  } satisfies SourceIdentity,
  edgar: {
    id: "src-edgar",
    name: "SEC EDGAR full-text search",
    kind: "SEC_EDGAR",
    trust: "PRIMARY",
  } satisfies SourceIdentity,
  exchangeFeed: {
    id: "src-feed",
    name: "Bitget public market feed",
    kind: "EXCHANGE_FEED",
    trust: "PRIMARY",
  } satisfies SourceIdentity,
  providerDocs: {
    id: "src-provider",
    name: "Token issuer product documentation",
    kind: "PROVIDER_DOC",
    trust: "SECONDARY",
  } satisfies SourceIdentity,
  riskEngine: {
    id: "src-risk",
    name: "AFTERMATH risk engine",
    kind: "RISK_ENGINE",
    trust: "PRIMARY",
  } satisfies SourceIdentity,
  bureauStats: {
    id: "src-bls",
    name: "Statistics bureau release schedule",
    kind: "PROVIDER_DOC",
    trust: "PRIMARY",
  } satisfies SourceIdentity,
} as const;

export const SOURCE_KIND_LABELS: Record<SourceIdentity["kind"], string> = {
  NEWS_WIRE: "News wire",
  SEC_EDGAR: "SEC EDGAR",
  EXCHANGE_FEED: "Exchange feed",
  PROVIDER_DOC: "Provider document",
  RISK_ENGINE: "Risk engine",
};
