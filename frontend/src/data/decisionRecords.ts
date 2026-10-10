import type {
  AIDecision,
  PaperExecution,
  RiskEngineResult,
  SignedReceipt,
} from "@/types/domain";

/**
 * Decision, risk, execution, and receipt records for the preview workspace.
 *
 * The reasoning here is written to be read. Every decision cites evidence
 * records that exist in evidenceRecords.ts, every risk outcome is the
 * deterministic result of the checks below it, and every receipt is an
 * illustrative presentation — never a cryptographic claim.
 */

export const decisionRecords: AIDecision[] = [
  {
    eventId: "EV-1001",
    state: "PROCEED",
    confidence: 0.78,
    plainLanguage:
      "The results are real, confirmed by the primary filing, and priced against a fresh executable quote — a small paper buy is justified.",
    reasoning: [
      "Revenue (45.26 B USD) and EPS (0.84 USD) both cleared consensus in the wire release, and the 8-K on EDGAR confirms the release exists (EV-1001-E3).",
      "Every cited figure traces to a captured evidence record; none were invented or substituted.",
      "The tokenized price observation (189.42 USD at 22:08 UTC) is two minutes old, so execution can be costed against reality rather than a stale reference.",
      "Order-book depth of 18.4 k USD within 0.5 % of mid comfortably supports a one-token paper order.",
    ],
    invalidationConditions: [
      "The 8-K is amended or withdrawn.",
      "Tokenized price detaches more than 2 % from the reference-implied fair value before execution.",
      "Order-book depth collapses below the refusal floor before the order is simulated.",
    ],
    proposedAction: {
      side: "BUY",
      symbol: "NVDA",
      sizeTokens: 1,
      notionalUsd: 189.42,
      rationale: "Post-filing drift with complete evidence and fresh liquidity.",
    },
  },
  {
    eventId: "EV-1002",
    state: "REJECT",
    confidence: 0.31,
    plainLanguage:
      "One secondary headline with unnamed sources and a silent primary record is not evidence — the system refuses to trade.",
    reasoning: [
      "The only positive claim (EV-1002-E1) comes from a single wire story citing unnamed people.",
      "The EDGAR search (EV-1002-E2) found zero relevant filings today, so the primary record contradicts nothing and confirms nothing.",
      "No company statement exists to raise the bundle above one unverified source.",
      "Trading on this pattern is exactly how misleading headlines cause losses outside market hours.",
    ],
    invalidationConditions: [
      "Tesla files an 8-K that confirms the agreement.",
      "A second independent wire confirms the story with named sources.",
    ],
    proposedAction: null,
  },
  {
    eventId: "EV-1003",
    state: "REJECT",
    confidence: 0.22,
    plainLanguage:
      "The headline says more than the filing does. The primary record contradicts the claim, and the wire later corrected itself — no trade.",
    reasoning: [
      "The headline (EV-1003-E1) claims an approval and attributes it to a filing.",
      "The cited filing itself (EV-1003-E2) contains no approval language — the claim does not trace to its alleged source.",
      "An independent register check (EV-1003-E3) also finds no approval record.",
      "The originating wire published a correction (EV-1003-E4), confirming the adversarial finding.",
    ],
    invalidationConditions: [
      "The public device register is updated with an approval entry tied to the product.",
      "Meta files an amended document that contains approval language.",
    ],
    proposedAction: null,
  },
  {
    eventId: "EV-1004",
    state: "WAIT",
    confidence: 0.44,
    plainLanguage:
      "The token moved, the reference didn't keep up, and no one can say which side is wrong yet — so the system waits for a fresh reference.",
    reasoning: [
      "Tokenized COIN traded at 281.35 USD (EV-1004-E1) while the reference quote stood at 299.10 USD — a −5.9 % divergence (EV-1004-E3).",
      "The reference quote is 65 minutes old (EV-1004-E2), which is beyond the freshness limit for gap events.",
      "Both prices cannot be right. Acting now would mean guessing whether the token leads or misleads.",
      "Depth of 7.1 k USD is above the refusal floor, so the block is purely about stale data, not liquidity.",
    ],
    invalidationConditions: [
      "A fresh reference quote arrives and divergence resolves below 1.5 %.",
      "The exchange feed reports an outage or correction explaining the gap.",
    ],
    proposedAction: null,
  },
  {
    eventId: "EV-1005",
    state: "REDUCE",
    confidence: 0.66,
    plainLanguage:
      "The filing is real and mildly positive, but liquidity is thin for the intended size — so the engine cuts the order to 35 % instead of skipping it.",
    reasoning: [
      "The 8-K on EDGAR (EV-1005-E1) confirms the AWS pricing update is a real, filed event.",
      "The materiality excerpt (EV-1005-E2) shows a mechanics update rather than a demand shock — modest expected impact.",
      "Order-book depth of 2.3 k USD within 0.5 % of mid (EV-1005-E4) is well below the full-size comfort band.",
      "A smaller order keeps execution costs inside the deterministic limits while still recording a position.",
    ],
    invalidationConditions: [
      "Depth recovers above the full-size band before execution.",
      "An amended filing materially changes the pricing update.",
    ],
    proposedAction: {
      side: "BUY",
      symbol: "AMZN",
      sizeTokens: 2,
      notionalUsd: 455.8,
      rationale: "Confirmed filing with positive read, sized before the liquidity check.",
    },
  },
  {
    eventId: "EV-1006",
    state: "NO ACTION",
    confidence: 0.81,
    plainLanguage:
      "The dividend matches last quarter and the record date is unchanged — there is nothing to trade, and the system records exactly that.",
    reasoning: [
      "The declared dividend of 0.25 USD per share (EV-1006-E1) equals the prior quarter (EV-1006-E2).",
      "The record-date consistency check (EV-1006-E3) found no changes.",
      "No surprise component exists to trade on, and none is needed to justify the record.",
    ],
    invalidationConditions: [
      "A special dividend or changed record date is later disclosed.",
    ],
    proposedAction: null,
  },
  {
    eventId: "EV-1007",
    state: "NO ACTION",
    confidence: 0.38,
    plainLanguage:
      "A review with no named companies, scope, or dates is not tradeable information — connecting it to MU would be speculation.",
    reasoning: [
      "The headline (EV-1007-E1) describes a process being floated, not a decision made.",
      "No companies are named in the story (EV-1007-E2); the link to a specific ticker is an inference.",
      "The −2.1 % price reaction (EV-1007-E3) shows the market cares, but a reaction is not confirmation.",
    ],
    invalidationConditions: [
      "A named scope covering memory modules is published with dates.",
      "A company filing quantifies exposure.",
    ],
    proposedAction: null,
  },
  {
    eventId: "EV-1008",
    state: "WAIT",
    confidence: 0.51,
    plainLanguage:
      "The print matched expectations and the cash reference is closed until Monday — there is nothing new to act on tonight.",
    reasoning: [
      "Headline CPI of +0.2 % MoM (EV-1008-E1) matched the consensus (EV-1008-E2), so the surprise component is approximately zero.",
      "The cash reference is closed until Monday 09:30 ET (EV-1008-E3); token divergence tonight can be observed, not validated.",
      "Waiting is cheaper than paying weekend spreads to express no new information.",
    ],
    invalidationConditions: [
      "A materially different core print is published in the detailed tables.",
      "Monday's cash open reveals a divergence the tokenized market has already priced.",
    ],
    proposedAction: null,
  },
];

