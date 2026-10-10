import type {
  ActivityRecord,
  AIDecision,
  EventBundle,
  EvidenceRecord,
  InstrumentIdentity,
  MarketEvent,
  MarketObservation,
  PaperExecution,
  PriceSeries,
  RiskEngineResult,
  SignedReceipt,
} from "@/types/domain";

export interface CycleSnapshot {
  decisionCount: number;
  refusalCount: number;
  fillCount: number;
  reason: string | null;
  decisionId: string | null;
  receiptId: string | null;
  occurredAt: string | null;
  status: string | null;
}

const NAMES: Record<string, string> = {
  NVDAUSDT: "NVIDIA",
  TSLAUSDT: "Tesla",
  AAPLUSDT: "Apple",
  AMZNUSDT: "Amazon",
  MSFTUSDT: "Microsoft",
  METAUSDT: "Meta",
  GOOGLUSDT: "Alphabet",
  COINUSDT: "Coinbase",
  MSTRUSDT: "MicroStrategy",
};

async function readJson(path: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(`/api/read${path}`, { ...init, cache: "no-store" });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const code = body && typeof body === "object" && "error" in body ? String((body as { error?: { code?: string } }).error?.code) : String(response.status);
    throw new Error(code || "backend unavailable");
  }
  return body;
}

function freshness(iso: string): MarketObservation["freshness"] {
  const age = Date.now() - Date.parse(iso);
  if (!Number.isFinite(age)) return "STALE";
  if (age <= 90_000) return "FRESH";
  if (age <= 90 * 60_000) return "AGING";
  return "STALE";
}

function asEvent(row: Record<string, unknown>): MarketEvent {
  const payload = (row.payload || {}) as Record<string, unknown>;
  const book = row.event_type === "book";
  const symbol = String(row.instrument_id || "");
  return {
    id: String(row.id),
    headline: book ? `Bitget order book ${symbol}` : `${row.event_type} ${symbol}`,
    summary: book
      ? `Bid ${payload.bid}, ask ${payload.ask}, spread ${payload.spread_bp} bp, depth ${payload.depth_usdt} USDT within 25 bp. No filing or news event is attached, so this is not a trade.`
      : `Stored Bitget ticker last ${payload.last}. A ticker is not an order book and is not a trade.`,
    instrumentSymbol: symbol || null,
    category: "MARKET",
    occurredAt: String(row.fetched_at_utc || row.event_time_utc),
    source: { id: "bitget-rest", name: "Bitget public REST", kind: "EXCHANGE_FEED", trust: "PRIMARY" },
    evidenceCompleteness: book ? 1 : 0,
    decisionState: "NO ACTION",
    status: "NEW",
  };
}

function asObservation(row: Record<string, unknown>): MarketObservation | null {
  if (row.event_type !== "book") return null;
  const payload = (row.payload || {}) as Record<string, unknown>;
  const mid = Number(payload.mid);
  if (!Number.isFinite(mid)) return null;
  return {
    symbol: String(row.instrument_id),
    priceUsd: mid,
    changePct24h: null,
    observedAt: String(row.fetched_at_utc),
    freshness: freshness(String(row.fetched_at_utc)),
    sessionNote: `Bitget book mid. Spread ${payload.spread_bp} bp. Depth ${payload.depth_usdt} USDT. 24h change is not in this snapshot.`,
  };
}

function instrument(symbol: string): InstrumentIdentity {
  const reference = symbol.endsWith("USDT") ? symbol.slice(0, -4) : symbol;
  return {
    symbol,
    name: NAMES[symbol] || symbol,
    kind: "EQUITY_TOKEN",
    company: NAMES[symbol] || null,
    referenceSymbol: reference,
    venue: "Bitget USDT perpetual",
  };
}

