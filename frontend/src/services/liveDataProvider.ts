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
  stale: boolean;
  evaluationStatus: string | null;
  eventCount: number | null;
  bookCount: number | null;
  precedentCount: number | null;
  scheduler: string | null;
  schedule: string | null;
  continuousOperation: boolean;
  killSwitch: boolean;
  secEdgarStatus: string | null;
  modelCallsLatest: number | null;
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
  const filing = row.event_type === "filing";
  const symbol = String(row.instrument_id || "");
  if (filing) {
    const reaction = typeof payload.reaction_bp === "number" ? `${payload.reaction_bp} bp` : "missing";
    const accession = typeof payload.accession === "string" ? payload.accession : "missing";
    return {
      id: String(row.id),
      headline: `Historical warm-up reaction ${symbol}`,
      summary: `Item 2.02 accession ${accession}, accepted ${String(row.event_time_utc)}. Residual ${reaction} versus QQQUSDT. This row can raise the precedent count. It is not a model decision, not a paper fill, and not a scored outcome.`,
      instrumentSymbol: symbol || null,
      category: "FILING",
      occurredAt: String(row.event_time_utc || row.fetched_at_utc),
      source: { id: "sec-edgar", name: "SEC EDGAR", kind: "SEC_EDGAR", trust: "PRIMARY" },
      evidenceCompleteness: null,
      decisionState: "NO ACTION",
      status: "RESOLVED",
    };
  }
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
    evidenceCompleteness: null,
    decisionState: "NO ACTION",
    status: "NEW",
  };
}

function isPreModelDecision(row: Record<string, unknown>): boolean {
  return row.model_called !== true && row.decision_source !== "model";
}

function mapActivityExecution(row: Record<string, unknown>, preModel: boolean): ActivityRecord["execution"] {
  const status = String(row.status || "").toUpperCase();
  if (status.includes("FILL") || status === "PAPER_FILLED" || status === "CLOSED") return "FILLED";
  if (preModel) return "NONE";
  if (status === "ABSTAIN" || status === "REFUSED" || status === "REJECT") return "REFUSED";
  return "NONE";
}

function mapActivityRisk(row: Record<string, unknown>, preModel: boolean): ActivityRecord["riskOutcome"] {
  if (preModel) return "APPROVED";
  const status = String(row.status || "").toUpperCase();
  if (status === "APPROVED" || status === "PAPER_PROPOSED" || status === "NO_ACTION") return "APPROVED";
  if (status.includes("REDUC")) return "REDUCED";
  return "REFUSED";
}