export const riskResults: RiskEngineResult[] = [
  {
    eventId: "EV-1001",
    outcome: "APPROVED",
    plainLanguage:
      "All deterministic checks passed. The language model cannot loosen these limits — it can only work inside them.",
    checks: [
      { id: "rc-fresh", label: "Data freshness", status: "PASS", detail: "Post-event prices must be recent enough to cost an order against.", limit: "≤ 45 min old", observed: "2 min old" },
      { id: "rc-ref", label: "Reference price validity", status: "PASS", detail: "The reference move must trace to a primary record, not a headline.", limit: "Primary filing required", observed: "8-K confirmed" },
      { id: "rc-depth", label: "Order-book depth", status: "PASS", detail: "Enough visible liquidity to fill without dominating the book.", limit: "≥ 5 k USD within 0.5 %", observed: "18.4 k USD" },
      { id: "rc-cost", label: "Expected transaction costs", status: "PASS", detail: "Estimated all-in cost must stay a small fraction of notional.", limit: "≤ 0.5 % of notional", observed: "0.19 %" },
      { id: "rc-size", label: "Position-size limit", status: "PASS", detail: "Single paper orders are capped relative to workspace notional.", limit: "≤ 2 % of workspace notional", observed: "1.9 %" },
      { id: "rc-evid", label: "Evidence completeness", status: "PASS", detail: "Enough of the expected evidence bundle exists to justify a PROCEED.", limit: "≥ 0.90", observed: "0.94" },
    ],
    sizeMultiplier: null,
  },
  {
    eventId: "EV-1002",
    outcome: "REFUSED",
    plainLanguage:
      "Missing essential evidence. The risk engine refuses rather than force a trade — a refusal is a successful outcome here.",
    checks: [
      { id: "rc-evid", label: "Evidence completeness", status: "FAIL", detail: "The bundle never reached the threshold a trade requires.", limit: "≥ 0.90", observed: "0.45" },
      { id: "rc-src", label: "Source consistency", status: "FAIL", detail: "Headline-driven events need at least two independent sources.", limit: "≥ 2 independent sources", observed: "1 unverified source" },
      { id: "rc-fresh", label: "Data freshness", status: "PASS", detail: "The observations themselves are recent — freshness is not the problem.", limit: "≤ 45 min old", observed: "14 min old" },
    ],
    sizeMultiplier: null,
  },
  {
    eventId: "EV-1003",
    outcome: "REFUSED",
    plainLanguage:
      "The adversarial check found an unsupported claim. The AI's read was rejected before any order could exist.",
    checks: [
      { id: "rc-adv", label: "Adversarial claim check", status: "FAIL", detail: "Every material claim must trace to a primary record.", limit: "0 unsupported claims", observed: "1 unsupported claim" },
      { id: "rc-src", label: "Source consistency", status: "FAIL", detail: "The story and its cited filing disagree.", limit: "No source conflicts", observed: "2 conflicting records" },
      { id: "rc-evid", label: "Evidence completeness", status: "WARN", detail: "The bundle is substantial but internally contradictory.", limit: "≥ 0.90", observed: "0.62" },
    ],
    sizeMultiplier: null,
  },
  {
    eventId: "EV-1004",
    outcome: "REFUSED",
    plainLanguage:
      "Stale reference data. With no fresh reference, the risk engine blocks execution and the decision stands as WAIT.",
    checks: [
      { id: "rc-ref", label: "Reference price validity", status: "FAIL", detail: "Gap events require a fresh reference to judge which price is wrong.", limit: "Reference age ≤ 30 min", observed: "65 min old" },
      { id: "rc-fresh", label: "Data freshness", status: "WARN", detail: "The token price itself is recent; only the reference lags.", limit: "≤ 45 min old", observed: "12 min old" },
      { id: "rc-depth", label: "Order-book depth", status: "WARN", detail: "Above the refusal floor but below the comfort band — noted, not blocking.", limit: "≥ 5 k USD within 0.5 %", observed: "7.1 k USD" },
    ],
    sizeMultiplier: null,
  },
  {
    eventId: "EV-1005",
    outcome: "REDUCED",
    plainLanguage:
      "Liquidity is too thin for the proposed size. The engine cut the order to 35 % — the AI cannot overrule this.",
    checks: [
      { id: "rc-evid", label: "Evidence completeness", status: "PASS", detail: "A primary filing backs the event.", limit: "≥ 0.90", observed: "0.88 (filing-confirmed)" },
      { id: "rc-depth", label: "Order-book depth", status: "WARN", detail: "Depth below the full-size band forces a size cut, not a refusal.", limit: "≥ 5 k USD for full size", observed: "2.3 k USD" },
      { id: "rc-cost", label: "Expected transaction costs", status: "WARN", detail: "At the requested size, estimated costs approached the cap.", limit: "≤ 0.5 % of notional", observed: "0.42 % at requested size" },
      { id: "rc-fresh", label: "Data freshness", status: "PASS", detail: "All observations are recent.", limit: "≤ 45 min old", observed: "9 min old" },
    ],
    sizeMultiplier: 0.35,
  },
  {
    eventId: "EV-1006",
    outcome: "APPROVED",
    plainLanguage:
      "No proposed action to limit. The checks were recorded anyway, because “nothing happened” should be auditable too.",
    checks: [
      { id: "rc-evid", label: "Evidence completeness", status: "PASS", detail: "The routine event is fully documented.", limit: "≥ 0.90", observed: "0.96" },
      { id: "rc-fresh", label: "Data freshness", status: "PASS", detail: "Records are aging but the event is already resolved.", limit: "≤ 45 min old at decision time", observed: "7 min old at decision time" },
    ],
    sizeMultiplier: null,
  },
  {
    eventId: "EV-1007",
    outcome: "APPROVED",
    plainLanguage:
      "No proposed action to limit. The record documents why the headline was judged insufficiently specific.",
    checks: [
      { id: "rc-evid", label: "Evidence completeness", status: "WARN", detail: "Only unverified secondary material exists — acceptable for NO ACTION, never for a trade.", limit: "≥ 0.90 to trade", observed: "0.58" },
      { id: "rc-src", label: "Source consistency", status: "WARN", detail: "A single unnamed-source story.", limit: "≥ 2 independent sources to trade", observed: "1 unverified source" },
    ],
    sizeMultiplier: null,
  },
  {
    eventId: "EV-1008",
    outcome: "REFUSED",
    plainLanguage:
      "No fresh reference exists to validate any order tonight. The refusal is the mechanism that makes WAIT enforceable.",
    checks: [
      { id: "rc-ref", label: "Reference price validity", status: "FAIL", detail: "The cash reference is closed until Monday.", limit: "Fresh reference required", observed: "Closed · 2 days" },
      { id: "rc-evid", label: "Evidence completeness", status: "PASS", detail: "The macro print itself is fully documented.", limit: "≥ 0.90", observed: "0.83 (macro event)" },
    ],
    sizeMultiplier: null,
  },
];

