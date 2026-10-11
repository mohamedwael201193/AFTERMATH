/**
 * AFTERMATH domain types.
 *
 * This is the data boundary of the application. The preview data provider
 * implements these shapes today; a real API provider can implement the same
 * interfaces later without touching presentation code.
 *
 * Naming rule: every value that comes from the illustrative preview workspace
 * must remain obviously illustrative — receipts are presentation previews,
 * observations carry their source timestamps, and nothing here claims to be
 * a live measurement.
 */

/* ── Instruments ──────────────────────────────────────────────── */

export type InstrumentKind = "EQUITY_TOKEN" | "INDEX_TOKEN" | "CRYPTO_LINKED";

export interface InstrumentIdentity {
  /** Ticker-style symbol of the tradable tokenized instrument. */
  symbol: string;
  /** Human-readable instrument name. */
  name: string;
  kind: InstrumentKind;
  /** Company behind the reference equity, when relevant. */
  company: string | null;
  /** Underlying US equity reference symbol, when one exists. */
  referenceSymbol: string | null;
  /** Venue context for the tokenized instrument. */
  venue: string;
}

/* ── Market observations ──────────────────────────────────────── */

export type Freshness = "FRESH" | "AGING" | "STALE";

export interface MarketObservation {
  symbol: string;
  /** Illustrative last observed price in USD. */
  priceUsd: number;
  /** Change over the trailing 24h window, in percent. Null when the source did not provide it. */
  changePct24h: number | null;
  /** ISO 8601 timestamp of the observation. */
  observedAt: string;
  freshness: Freshness;
  /** Human-readable session context, e.g. "US cash market closed". */
  sessionNote: string;
}

/* ── Sources ──────────────────────────────────────────────────── */

export type SourceKind =
  | "NEWS_WIRE"
  | "SEC_EDGAR"
  | "EXCHANGE_FEED"
  | "PROVIDER_DOC"
  | "RISK_ENGINE";

export type SourceTrust = "PRIMARY" | "SECONDARY" | "UNKNOWN";

export interface SourceIdentity {
  id: string;
  name: string;
  kind: SourceKind;
  trust: SourceTrust;
}

/* ── Events ───────────────────────────────────────────────────── */

export type EventCategory =
  | "EARNINGS"
  | "FILING"
  | "HEADLINE"
  | "MACRO"
  | "REFERENCE_GAP"
  | "MARKET";

export type EventStatus = "NEW" | "REVIEWING" | "RESOLVED";

export interface MarketEvent {
  id: string;
  headline: string;
  /** Plain-language explanation of why the event might matter. */
  summary: string;
  instrumentSymbol: string | null;
  category: EventCategory;
  /** ISO 8601 timestamp of when the event was observed. */
  occurredAt: string;
  source: SourceIdentity;
  /** 0..1 — how complete the current evidence bundle is. */
  evidenceCompleteness: number;
  decisionState: DecisionState;
  status: EventStatus;
}

/* ── Decisions ────────────────────────────────────────────────── */

export type DecisionState =
  | "PROCEED"
  | "REDUCE"
  | "WAIT"
  | "REJECT"
  | "NO ACTION";

export interface ProposedAction {
  side: "BUY" | "SELL";
  symbol: string;
  sizeTokens: number;
  notionalUsd: number;
  rationale: string;
}

export interface AIDecision {
  eventId: string;
  state: DecisionState;
  /** 0..1 model-stated confidence. Absent when the model was not called. */
  confidence: number;
  /** True only when a model proposal was recorded for this decision. */
  modelCalled?: boolean;
  /** One-sentence plain-language verdict. */
  plainLanguage: string;
  /** Short reasoning bullets, each tied to evidence where possible. */
  reasoning: string[];
  /** Conditions that would invalidate this reasoning. */
  invalidationConditions: string[];
  proposedAction: ProposedAction | null;
}

/* ── Risk engine ──────────────────────────────────────────────── */

export type RiskCheckStatus = "PASS" | "WARN" | "FAIL";

export interface RiskCheck {
  id: string;
  /** Short human label, e.g. "Data freshness". */
  label: string;
  status: RiskCheckStatus;
  /** Plain-language explanation of what was checked and why. */
  detail: string;
  /** The deterministic limit, when the check defines one. */
  limit: string | null;
  /** What was actually observed. */
  observed: string | null;
}