function receiptDigestPreview(receiptId: unknown): string | null {
  if (!receiptId) return null;
  const id = String(receiptId);
  return id.length > 16 ? id.slice(0, 16) : id;
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

function anchorLabel(status?: string): string {
  if (status === "not_anchored") return "Not anchored";
  if (status === "pending") return "OpenTimestamps pending";
  if (status === "confirmed") return "OpenTimestamps confirmed";
  return status || "unavailable";
}

function anchorUnconfirmed(status?: string): boolean {
  return status === "pending" || status === "not_anchored" || !status;
}

function cycleFromOps(ops: {
  latest_run?: {
    status?: string;
    reason?: string;
    decision_id?: string;
    receipt_id?: string;
    finished_at_utc?: string;
    started_at_utc?: string;
    detail?: { model_calls?: number };
  };
  fill_count?: number;
  decision_count?: number;
  event_count?: number;
  book_count?: number;
  precedent_count?: number;
  stale?: boolean;
  scheduler?: string;
  schedule?: string;
  continuous_operation?: boolean;
  kill_switch?: boolean;
  sources?: { sec_edgar?: { status?: string } };
}): CycleSnapshot {
  const latest = ops.latest_run;
  const detail = latest?.detail;
  return {
    decisionCount: typeof ops.decision_count === "number" ? ops.decision_count : latest?.decision_id ? 1 : 0,
    refusalCount: latest?.status === "refused" ? 1 : 0,
    fillCount: typeof ops.fill_count === "number" ? ops.fill_count : 0,
    reason: latest?.reason || null,
    decisionId: latest?.decision_id || null,
    receiptId: latest?.receipt_id || null,
    occurredAt: latest?.finished_at_utc || latest?.started_at_utc || null,
    status: latest?.status || null,
    stale: ops.stale === true,
    evaluationStatus: null,
    eventCount: typeof ops.event_count === "number" ? ops.event_count : null,
    bookCount: typeof ops.book_count === "number" ? ops.book_count : null,
    precedentCount: typeof ops.precedent_count === "number" ? ops.precedent_count : null,
    scheduler: ops.scheduler ?? null,
    schedule: ops.schedule ?? null,
    continuousOperation: ops.continuous_operation === true,
    killSwitch: ops.kill_switch === true,
    secEdgarStatus: ops.sources?.sec_edgar?.status ?? null,
    modelCallsLatest: typeof detail?.model_calls === "number" ? detail.model_calls : null,
  };
}

function activityFromCycle(cycle: CycleSnapshot): ActivityRecord[] {
  if (!cycle.decisionId || !cycle.occurredAt) return [];
  const preModel =
    cycle.reason === "no_qualifying_event" ||
    cycle.reason === "scheduled_no_new_evidence" ||
    cycle.reason === "source_unavailable" ||
    cycle.reason === "filing_document_missing";
  return [{
    eventId: cycle.decisionId,
    instrumentSymbol: "",
    headline: preModel ? `Pre-model cycle: ${cycle.reason}` : `Paper cycle: ${cycle.reason || "no reason"}`,
    decisionState: "NO ACTION",
    riskOutcome: preModel ? "APPROVED" : cycle.status === "approved" ? "APPROVED" : "REFUSED",
    execution: "NONE",
    occurredAt: cycle.occurredAt,
    sourceKind: "EXCHANGE_FEED",
    receiptDigest: receiptDigestPreview(cycle.receiptId),
    governorCalled: !preModel,
  }];
}

function activityFromDecisions(items: Record<string, unknown>[]): ActivityRecord[] {
  return items.map((row) => {
    const reason = String(row.reason || "no reason");
    const modelCalled = row.model_called === true || row.decision_source === "model";
    const preModel = isPreModelDecision(row);
    return {
      eventId: String(row.id),
      instrumentSymbol: "",
      headline: modelCalled ? `Model decision: ${reason}` : `Pre-model cycle: ${reason}`,
      decisionState: "NO ACTION" as const,
      riskOutcome: mapActivityRisk(row, preModel),
      execution: mapActivityExecution(row, preModel),
      occurredAt: String(row.created_at_utc || ""),
      sourceKind: "EXCHANGE_FEED" as const,
      receiptDigest: receiptDigestPreview(row.receipt_id),
      governorCalled: modelCalled,
    };
  });
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
      const row = (await readJson(`/v1/decisions/${eventId}`)) as {
        id?: string;
        reason?: string;
        created_at_utc?: string;
        model_called?: boolean;
        decision_source?: string;
        receipt_id?: string | null;
      };
      const reason = row.reason || "no reason recorded";
      const modelCalled = row.model_called === true || row.decision_source === "model";
      const event: MarketEvent = {
        id: eventId,
        headline: modelCalled ? `Model decision ${reason}` : `Pre-model cycle ${reason}`,
        summary: "One scheduled paper cycle. It is not a separate decision for each symbol.",
        instrumentSymbol: null,
        category: "MARKET",
        occurredAt: row.created_at_utc || new Date().toISOString(),
        source: { id: "bitget-rest", name: "Bitget public REST", kind: "EXCHANGE_FEED", trust: "PRIMARY" },
        evidenceCompleteness: null,
        decisionState: "NO ACTION",
        status: "RESOLVED",
      };
      const decision: AIDecision = {
        eventId,
        state: "NO ACTION",
        confidence: 0,
        plainLanguage: modelCalled
          ? `${reason}. A model proposal was recorded and did not become a fill.`
          : `${reason}. The model was not asked to authorize a trade.`,
        modelCalled,
        reasoning: modelCalled ? [reason] : ["MODEL NOT CALLED — PRE-MODEL REFUSAL", reason],
        invalidationConditions: ["A verified event and a usable order book are required before a proposal."],
        proposedAction: null,
      };
      const risk: RiskEngineResult = {
        eventId,
        outcome: modelCalled ? "REFUSED" : "APPROVED",
        plainLanguage: modelCalled ? reason : "The governor was not called. This cycle has no risk verdict.",
        checks: [],
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
      if (row.receipt_id) {
        const stored = (await readJson(`/v1/receipts/${row.receipt_id}`)) as { ots_status?: string; line?: { line_hash?: string } };
        const verified = (await readJson(`/v1/receipts/${row.receipt_id}/verify`, { method: "POST" })) as { verified?: boolean };
        receipt = {
          eventId,
          digestPreview: String(stored.line?.line_hash || "").slice(0, 16),
          algorithm: "ed25519",
          timestampAuthority: anchorLabel(stored.ots_status),
          createdAt: event.occurredAt,
          verification: verified.verified ? (anchorUnconfirmed(stored.ots_status) ? "UNCONFIRMED" : "SIGNATURE_VERIFIED") : "UNAVAILABLE",
          fieldsIncluded: ["decision_id", "status", "reason", "evidence_ids", "input_snapshot_hash"],
        };
      }
      return { event, instrument: null, observation: null, evidence: [], decision, risk, execution, receipt, priceSeries: null };
    }
    const row = (await readJson(`/v1/events/${eventId}`)) as Record<string, unknown>;
    if (!row?.id) return null;
    const event = asEvent(row);
    const observation = asObservation(row);
    const payload = (row.payload || {}) as Record<string, unknown>;
    const filing = row.event_type === "filing";
    const ops = (await readJson("/v1/ops/status")) as { latest_run?: { reason?: string; decision_id?: string; receipt_id?: string } };
    const reason = ops.latest_run?.reason || "no decision recorded for this event";
    const accession = typeof payload.accession === "string" ? payload.accession : "missing";
    const reaction = typeof payload.reaction_bp === "number" ? payload.reaction_bp : null;
    const evidence: EvidenceRecord[] = [{
      id: String(row.id),
      eventId,
      label: filing ? "SEC 8-K Item 2.02 warm-up" : row.event_type === "book" ? "Bitget order book" : "Bitget ticker",
      source: event.source,
      capturedAt: event.occurredAt,
      value: filing
        ? `accession ${accession}; residual ${reaction == null ? "missing" : reaction + " bp"}`
        : observation
          ? `${observation.priceUsd} mid`
          : `last ${String(payload.last ?? "unavailable")}`,
      numericValue: filing ? reaction : observation?.priceUsd ?? null,
      unit: filing ? "bp" : "USDT",
      freshness: observation?.freshness || "STALE",
      whyItMatters: filing
        ? "A warm-up residual can satisfy the precedent count. It is not a scored outcome and it does not authorize a trade."
        : "The paper cycle refuses a trade when the book is missing, wide, thin, or no qualifying event is attached.",
      verification: filing || row.event_type === "book" ? "SOURCE_CONFIRMED" : "UNVERIFIED",
    }];
    const decision: AIDecision = {
      eventId,
      state: "NO ACTION",
      confidence: 0,
      plainLanguage: filing
        ? "Historical warm-up reaction. The model and the governor were not called for this accession."
        : `Latest paper cycle: ${reason}. This symbol row is a stored observation, not its own decision. The model and the governor were not called.`,
      modelCalled: false,
      reasoning: filing
        ? ["WARM-UP REACTION — NOT A CYCLE DECISION", `accession ${accession}`]
        : ["MODEL NOT CALLED — PRE-MODEL REFUSAL", reason],
      invalidationConditions: filing
        ? ["This row stays out of the paired metric sample."]
        : ["A verified event tied to this instrument would be required before a proposal."],
      proposedAction: null,
    };
    const risk: RiskEngineResult = {
      eventId,
      outcome: "APPROVED",
      plainLanguage: "The governor was not called for this observation.",
      checks: [],
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
    const receipt: SignedReceipt = {
      eventId,
      digestPreview: "none",
      algorithm: "none",
      timestampAuthority: "not attached",
      createdAt: event.occurredAt,
      verification: "UNAVAILABLE",
      fieldsIncluded: [],
    };
    return {
      event,
      instrument: event.instrumentSymbol ? instrument(event.instrumentSymbol) : null,
      observation,
      evidence,
      decision,
      risk,
      execution,
      receipt,
      priceSeries: null,
    };
  },

  async getCycle(): Promise<CycleSnapshot> {
    const ops = (await readJson("/v1/ops/status")) as Parameters<typeof cycleFromOps>[0];
    return cycleFromOps(ops);
  },

  async loadDashboard(): Promise<{
    events: MarketEvent[];
    observations: MarketObservation[];
    instruments: InstrumentIdentity[];
    activity: ActivityRecord[];
    cycle: CycleSnapshot;
  }> {
    const [eventBody, ops, metrics, decisionBody] = await Promise.all([
      readJson("/v1/events?limit=50") as Promise<{ items?: Record<string, unknown>[] }>,
      readJson("/v1/ops/status") as Promise<Parameters<typeof cycleFromOps>[0]>,
      readJson("/v1/metrics").catch(() => null) as Promise<{ status?: string; evaluation?: { status?: string } } | null>,
      readJson("/v1/decisions?limit=50").catch(() => null) as Promise<{ items?: Record<string, unknown>[] } | null>,
    ]);
    const items = eventBody.items || [];
    const events = items.map(asEvent);
    const seen = new Set<string>();
    const observations: MarketObservation[] = [];
    for (const item of items) {
      const observation = asObservation(item);
      if (!observation || seen.has(observation.symbol)) continue;
      seen.add(observation.symbol);
      observations.push(observation);
    }
    const symbols = [...new Set(events.map((event) => event.instrumentSymbol).filter(Boolean))] as string[];
    const cycle = cycleFromOps(ops);
    cycle.evaluationStatus = metrics?.evaluation?.status || metrics?.status || null;
    const activity = decisionBody?.items?.length ? activityFromDecisions(decisionBody.items) : activityFromCycle(cycle);
    const riskRefusals = activity.filter((a) => a.governorCalled !== false && a.riskOutcome === "REFUSED").length;
    cycle.refusalCount = riskRefusals;
    return {
      events,
      observations,
      instruments: symbols.map(instrument),
      activity,
      cycle,
    };
  },

  async listActivity(): Promise<ActivityRecord[]> {
    const body = (await readJson("/v1/decisions?limit=50").catch(() => null)) as { items?: Record<string, unknown>[] } | null;
    if (body?.items?.length) return activityFromDecisions(body.items);
    return activityFromCycle(await this.getCycle());
  },

  async getReceipt(eventId: string): Promise<SignedReceipt | null> {
    const bundle = await this.getEventBundle(eventId);
    return bundle?.receipt ?? null;
  },

  async explainVerification(receipt: SignedReceipt): Promise<string> {
    if (receipt.verification === "UNCONFIRMED") {
      if (receipt.timestampAuthority === "Not anchored") {
        return "The production public key verified the signature. No OpenTimestamps anchor was submitted.";
      }
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