export const paperExecutions: PaperExecution[] = [
  {
    eventId: "EV-1001",
    kind: "FILL",
    symbol: "NVDA",
    side: "BUY",
    filledTokens: 1,
    avgPriceUsd: 189.58,
    feeUsd: 0.19,
    slippageUsd: 0.16,
    totalCostUsd: 0.35,
    executedAt: "2026-01-09T22:09:00Z",
    note: "Simulated fill against the two-minute-old book. Costs are estimates, not realized profits.",
    costBreakdown: [
      { label: "Exchange fee", usd: 0.19 },
      { label: "Slippage vs mid", usd: 0.16 },
    ],
  },
  {
    eventId: "EV-1002",
    kind: "REFUSAL",
    symbol: "TSLA",
    side: null,
    filledTokens: 0,
    avgPriceUsd: null,
    feeUsd: 0,
    slippageUsd: 0,
    totalCostUsd: 0,
    executedAt: "2026-01-09T18:26:00Z",
    note: "No order was simulated: the evidence bundle never reached the minimum completeness.",
    costBreakdown: [],
  },
  {
    eventId: "EV-1003",
    kind: "REFUSAL",
    symbol: "META",
    side: null,
    filledTokens: 0,
    avgPriceUsd: null,
    feeUsd: 0,
    slippageUsd: 0,
    totalCostUsd: 0,
    executedAt: "2026-01-09T20:17:00Z",
    note: "No order was simulated: the adversarial check rejected the decision's supporting claims.",
    costBreakdown: [],
  },
  {
    eventId: "EV-1004",
    kind: "NONE",
    symbol: "COIN",
    side: null,
    filledTokens: 0,
    avgPriceUsd: null,
    feeUsd: 0,
    slippageUsd: 0,
    totalCostUsd: 0,
    executedAt: "2026-01-09T21:02:00Z",
    note: "Waiting: no order simulated while the reference quote is stale.",
    costBreakdown: [],
  },
  {
    eventId: "EV-1005",
    kind: "FILL",
    symbol: "AMZN",
    side: "BUY",
    filledTokens: 0.7,
    avgPriceUsd: 229.78,
    feeUsd: 0.23,
    slippageUsd: 0.41,
    totalCostUsd: 0.64,
    executedAt: "2026-01-09T14:31:00Z",
    note: "Reduced to 35 % of the proposed size to respect thin order-book depth.",
    costBreakdown: [
      { label: "Exchange fee", usd: 0.23 },
      { label: "Slippage vs mid", usd: 0.41 },
    ],
  },
  {
    eventId: "EV-1006",
    kind: "NONE",
    symbol: "AAPL",
    side: null,
    filledTokens: 0,
    avgPriceUsd: null,
    feeUsd: 0,
    slippageUsd: 0,
    totalCostUsd: 0,
    executedAt: "2026-01-08T21:50:00Z",
    note: "No order simulated — the decision was NO ACTION.",
    costBreakdown: [],
  },
  {
    eventId: "EV-1007",
    kind: "NONE",
    symbol: "MU",
    side: null,
    filledTokens: 0,
    avgPriceUsd: null,
    feeUsd: 0,
    slippageUsd: 0,
    totalCostUsd: 0,
    executedAt: "2026-01-09T12:46:00Z",
    note: "No order simulated — the decision was NO ACTION.",
    costBreakdown: [],
  },
  {
    eventId: "EV-1008",
    kind: "NONE",
    symbol: "QQQ",
    side: null,
    filledTokens: 0,
    avgPriceUsd: null,
    feeUsd: 0,
    slippageUsd: 0,
    totalCostUsd: 0,
    executedAt: "2026-01-09T13:41:00Z",
    note: "Waiting: no order simulated until a fresh reference exists.",
    costBreakdown: [],
  },
];