export const liveDataProvider = {
  async listInstruments(): Promise<InstrumentIdentity[]> {
    const events = await this.listEvents();
    const symbols = [...new Set(events.map((event) => event.instrumentSymbol).filter(Boolean))] as string[];
    return symbols.map(instrument);
  },

  async getMarketOverview(): Promise<MarketObservation[]> {
    const body = (await readJson("/v1/events?limit=50")) as { items?: Record<string, unknown>[] };
    const seen = new Set<string>();
    const rows: MarketObservation[] = [];
    for (const item of body.items || []) {
      const observation = asObservation(item);
      if (!observation || seen.has(observation.symbol)) continue;
      seen.add(observation.symbol);
      rows.push(observation);
    }
    return rows;
  },

  async getPriceSeries(symbol: string): Promise<PriceSeries | null> {
    const overview = await this.getMarketOverview();
    const current = overview.find((row) => row.symbol === symbol);
    if (!current) return null;
    return { symbol, points: [{ t: current.observedAt, p: current.priceUsd, event: true }], markers: [] };
  },

  async listEvents(): Promise<MarketEvent[]> {
    const body = (await readJson("/v1/events?limit=50")) as { items?: Record<string, unknown>[] };
    return (body.items || []).map(asEvent);
  },

  async getEventBundle(eventId: string): Promise<EventBundle | null> {
    if (eventId.startsWith("dec_")) {
      const cycle = await this.getCycle();
      const reason = cycle.reason || "no reason recorded";
      const event: MarketEvent = {
        id: eventId,
        headline: `Paper cycle ${reason}`,
        summary: "One scheduled paper cycle. It is not a separate decision for each symbol.",
        instrumentSymbol: null,
        category: "MARKET",
        occurredAt: cycle.occurredAt || new Date().toISOString(),
        source: { id: "bitget-rest", name: "Bitget public REST", kind: "EXCHANGE_FEED", trust: "PRIMARY" },
        evidenceCompleteness: 0,
        decisionState: "NO ACTION",
        status: "RESOLVED",
      };
      const decision: AIDecision = {
        eventId,
        state: "NO ACTION",
        confidence: 0,
        plainLanguage: `${reason}. The model was not asked to authorize a trade.`,
        reasoning: [reason],
        invalidationConditions: ["A verified event and a usable order book are required before a proposal."],
        proposedAction: null,
      };
      const risk: RiskEngineResult = {
        eventId,
        outcome: cycle.status === "approved" ? "APPROVED" : "REFUSED",
        plainLanguage: reason,
        checks: [{ id: "cycle", label: "Paper cycle", status: cycle.status === "approved" ? "PASS" : "FAIL", detail: reason, limit: "qualifying event and book", observed: reason }],
        sizeMultiplier: null,
      };
      const execution: PaperExecution = {
        eventId,
        kind: "NONE",
        symbol: "",
        side: null,
        filledTokens: 0,
        avgPriceUsd: null,
        feeUsd: 0,
        slippageUsd: 0,
        totalCostUsd: 0,
        executedAt: event.occurredAt,
        note: "No paper order was sent. This is not an exchange fill.",
        costBreakdown: [],
      };
      let receipt: SignedReceipt = {
        eventId,
        digestPreview: "none",
        algorithm: "ed25519",
        timestampAuthority: "not attached",
        createdAt: event.occurredAt,
        verification: "UNAVAILABLE",
        fieldsIncluded: [],
      };
      if (cycle.receiptId) {
        const stored = (await readJson(`/v1/receipts/${cycle.receiptId}`)) as { ots_status?: string; line?: { line_hash?: string } };
        const verified = (await readJson(`/v1/receipts/${cycle.receiptId}/verify`, { method: "POST" })) as { verified?: boolean };
        receipt = {
          eventId,
          digestPreview: String(stored.line?.line_hash || "").slice(0, 16),
          algorithm: "ed25519",
          timestampAuthority: stored.ots_status === "pending" ? "OpenTimestamps pending" : String(stored.ots_status || "unavailable"),
          createdAt: event.occurredAt,
          verification: verified.verified ? (stored.ots_status === "pending" ? "UNCONFIRMED" : "SIGNATURE_VERIFIED") : "UNAVAILABLE",
          fieldsIncluded: ["decision_id", "status", "reason", "evidence_ids", "input_snapshot_hash"],
        };
      }
      return { event, instrument: null, observation: null, evidence: [], decision, risk, execution, receipt, priceSeries: null };
    }
    const row = (await readJson(`/v1/events/${eventId}`)) as Record<string, unknown>;
    if (!row?.id) return null;
    const event = asEvent(row);
    const observation = asObservation(row);
    const ops = (await readJson("/v1/ops/status")) as { latest_run?: { reason?: string; decision_id?: string; receipt_id?: string } };
    const reason = ops.latest_run?.reason || "no decision recorded for this event";
    const evidence: EvidenceRecord[] = [{
      id: String(row.id),
      eventId,
      label: row.event_type === "book" ? "Bitget order book" : "Bitget ticker",
      source: event.source,
      capturedAt: event.occurredAt,
      value: observation ? `${observation.priceUsd} mid` : `last ${String((row.payload as Record<string, unknown> | undefined)?.last ?? "unavailable")}`,
      numericValue: observation?.priceUsd ?? null,
      unit: "USDT",
      freshness: observation?.freshness || "STALE",
      whyItMatters: "The paper cycle refuses a trade when the book is missing, wide, thin, or no qualifying event is attached.",
      verification: row.event_type === "book" ? "SOURCE_CONFIRMED" : "UNVERIFIED",
    }];
    const decision: AIDecision = {
      eventId,
      state: "NO ACTION",
      confidence: 0,
      plainLanguage: `Latest paper cycle: ${reason}. This symbol row is a stored observation, not its own decision. The model was not asked to authorize a trade.`,
      reasoning: [reason],
      invalidationConditions: ["A verified event tied to this instrument would be required before a proposal."],
      proposedAction: null,
    };
    const risk: RiskEngineResult = {
      eventId,
      outcome: "REFUSED",
      plainLanguage: reason,
      checks: [{ id: "event", label: "Qualifying event", status: "FAIL", detail: reason, limit: "event required", observed: "none" }],
      sizeMultiplier: null,
    };
    const execution: PaperExecution = {
      eventId,
      kind: "NONE",
      symbol: event.instrumentSymbol || "",
      side: null,
      filledTokens: 0,
      avgPriceUsd: null,
      feeUsd: 0,
      slippageUsd: 0,
      totalCostUsd: 0,
      executedAt: event.occurredAt,
      note: "No paper order was sent. This is not an exchange fill.",
      costBreakdown: [],
    };
    let receipt: SignedReceipt = {
      eventId,
      digestPreview: "none",
      algorithm: "ed25519",
      timestampAuthority: "not requested for this event row",
      createdAt: event.occurredAt,
      verification: "UNAVAILABLE",
      fieldsIncluded: [],
    };
    const receiptId = ops.latest_run?.receipt_id;
    if (receiptId) {
      const stored = (await readJson(`/v1/receipts/${receiptId}`)) as { id?: string; ots_status?: string; line?: { line_hash?: string } };
      const verified = (await readJson(`/v1/receipts/${receiptId}/verify`, { method: "POST" })) as { verified?: boolean; ots_status?: string };
      receipt = {
        eventId,
        digestPreview: String(stored.line?.line_hash || "").slice(0, 16),
        algorithm: "ed25519",
        timestampAuthority: stored.ots_status === "pending" ? "OpenTimestamps pending" : String(stored.ots_status || "unavailable"),
        createdAt: event.occurredAt,
        verification: verified.verified ? (stored.ots_status === "pending" ? "UNCONFIRMED" : "SIGNATURE_VERIFIED") : "UNAVAILABLE",
        fieldsIncluded: ["decision_id", "status", "reason", "evidence_ids", "input_snapshot_hash"],
      };
    }
    return {
      event,
      instrument: event.instrumentSymbol ? instrument(event.instrumentSymbol) : null,
      observation,
      evidence,
      decision,
      risk,
      execution,
      receipt,
      priceSeries: observation ? { symbol: observation.symbol, points: [{ t: observation.observedAt, p: observation.priceUsd, event: true }], markers: [] } : null,
    };
  },

  async getCycle(): Promise<CycleSnapshot> {
    const ops = (await readJson("/v1/ops/status")) as {
      latest_run?: { status?: string; reason?: string; decision_id?: string; receipt_id?: string; finished_at_utc?: string; started_at_utc?: string };
    };
    const fills = (await readJson("/v1/paper/fills")) as { items?: unknown[] };
    const latest = ops.latest_run;
    return {
      decisionCount: latest?.decision_id ? 1 : 0,
      refusalCount: latest?.status === "refused" ? 1 : 0,
      fillCount: (fills.items || []).length,
      reason: latest?.reason || null,
      decisionId: latest?.decision_id || null,
      receiptId: latest?.receipt_id || null,
      occurredAt: latest?.finished_at_utc || latest?.started_at_utc || null,
      status: latest?.status || null,
    };
  },

  async listActivity(): Promise<ActivityRecord[]> {
    const cycle = await this.getCycle();
    if (!cycle.decisionId || !cycle.occurredAt) return [];
    return [{
      eventId: cycle.decisionId,
      instrumentSymbol: "",
      headline: `Paper cycle ${cycle.status || "recorded"}: ${cycle.reason || "no reason"}`,
      decisionState: "NO ACTION",
      riskOutcome: cycle.status === "approved" ? "APPROVED" : "REFUSED",
      execution: "NONE",
      occurredAt: cycle.occurredAt,
      sourceKind: "EXCHANGE_FEED",
      receiptDigest: cycle.receiptId,
    }];
  },

  async getReceipt(eventId: string): Promise<SignedReceipt | null> {
    const bundle = await this.getEventBundle(eventId);
    return bundle?.receipt ?? null;
  },

  async explainVerification(receipt: SignedReceipt): Promise<string> {
    if (receipt.verification === "UNCONFIRMED") {
      return "The production public key verified the signature. The OpenTimestamps anchor is still pending, so this is not a confirmed external timestamp.";
    }
    if (receipt.verification === "SIGNATURE_VERIFIED") {
      return "The production public key verified the signature.";
    }
    if (receipt.verification === "UNAVAILABLE") {
      return "No signed production receipt is attached to this row.";
    }
    return "This row does not have a verified production receipt.";
  },
};
