import type {
  ActivityRecord,
  EventBundle,
  InstrumentIdentity,
  MarketEvent,
  MarketObservation,
  PriceSeries,
  SignedReceipt,
} from "@/types/domain";
import { instrumentCatalog } from "@/data/instrumentCatalog";
import { eventFeed } from "@/data/eventFeedData";
import { evidenceForEvent } from "@/data/evidenceRecords";
import {
  decisionForEvent,
  executionForEvent,
  receiptForEvent,
  riskForEvent,
} from "@/data/decisionRecords";
import {
  findObservation,
  findPriceSeries,
} from "@/data/marketOverviewData";

/**
 * Preview data provider — deterministic, local, and clearly illustrative.
 *
 * Everything the UI renders flows through this provider. When the real
 * backend lands, implement `MarketDataProvider`, `DecisionService`, and
 * `ReceiptVerificationService` (see marketDataProvider.ts) against actual
 * endpoints and swap the binding — no presentation changes required.
 */

const latency = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function listInstruments(): Promise<InstrumentIdentity[]> {
  await latency(40);
  return instrumentCatalog.map(({ note: _note, decisionState: _d, ...rest }) => rest);
}

async function getMarketOverview(): Promise<MarketObservation[]> {
  await latency(40);
  return instrumentCatalog.map((i) => {
    const obs = findObservation(i.symbol);
    return (
      obs ?? {
        symbol: i.symbol,
        priceUsd: 0,
        changePct24h: 0,
        observedAt: "",
        freshness: "STALE" as const,
        sessionNote: "No observation in the preview workspace",
      }
    );
  });
}

async function getPriceSeries(symbol: string): Promise<PriceSeries | null> {
  await latency(30);
  return findPriceSeries(symbol);
}

async function listEvents(): Promise<MarketEvent[]> {
  await latency(50);
  return [...eventFeed].sort(
    (a, b) => Date.parse(b.occurredAt) - Date.parse(a.occurredAt)
  );
}

async function getEventBundle(eventId: string): Promise<EventBundle | null> {
  await latency(60);
  const event = eventFeed.find((e) => e.id === eventId);
  if (!event) return null;

  const decision = decisionForEvent(eventId);
  const risk = riskForEvent(eventId);
  const execution = executionForEvent(eventId);
  const receipt = receiptForEvent(eventId);
  if (!decision || !risk || !execution || !receipt) return null;

  return {
    event,
    instrument: event.instrumentSymbol
      ? instrumentCatalog.find((i) => i.symbol === event.instrumentSymbol) ?? null
      : null,
    observation: event.instrumentSymbol
      ? findObservation(event.instrumentSymbol)
      : null,
    evidence: evidenceForEvent(eventId),
    decision,
    risk,
    execution,
    receipt,
    priceSeries: event.instrumentSymbol
      ? findPriceSeries(event.instrumentSymbol)
      : null,
  };
}

const activity: ActivityRecord[] = [
  {
    eventId: "EV-1001",
    instrumentSymbol: "NVDA",
    headline: "NVIDIA reports Q3 revenue and EPS above consensus",
    decisionState: "PROCEED",
    riskOutcome: "APPROVED",
    execution: "FILLED",
    occurredAt: "2026-01-09T21:16:00Z",
    sourceKind: "NEWS_WIRE",
    receiptDigest: "a41f…c7e2",
  },
  {
    eventId: "EV-1008",
    instrumentSymbol: "QQQ",
    headline: "CPI prints in line with expectations",
    decisionState: "WAIT",
    riskOutcome: "REFUSED",
    execution: "NONE",
    occurredAt: "2026-01-09T13:30:00Z",
    sourceKind: "PROVIDER_DOC",
    receiptDigest: "6f8e…5c07",
  },
  {
    eventId: "EV-1007",
    instrumentSymbol: "MU",
    headline: "Commerce department floats memory-module tariff review",
    decisionState: "NO ACTION",
    riskOutcome: "APPROVED",
    execution: "NONE",
    occurredAt: "2026-01-09T12:31:00Z",
    sourceKind: "NEWS_WIRE",
    receiptDigest: "e461…f118",
  },
  {
    eventId: "EV-1004",
    instrumentSymbol: "COIN",
    headline: "COIN tokenized price gaps while reference quote lags",
    decisionState: "WAIT",
    riskOutcome: "REFUSED",
    execution: "NONE",
    occurredAt: "2026-01-09T20:58:00Z",
    sourceKind: "EXCHANGE_FEED",
    receiptDigest: "9f2c…48be",
  },
  {
    eventId: "EV-1003",
    instrumentSymbol: "META",
    headline: "Meta wins FDA approval for neural wristband, filing shows",
    decisionState: "REJECT",
    riskOutcome: "REFUSED",
    execution: "REFUSED",
    occurredAt: "2026-01-09T19:47:00Z",
    sourceKind: "NEWS_WIRE",
    receiptDigest: "3e8b…d4f0",
  },
  {
    eventId: "EV-1002",
    instrumentSymbol: "TSLA",
    headline: "Report: Tesla near multi-year battery supply contract",
    decisionState: "REJECT",
    riskOutcome: "REFUSED",
    execution: "REFUSED",
    occurredAt: "2026-01-09T18:05:00Z",
    sourceKind: "NEWS_WIRE",
    receiptDigest: "7c0d…91ab",
  },
  {
    eventId: "EV-1005",
    instrumentSymbol: "AMZN",
    headline: "Amazon 8-K discloses AWS segment pricing update",
    decisionState: "REDUCE",
    riskOutcome: "REDUCED",
    execution: "FILLED",
    occurredAt: "2026-01-09T14:22:00Z",
    sourceKind: "SEC_EDGAR",
    receiptDigest: "b57a…0e63",
  },
  {
    eventId: "EV-1006",
    instrumentSymbol: "AAPL",
    headline: "Apple declares quarterly dividend, record date unchanged",
    decisionState: "NO ACTION",
    riskOutcome: "APPROVED",
    execution: "NONE",
    occurredAt: "2026-01-08T21:40:00Z",
    sourceKind: "SEC_EDGAR",
    receiptDigest: "c1d9…7a35",
  },
];

async function listActivity(): Promise<ActivityRecord[]> {
  await latency(45);
  return [...activity].sort(
    (a, b) => Date.parse(b.occurredAt) - Date.parse(a.occurredAt)
  );
}

async function getReceipt(eventId: string): Promise<SignedReceipt | null> {
  await latency(30);
  return receiptForEvent(eventId);
}

async function explainVerification(receipt: SignedReceipt): Promise<string> {
  await latency(20);
  if (receipt.verification === "STRUCTURE_VERIFIED") {
    return "Structure checks passed in the preview workspace: every expected field is present and internally consistent. This is not a cryptographic verification — no real signature exists in the preview environment.";
  }
  return "This is a simulated receipt presentation. In production, the digest, signature, and timestamp authority could be independently checked outside AFTERMATH. Nothing here should be read as a verified live record.";
}

export const previewDataProvider = {
  listInstruments,
  getMarketOverview,
  getPriceSeries,
  listEvents,
  getEventBundle,
  listActivity,
  getReceipt,
  explainVerification,
} as const;
