import type { MarketEvent } from "@/types/domain";
import { SOURCES } from "@/data/sources";

/**
 * Illustrative event feed for the preview workspace.
 *
 * Scenario coverage (see decisionRecords.ts for the paired reasoning):
 *  1. EV-1001 NVDA — complete evidence, approved paper outcome.
 *  2. EV-1002 TSLA — missing-evidence refusal.
 *  3. EV-1003 META — misleading headline, adversarial refusal.
 *  4. EV-1004 COIN — stale reference data, wait.
 *  5. EV-1005 AMZN — risk-based size reduction.
 *  6. EV-1006 AAPL — receipt structure-verification example.
 *  7. EV-1007 MU — unspecified macro headline, no action.
 *  8. EV-1008 QQQ — macro print, wait for cash open.
 *
 * Headlines are illustrative scenarios, not claims about real news.
 */

export const eventFeed: MarketEvent[] = [
  {
    id: "EV-1001",
    headline: "NVIDIA reports Q3 revenue and EPS above consensus",
    summary:
      "NVIDIA's quarterly results landed after the US cash close. Because tokenized NVDA keeps trading, the size of the beat and the freshness of the filing decide whether a paper trade is justified tonight.",
    instrumentSymbol: "NVDA",
    category: "EARNINGS",
    occurredAt: "2026-01-09T21:16:00Z",
    source: SOURCES.globalWire,
    evidenceCompleteness: 0.94,
    decisionState: "PROCEED",
    status: "RESOLVED",
  },
  {
    id: "EV-1002",
    headline: "Report: Tesla near multi-year battery supply contract",
    summary:
      "A single wire story cites unnamed sources for a supply agreement. No filing backs it yet. The system has to decide whether a headline alone is ever enough to trade on.",
    instrumentSymbol: "TSLA",
    category: "HEADLINE",
    occurredAt: "2026-01-09T18:05:00Z",
    source: SOURCES.globalWire,
    evidenceCompleteness: 0.45,
    decisionState: "REJECT",
    status: "RESOLVED",
  },
  {
    id: "EV-1003",
    headline: "Meta wins FDA approval for neural wristband, filing shows",
    summary:
      "The headline claims an approval tied to a specific filing. Checking the primary record matters here: if the filing says something weaker, the story is misleading and must not be traded.",
    instrumentSymbol: "META",
    category: "HEADLINE",
    occurredAt: "2026-01-09T19:47:00Z",
    source: SOURCES.globalWire,
    evidenceCompleteness: 0.62,
    decisionState: "REJECT",
    status: "RESOLVED",
  },
  {
    id: "EV-1004",
    headline: "COIN tokenized price gaps while reference quote lags",
    summary:
      "Tokenized COIN dropped sharply minutes before the cash close, but the reference quote is over an hour old. Acting now would mean guessing which price is wrong.",
    instrumentSymbol: "COIN",
    category: "REFERENCE_GAP",
    occurredAt: "2026-01-09T20:58:00Z",
    source: SOURCES.exchangeFeed,
    evidenceCompleteness: 0.71,
    decisionState: "WAIT",
    status: "REVIEWING",
  },
  {
    id: "EV-1005",
    headline: "Amazon 8-K discloses AWS segment pricing update",
    summary:
      "A primary filing confirms a pricing-mechanics update for AWS reserved capacity. The event is real and modestly positive — the question is whether after-open liquidity supports the intended size.",
    instrumentSymbol: "AMZN",
    category: "FILING",
    occurredAt: "2026-01-09T14:22:00Z",
    source: SOURCES.edgar,
    evidenceCompleteness: 0.88,
    decisionState: "REDUCE",
    status: "RESOLVED",
  },
  {
    id: "EV-1006",
    headline: "Apple declares quarterly dividend, record date unchanged",
    summary:
      "A routine dividend declaration that matches the prior quarter. There is nothing to trade, but the conclusion — and the record proving why nothing was done — is still worth keeping.",
    instrumentSymbol: "AAPL",
    category: "FILING",
    occurredAt: "2026-01-08T21:40:00Z",
    source: SOURCES.edgar,
    evidenceCompleteness: 0.96,
    decisionState: "NO ACTION",
    status: "RESOLVED",
  },
  {
    id: "EV-1007",
    headline: "Commerce department floats memory-module tariff review",
    summary:
      "A possible tariff review is headline-relevant to memory makers, but scope and timing are unspecified. Connecting it to a specific company's earnings would be speculation.",
    instrumentSymbol: "MU",
    category: "MACRO",
    occurredAt: "2026-01-09T12:31:00Z",
    source: SOURCES.globalWire,
    evidenceCompleteness: 0.58,
    decisionState: "NO ACTION",
    status: "RESOLVED",
  },
  {
    id: "EV-1008",
    headline: "CPI prints in line with expectations",
    summary:
      "The index-level print matched expectations. With the cash reference now closed until Monday, the tokenized price already reflects the news — there is nothing new to act on tonight.",
    instrumentSymbol: "QQQ",
    category: "MACRO",
    occurredAt: "2026-01-09T13:30:00Z",
    source: SOURCES.bureauStats,
    evidenceCompleteness: 0.83,
    decisionState: "WAIT",
    status: "REVIEWING",
  },
];

export function findEvent(eventId: string): MarketEvent | null {
  return eventFeed.find((e) => e.id === eventId) ?? null;
}