export const signedReceipts: SignedReceipt[] = [
  {
    eventId: "EV-1001",
    digestPreview: "a41f 92c0 … 5d18 c7e2",
    algorithm: "Ed25519 · illustrative",
    timestampAuthority: "Independent RFC 3161 authority · illustrative",
    createdAt: "2026-01-09T22:09:00Z",
    verification: "UNVERIFIED_PREVIEW",
    fieldsIncluded: ["decision state", "confidence", "risk outcome", "execution digest", "evidence digests"],
  },
  {
    eventId: "EV-1002",
    digestPreview: "7c0d 4ab1 … 33f0 91ab",
    algorithm: "Ed25519 · illustrative",
    timestampAuthority: "Independent RFC 3161 authority · illustrative",
    createdAt: "2026-01-09T18:26:00Z",
    verification: "UNVERIFIED_PREVIEW",
    fieldsIncluded: ["decision state", "confidence", "risk outcome", "refusal reason", "evidence digests"],
  },
  {
    eventId: "EV-1003",
    digestPreview: "3e8b 7f2d … c90a d4f0",
    algorithm: "Ed25519 · illustrative",
    timestampAuthority: "Independent RFC 3161 authority · illustrative",
    createdAt: "2026-01-09T20:17:00Z",
    verification: "UNVERIFIED_PREVIEW",
    fieldsIncluded: ["decision state", "confidence", "risk outcome", "adversarial findings", "evidence digests"],
  },
  {
    eventId: "EV-1004",
    digestPreview: "9f2c 615e … 07d3 48be",
    algorithm: "Ed25519 · illustrative",
    timestampAuthority: "Independent RFC 3161 authority · illustrative",
    createdAt: "2026-01-09T21:02:00Z",
    verification: "UNVERIFIED_PREVIEW",
    fieldsIncluded: ["decision state", "confidence", "risk outcome", "stale-reference finding", "evidence digests"],
  },
  {
    eventId: "EV-1005",
    digestPreview: "b57a 03cc … 8e41 0e63",
    algorithm: "Ed25519 · illustrative",
    timestampAuthority: "Independent RFC 3161 authority · illustrative",
    createdAt: "2026-01-09T14:31:00Z",
    verification: "UNVERIFIED_PREVIEW",
    fieldsIncluded: ["decision state", "confidence", "risk outcome", "size multiplier", "execution digest", "evidence digests"],
  },
  {
    eventId: "EV-1006",
    digestPreview: "c1d9 8a77 … b205 7a35",
    algorithm: "Ed25519 · illustrative",
    timestampAuthority: "Independent RFC 3161 authority · illustrative",
    createdAt: "2026-01-08T21:50:00Z",
    verification: "STRUCTURE_VERIFIED",
    fieldsIncluded: ["decision state", "confidence", "risk outcome", "no-action rationale", "evidence digests"],
  },
  {
    eventId: "EV-1007",
    digestPreview: "e461 9b3f … 7c2a f118",
    algorithm: "Ed25519 · illustrative",
    timestampAuthority: "Independent RFC 3161 authority · illustrative",
    createdAt: "2026-01-09T12:46:00Z",
    verification: "UNVERIFIED_PREVIEW",
    fieldsIncluded: ["decision state", "confidence", "risk outcome", "no-action rationale", "evidence digests"],
  },
  {
    eventId: "EV-1008",
    digestPreview: "6f8e 12aa … 90b4 5c07",
    algorithm: "Ed25519 · illustrative",
    timestampAuthority: "Independent RFC 3161 authority · illustrative",
    createdAt: "2026-01-09T13:41:00Z",
    verification: "UNVERIFIED_PREVIEW",
    fieldsIncluded: ["decision state", "confidence", "risk outcome", "wait rationale", "evidence digests"],
  },
];

export function decisionForEvent(eventId: string): AIDecision | null {
  return decisionRecords.find((d) => d.eventId === eventId) ?? null;
}

export function riskForEvent(eventId: string): RiskEngineResult | null {
  return riskResults.find((r) => r.eventId === eventId) ?? null;
}

export function executionForEvent(eventId: string): PaperExecution | null {
  return paperExecutions.find((p) => p.eventId === eventId) ?? null;
}

export function receiptForEvent(eventId: string): SignedReceipt | null {
  return signedReceipts.find((r) => r.eventId === eventId) ?? null;
}
