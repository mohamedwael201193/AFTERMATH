import type {
  ActivityRecord,
  EventBundle,
  InstrumentIdentity,
  MarketEvent,
  MarketObservation,
  PriceSeries,
  SignedReceipt,
} from "@/types/domain";

/**
 * Market data provider boundary.
 *
 * The preview provider (previewDataProvider.ts) implements this interface
 * with deterministic local data. A real backend implements the same
 * interface against live endpoints — presentation code never changes.
 */
export interface MarketDataProvider {
  /** Catalog of instruments the workspace knows about. */
  listInstruments(): Promise<InstrumentIdentity[]>;

  /** Current observations for the catalog, with timestamps and freshness. */
  getMarketOverview(): Promise<MarketObservation[]>;

  /** Deterministic price series with event markers for one instrument. */
  getPriceSeries(symbol: string): Promise<PriceSeries | null>;

  /** Recent events, newest first. */
  listEvents(): Promise<MarketEvent[]>;
}

/**
 * Decision service boundary.
 *
 * In production this calls the reasoning + risk pipeline. In the preview
 * workspace it returns the deterministic scenario bundles.
 */
export interface DecisionService {
  /** Full bundle for one event: evidence, decision, risk, execution, receipt. */
  getEventBundle(eventId: string): Promise<EventBundle | null>;

  /** Compact decision history for the activity ledger. */
  listActivity(): Promise<ActivityRecord[]>;
}

/**
 * Receipt verification boundary.
 *
 * A real implementation checks signatures and timestamp authorities.
 * The preview implementation only describes what could be verified.
 */
export interface ReceiptVerificationService {
  getReceipt(eventId: string): Promise<SignedReceipt | null>;

  /** Human-readable explanation of the verification state. */
  explainVerification(receipt: SignedReceipt): Promise<string>;
}