export type RiskOutcome = "APPROVED" | "REDUCED" | "REFUSED";

export interface RiskEngineResult {
  eventId: string;
  outcome: RiskOutcome;
  /** Plain-language explanation of the deterministic outcome. */
  plainLanguage: string;
  checks: RiskCheck[];
  /** When REDUCED — the fraction of the proposed size that survives. */
  sizeMultiplier: number | null;
}

/* ── Evidence ─────────────────────────────────────────────────── */

export type EvidenceVerification =
  | "SOURCE_CONFIRMED"
  | "UNVERIFIED"
  | "CONFLICTING";

export interface EvidenceRecord {
  id: string;
  eventId: string;
  /** What fact this record states, e.g. "Q3 diluted EPS". */
  label: string;
  source: SourceIdentity;
  /** ISO 8601 timestamp when the fact was captured. */
  capturedAt: string;
  /** Rendered value with units, e.g. "0.84 USD". */
  value: string;
  /** Machine value when numeric. */
  numericValue: number | null;
  unit: string | null;
  freshness: Freshness;
  /** Why this record matters for the decision. */
  whyItMatters: string;
  verification: EvidenceVerification;
}

/* ── Paper execution ──────────────────────────────────────────── */

export interface CostEstimate {
  label: string;
  usd: number;
}

export interface PaperExecution {
  eventId: string;
  /** FILL — simulated fill; REFUSAL — order refused; NONE — no order attempted. */
  kind: "FILL" | "REFUSAL" | "NONE";
  symbol: string;
  side: "BUY" | "SELL" | null;
  filledTokens: number;
  avgPriceUsd: number | null;
  feeUsd: number;
  slippageUsd: number;
  totalCostUsd: number;
  /** ISO 8601 timestamp of the simulated execution. */
  executedAt: string;
  /** Plain-language note about the result. */
  note: string;
  /** Estimated cost breakdown, when a fill exists. */
  costBreakdown: CostEstimate[];
}

/* ── Receipts ─────────────────────────────────────────────────── */

export type ReceiptVerification =
  /** No signed receipt is stored for this row. */
  | "UNAVAILABLE"
  /** Preview presentation only — no real signature exists. */
  | "UNVERIFIED_PREVIEW"
  /** Structure checks passed in the preview workspace. */
  | "STRUCTURE_VERIFIED"
  /** The production public key verified the signature. The external anchor is not confirmed. */
  | "UNCONFIRMED"
  /** The production public key verified the signature. */
  | "SIGNATURE_VERIFIED";

export interface SignedReceipt {
  eventId: string;
  /** Truncated digest preview (illustrative). */
  digestPreview: string;
  algorithm: string;
  timestampAuthority: string;
  createdAt: string;
  verification: ReceiptVerification;
  /** Fields covered by the illustrative record. */
  fieldsIncluded: string[];
}

/* ── Activity / history ───────────────────────────────────────── */

export interface ActivityRecord {
  eventId: string;
  instrumentSymbol: string;
  headline: string;
  decisionState: DecisionState;
  riskOutcome: RiskOutcome;
  execution: "FILLED" | "REFUSED" | "NONE";
  occurredAt: string;
  sourceKind: SourceKind;
  receiptDigest: string | null;
  /** False when the cycle stopped before the model and the governor. */
  governorCalled?: boolean;
}

/* ── Price series ─────────────────────────────────────────────── */

export interface PricePoint {
  /** ISO 8601 timestamp. */
  t: string;
  /** Price in USD. */
  p: number;
}

export interface PriceSeriesPoint {
  t: string;
  p: number;
  event: boolean;
}

export interface PriceSeries {
  symbol: string;
  /** Deterministic illustrative series. */
  points: PriceSeriesPoint[];
  markers: Array<{
    t: string;
    label: string;
    kind: "EVENT" | "SESSION";
  }>;
}

/* ── The full bundle shown in the decision detail panel ───────── */

export interface EventBundle {
  event: MarketEvent;
  instrument: InstrumentIdentity | null;
  observation: MarketObservation | null;
  evidence: EvidenceRecord[];
  decision: AIDecision;
  risk: RiskEngineResult;
  execution: PaperExecution;
  receipt: SignedReceipt;
  priceSeries: PriceSeries | null;
}
