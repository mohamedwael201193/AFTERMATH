import type { EvidenceRecord } from "@/types/domain";
import { SOURCES } from "@/data/sources";

/**
 * Evidence records for the preview workspace events.
 * Each record states one fact, its source, its timestamp, and why it matters.
 * The AI decision layer may only cite records that exist here.
 */

export const evidenceRecords: EvidenceRecord[] = [
  /* ── EV-1001 · NVDA Q3 earnings ─────────────────────────────── */
  {
    id: "EV-1001-E1",
    eventId: "EV-1001",
    label: "Q3 FY26 revenue",
    source: SOURCES.globalWire,
    capturedAt: "2026-01-09T21:18:00Z",
    value: "45.26 B USD",
    numericValue: 45.26,
    unit: "B USD",
    freshness: "FRESH",
    whyItMatters:
      "Revenue is the headline number of the release. It sets the direction and rough magnitude of the reference-price move.",
    verification: "SOURCE_CONFIRMED",
  },
  {
    id: "EV-1001-E2",
    eventId: "EV-1001",
    label: "Q3 diluted EPS",
    source: SOURCES.globalWire,
    capturedAt: "2026-01-09T21:19:00Z",
    value: "0.84 USD",
    numericValue: 0.84,
    unit: "USD",
    freshness: "FRESH",
    whyItMatters:
      "EPS confirms the quality of the beat. Both revenue and EPS clearing consensus makes a positive gap more defensible.",
    verification: "SOURCE_CONFIRMED",
  },
  {
    id: "EV-1001-E3",
    eventId: "EV-1001",
    label: "8-K filed on EDGAR",
    source: SOURCES.edgar,
    capturedAt: "2026-01-09T21:14:00Z",
    value: "1 filing · accession 0001047469-26-000011",
    numericValue: null,
    unit: null,
    freshness: "FRESH",
    whyItMatters:
      "The primary record proves the wire story is not fabricated. Without the 8-K, a headline alone could not support a PROCEED.",
    verification: "SOURCE_CONFIRMED",
  },
  {
    id: "EV-1001-E4",
    eventId: "EV-1001",
    label: "Data-center segment revenue",
    source: SOURCES.providerDocs,
    capturedAt: "2026-01-09T21:24:00Z",
    value: "30.8 B USD",
    numericValue: 30.8,
    unit: "B USD",
    freshness: "FRESH",
    whyItMatters:
      "The segment breakdown indicates whether growth is concentrated where tokenized-equity buyers are most sensitive.",
    verification: "SOURCE_CONFIRMED",
  },
  {
    id: "EV-1001-E5",
    eventId: "EV-1001",
    label: "Tokenized price observation",
    source: SOURCES.exchangeFeed,
    capturedAt: "2026-01-09T22:08:00Z",
    value: "189.42 USD",
    numericValue: 189.42,
    unit: "USD",
    freshness: "FRESH",
    whyItMatters:
      "The executable price right now, with its timestamp. Paper execution will be costed against this observation, not against the reference close.",
    verification: "SOURCE_CONFIRMED",
  },

  /* ── EV-1002 · TSLA supply-contract rumor ───────────────────── */
  {
    id: "EV-1002-E1",
    eventId: "EV-1002",
    label: "Wire headline text",
    source: SOURCES.globalWire,
    capturedAt: "2026-01-09T18:05:00Z",
    value: "“People familiar with the matter” describe a supply agreement",
    numericValue: null,
    unit: null,
    freshness: "FRESH",
    whyItMatters:
      "This is the only positive claim in the bundle — and it is a single secondary source citing unnamed people.",
    verification: "UNVERIFIED",
  },
  {
    id: "EV-1002-E2",
    eventId: "EV-1002",
    label: "EDGAR search: Tesla filings today",
    source: SOURCES.edgar,
    capturedAt: "2026-01-09T18:20:00Z",
    value: "0 relevant filings",
    numericValue: 0,
    unit: "filings",
    freshness: "FRESH",
    whyItMatters:
      "The primary record is silent. An absence of evidence is itself evidence — it means the claim cannot be confirmed today.",
    verification: "SOURCE_CONFIRMED",
  },
  {
    id: "EV-1002-E3",
    eventId: "EV-1002",
    label: "Company statement search",
    source: SOURCES.providerDocs,
    capturedAt: "2026-01-09T18:24:00Z",
    value: "No statement found",
    numericValue: null,
    unit: null,
    freshness: "FRESH",
    whyItMatters:
      "A second independent confirmation would raise the bundle's completeness. None exists, so the decision has to lean on refusal.",
    verification: "UNVERIFIED",
  },

  /* ── EV-1003 · META misleading headline ─────────────────────── */
  {
    id: "EV-1003-E1",
    eventId: "EV-1003",
    label: "Wire headline claim",
    source: SOURCES.globalWire,
    capturedAt: "2026-01-09T19:47:00Z",
    value: "“FDA approval … filing shows”",
    numericValue: null,
    unit: null,
    freshness: "FRESH",
    whyItMatters:
      "The claim asserts an approval and attributes it to a filing. Both halves of that sentence can be checked independently.",
    verification: "CONFLICTING",
  },
  {
    id: "EV-1003-E2",
    eventId: "EV-1003",
    label: "Cited filing contents (10-Q)",
    source: SOURCES.edgar,
    capturedAt: "2026-01-09T19:58:00Z",
    value: "No approval language present",
    numericValue: null,
    unit: null,
    freshness: "FRESH",
    whyItMatters:
      "The primary record contradicts the headline. When the source and the story disagree, the source wins.",
    verification: "SOURCE_CONFIRMED",
  },
  {
    id: "EV-1003-E3",
    eventId: "EV-1003",
    label: "Public device register check",
    source: SOURCES.providerDocs,
    capturedAt: "2026-01-09T20:02:00Z",
    value: "No approval record for the device",
    numericValue: null,
    unit: null,
    freshness: "FRESH",
    whyItMatters:
      "A second independent check confirms the first: the approval does not exist in any primary source.",
    verification: "SOURCE_CONFIRMED",
  },
  {
    id: "EV-1003-E4",
    eventId: "EV-1003",
    label: "Wire correction notice",
    source: SOURCES.globalWire,
    capturedAt: "2026-01-09T20:15:00Z",
    value: "“An earlier version mischaracterized the filing”",
    numericValue: null,
    unit: null,
    freshness: "FRESH",
    whyItMatters:
      "The originating source retracted the characterization. This is exactly the pattern adversarial validation exists to catch.",
    verification: "CONFLICTING",
  },

  /* ── EV-1004 · COIN reference gap ───────────────────────────── */
  {
    id: "EV-1004-E1",
    eventId: "EV-1004",
    label: "Tokenized COIN last trade",
    source: SOURCES.exchangeFeed,
    capturedAt: "2026-01-09T20:58:00Z",
    value: "281.35 USD",
    numericValue: 281.35,
    unit: "USD",
    freshness: "FRESH",
    whyItMatters:
      "The price you could actually trade at. It has moved sharply and recently.",
    verification: "SOURCE_CONFIRMED",
  },
  {
    id: "EV-1004-E2",
    eventId: "EV-1004",
    label: "Reference equity quote",
    source: SOURCES.exchangeFeed,
    capturedAt: "2026-01-09T19:45:00Z",
    value: "299.10 USD",
    numericValue: 299.1,
    unit: "USD",
    freshness: "STALE",
    whyItMatters:
      "This quote is 65 minutes old. Without a fresh reference, no one can say whether the token or the reference is the outlier.",
    verification: "SOURCE_CONFIRMED",
  },
  {
    id: "EV-1004-E3",
    eventId: "EV-1004",
    label: "Token vs reference divergence",
    source: SOURCES.riskEngine,
    capturedAt: "2026-01-09T21:00:00Z",
    value: "−5.9 %",
    numericValue: -5.9,
    unit: "%",
    freshness: "FRESH",
    whyItMatters:
      "The divergence is what makes this event interesting — and dangerous. It exceeds every threshold the workspace defines as normal.",
    verification: "SOURCE_CONFIRMED",
  },
  {
    id: "EV-1004-E4",
    eventId: "EV-1004",
    label: "Order-book depth within 0.5 % of mid",
    source: SOURCES.exchangeFeed,
    capturedAt: "2026-01-09T21:01:00Z",
    value: "7.1 k USD",
    numericValue: 7100,
    unit: "USD",
    freshness: "FRESH",
    whyItMatters:
      "Depth is above the refusal floor but below the full-size comfort band, which matters if a trade is later considered.",
    verification: "SOURCE_CONFIRMED",
  },

  /* ── EV-1005 · AMZN 8-K filing ──────────────────────────────── */
  {
    id: "EV-1005-E1",
    eventId: "EV-1005",
    label: "8-K filed on EDGAR",
    source: SOURCES.edgar,
    capturedAt: "2026-01-09T14:22:00Z",
    value: "1 filing · accession 0001018724-26-000004",
    numericValue: null,
    unit: null,
    freshness: "FRESH",
    whyItMatters:
      "The primary record. It confirms the pricing update is real, filed, and attributable to Amazon.",
    verification: "SOURCE_CONFIRMED",
  },
  {
    id: "EV-1005-E2",
    eventId: "EV-1005",
    label: "Filing materiality excerpt",
    source: SOURCES.providerDocs,
    capturedAt: "2026-01-09T14:26:00Z",
    value: "Pricing mechanics update for reserved capacity",
    numericValue: null,
    unit: null,
    freshness: "FRESH",
    whyItMatters:
      "Describes what the filing actually changes, so the model reasons about the filing instead of the headline paraphrase.",
    verification: "SOURCE_CONFIRMED",
  },
  {
    id: "EV-1005-E3",
    eventId: "EV-1005",
    label: "Tokenized price at filing time",
    source: SOURCES.exchangeFeed,
    capturedAt: "2026-01-09T14:25:00Z",
    value: "227.90 USD",
    numericValue: 227.9,
    unit: "USD",
    freshness: "FRESH",
    whyItMatters:
      "The price context when the news became public — used to sanity-check the direction and size of the proposed trade.",
    verification: "SOURCE_CONFIRMED",
  },
  {
    id: "EV-1005-E4",
    eventId: "EV-1005",
    label: "Order-book depth within 0.5 % of mid",
    source: SOURCES.exchangeFeed,
    capturedAt: "2026-01-09T14:24:00Z",
    value: "2.3 k USD",
    numericValue: 2300,
    unit: "USD",
    freshness: "FRESH",
    whyItMatters:
      "Depth is thin relative to the intended size. This is the fact that turns an approval into a reduction.",
    verification: "SOURCE_CONFIRMED",
  },

  /* ── EV-1006 · AAPL dividend record ─────────────────────────── */
  {
    id: "EV-1006-E1",
    eventId: "EV-1006",
    label: "Dividend declaration filing",
    source: SOURCES.edgar,
    capturedAt: "2026-01-08T21:40:00Z",
    value: "0.25 USD per share · quarterly",
    numericValue: 0.25,
    unit: "USD/share",
    freshness: "AGING",
    whyItMatters:
      "Confirms the event is real and quantifies it. The amount matches the prior quarter, which is the key fact for a no-action conclusion.",
    verification: "SOURCE_CONFIRMED",
  },
  {
    id: "EV-1006-E2",
    eventId: "EV-1006",
    label: "Prior-quarter dividend amount",
    source: SOURCES.providerDocs,
    capturedAt: "2026-01-08T21:44:00Z",
    value: "0.25 USD per share",
    numericValue: 0.25,
    unit: "USD/share",
    freshness: "AGING",
    whyItMatters:
      "The comparison that makes this routine: an unchanged dividend removes the surprise that a trade would need.",
    verification: "SOURCE_CONFIRMED",
  },
  {
    id: "EV-1006-E3",
    eventId: "EV-1006",
    label: "Record-date consistency check",
    source: SOURCES.riskEngine,
    capturedAt: "2026-01-08T21:47:00Z",
    value: "Record date unchanged",
    numericValue: null,
    unit: null,
    freshness: "AGING",
    whyItMatters:
      "Closes the last material question. With amount and dates unchanged, there is nothing left to act on.",
    verification: "SOURCE_CONFIRMED",
  },

  /* ── EV-1007 · MU tariff review headline ────────────────────── */
  {
    id: "EV-1007-E1",
    eventId: "EV-1007",
    label: "Wire headline text",
    source: SOURCES.globalWire,
    capturedAt: "2026-01-09T12:31:00Z",
    value: "“Commerce department floats memory-module tariff review”",
    numericValue: null,
    unit: null,
    freshness: "FRESH",
    whyItMatters:
      "The only source for this event. It names a process, not a decision — scope and timing are unspecified.",
    verification: "UNVERIFIED",
  },
  {
    id: "EV-1007-E2",
    eventId: "EV-1007",
    label: "Named companies in the story",
    source: SOURCES.globalWire,
    capturedAt: "2026-01-09T12:31:00Z",
    value: "0 named companies",
    numericValue: 0,
    unit: "companies",
    freshness: "FRESH",
    whyItMatters:
      "No company is named. Linking the headline to a specific ticker would be an inference, not evidence.",
    verification: "UNVERIFIED",
  },
  {
    id: "EV-1007-E3",
    eventId: "EV-1007",
    label: "Tokenized MU price reaction",
    source: SOURCES.exchangeFeed,
    capturedAt: "2026-01-09T12:40:00Z",
    value: "−2.1 % within 9 minutes",
    numericValue: -2.1,
    unit: "%",
    freshness: "FRESH",
    whyItMatters:
      "The market reacted, which shows relevance — but a reaction is not confirmation of the underlying claim.",
    verification: "SOURCE_CONFIRMED",
  },

  /* ── EV-1008 · QQQ CPI print ────────────────────────────────── */
  {
    id: "EV-1008-E1",
    eventId: "EV-1008",
    label: "Headline CPI print",
    source: SOURCES.bureauStats,
    capturedAt: "2026-01-09T13:30:00Z",
    value: "+0.2 % month over month",
    numericValue: 0.2,
    unit: "% MoM",
    freshness: "AGING",
    whyItMatters:
      "The primary macro number. It matched expectations, which normally means little new information to trade.",
    verification: "SOURCE_CONFIRMED",
  },
  {
    id: "EV-1008-E2",
    eventId: "EV-1008",
    label: "Consensus expectation",
    source: SOURCES.providerDocs,
    capturedAt: "2026-01-09T09:00:00Z",
    value: "+0.2 % month over month",
    numericValue: 0.2,
    unit: "% MoM",
    freshness: "AGING",
    whyItMatters:
      "The comparison point. Print equals expectation means the surprise component — the tradable part — is approximately zero.",
    verification: "SOURCE_CONFIRMED",
  },
  {
    id: "EV-1008-E3",
    eventId: "EV-1008",
    label: "Reference market state",
    source: SOURCES.exchangeFeed,
    capturedAt: "2026-01-09T22:05:00Z",
    value: "Cash reference closed until Monday 09:30 ET",
    numericValue: null,
    unit: null,
    freshness: "AGING",
    whyItMatters:
      "With no fresh reference until Monday, any divergence in the token tonight cannot be validated, only observed.",
    verification: "SOURCE_CONFIRMED",
  },
];

export function evidenceForEvent(eventId: string): EvidenceRecord[] {
  return evidenceRecords.filter((e) => e.eventId === eventId);
}

export function evidenceCountForEvent(eventId: string): number {
  return evidenceRecords.reduce(
    (n, e) => (e.eventId === eventId ? n + 1 : n),
    0
  );
}
