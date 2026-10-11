"""One paper cycle. It records a refusal when core evidence is incomplete. It does not invent fills."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from .decide import abstain, decide_bounded
from .execution_context import PAPER_EQUITY, derive_execution
from .paper import govern
from .positions import advance_positions
from .errors import ApiError
from .ids import SCHEMA_VERSION, event_id, evidence_id, payload_hash, utc_now
from .receipts import issue_receipt

WHITELIST = (
    "AAPLUSDT",
    "AMZNUSDT",
    "COINUSDT",
    "GOOGLUSDT",
    "METAUSDT",
    "MSFTUSDT",
    "MSTRUSDT",
    "NVDAUSDT",
    "TSLAUSDT",
)


def fetch_live(cache_dir: Path) -> tuple[list[dict], list[str]]:
    from .connectors import BitgetConnector

    connector = BitgetConnector(cache_dir, mode="live")
    observations: list[dict] = []
    errors: list[str] = []
    for symbol in WHITELIST:
        try:
            observations.append(connector.depth(symbol))
        except ApiError as exc:
            errors.append(exc.code)
    return observations, errors


def cycle_reason(observations: list[dict]) -> str:
    """Refuse from the books actually fetched. A usable book is not a trade."""
    books = [row for row in observations if row.get("event_type") == "book"]
    if not books:
        return "missing_order_book"
    reasons = [_book_reason(row.get("payload") or {}) for row in books]
    if "no_qualifying_event" in reasons:
        return "no_qualifying_event"
    if "spread_too_wide" in reasons:
        return "spread_too_wide"
    if "insufficient_depth" in reasons:
        return "insufficient_depth"
    return "missing_order_book"


def _book_reason(payload: dict) -> str:
    try:
        spread = float(payload["spread_bp"])
        depth = float(payload["depth_usdt"])
    except (KeyError, TypeError, ValueError):
        return "missing_order_book"
    if spread != spread or depth != depth:
        return "missing_order_book"
    if spread > 12:
        return "spread_too_wide"
    if depth < 1000:
        return "insufficient_depth"
    return "no_qualifying_event"


def persist_observation(store, body: dict) -> dict:
    phash = payload_hash(body["payload"])
    eid = event_id(body["source"], body["instrument_id"], body["event_type"], body["event_time_utc"], phash)
    event = store.insert_event({
        "id": eid,
        "instrument_id": body["instrument_id"],
        "event_type": body["event_type"],
        "event_time_utc": body["event_time_utc"],
        "fetched_at_utc": body["fetched_at_utc"],
        "source": body["source"],
        "schema_version": SCHEMA_VERSION,
        "payload": body["payload"],
        "payload_hash": phash,
        "mapping_confidence": body.get("mapping_confidence", 1.0),
        "conflict": False,
        "created_at_utc": utc_now(),
    })
    evid = evidence_id(event["id"], phash)
    evidence = store.insert_evidence({
        "id": evid,
        "event_id": event["id"],
        "schema_version": SCHEMA_VERSION,
        "payload_hash": phash,
        "included_at_utc": utc_now(),
    })
    return {"event": event, "evidence": evidence}


def run_paper_cycle(settings, store, *, fetch=None, signing_path: str = "", event_fetch=None, model_transport=None, market_fetch=None) -> dict:
    now = datetime.now(timezone.utc)
    key = "paper-cycle:v2:" + now.strftime("%Y-%m-%dT%H")
    existing = store.decision_for_key(key)
    if existing:
        decision = store.get_decision(existing)
        receipt = store.receipt_for_decision(existing)
        if store.run_for_key(key) is None:
            store.insert_run({
                "id": "run_" + uuid.uuid4().hex[:16],
                "idempotency_key": key,
                "status": "refused" if decision["status"] == "ABSTAIN" else decision["status"],
                "reason": decision["reason"],
                "decision_id": existing,
                "started_at_utc": decision["created_at_utc"],
                "finished_at_utc": utc_now(),
                "detail": {"observations": len(decision.get("evidence_ids") or []), "model_calls": 0, "recovered": True},
            })
        return {
            "idempotency_key": key,
            "decision_id": existing,
            "repeated": True,
            "reason": decision.get("reason"),
            "receipt_id": None if receipt is None else receipt["id"],
        }
    observations: list[dict] = []
    errors: list[str] = []
    if fetch is not None:
        observations, errors = fetch()
    elif settings.env != "test":
        cache = Path("/tmp/aftermath-cache") if Path("/tmp").is_dir() else Path(".") / "cache"
        cache.mkdir(parents=True, exist_ok=True)
        observations, errors = fetch_live(cache)
    filings: list[dict] = []
    if event_fetch is not None:
        filings = [row for row in event_fetch() if not _already_seen(store, row)]
    elif settings.sec_user_agent.strip() and settings.env != "test":
        from .sources.edgar import fetch_filings
        import requests

        def transport(url, headers):
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            if str(url).split("?", 1)[0].endswith(".json"):
                return response.json()
            return response.text

        try:
            filings = [row for row in fetch_filings(settings.sec_user_agent, transport, utc_now()) if not _already_seen(store, row)]
        except Exception as exc:
            errors.append(getattr(exc, "message", None) or "sec_fetch_failed")
    observations = list(observations) + list(filings)
    advance_positions(store, observations, now)
    links = []
    loaded = []
    if not observations:
        result = abstain("source_unavailable" if errors else "scheduled_no_new_evidence", [])
        model_calls = 0
    else:
        rows = []
        for obs in observations:
            saved = persist_observation(store, obs)
            evid = saved["evidence"]["id"]
            phash = saved["evidence"]["payload_hash"]
            rows.append((evid, phash))
            links.append(evid)
            loaded.append({"id": evid, "payload_hash": phash, "facts": obs.get("payload") or {}, "event": {**obs, "payload_hash": phash}})
        result, model_calls = _decide_or_abstain(settings, store, observations, loaded, rows, now, model_transport, market_fetch)
    did = "dec_" + uuid.uuid4().hex[:24]
    store.insert_decision({
        "id": did,
        "status": result["status"],
        "decision_source": result["decision_source"],
        "prompt_hash": result["prompt_hash"],
        "input_snapshot_hash": result["input_snapshot_hash"],
        "schema_version": SCHEMA_VERSION,
        "reason": result["reason"],
        "idempotency_key": key,
        "created_at_utc": utc_now(),
    }, [{"decision_id": did, "evidence_id": evid, "position": i} for i, evid in enumerate(links)])
    if result.get("pending_entry"):
        store.insert_fill({
            "id": "fill_" + uuid.uuid4().hex[:16],
            "decision_id": did,
            "idempotency_key": key + ":entry",
            "status": "PENDING_ENTRY",
            "cost_json": result["pending_entry"],
            "created_at_utc": utc_now(),
        })
    receipt = None
    path = Path(signing_path) if signing_path else None
    if path is not None and path.is_file():
        final = store.get_decision(did)
        receipt = issue_receipt(store, path, {
            "decision_id": final["id"],
            "status": final["status"],
            "reason": final["reason"],
            "input_snapshot_hash": final["input_snapshot_hash"],
            "evidence_ids": final["evidence_ids"],
            "prompt_hash": final["prompt_hash"],
            "model": settings.llm_model if result["decision_source"] == "model" else "absent",
        })
    store.insert_run({
        "id": "run_" + uuid.uuid4().hex[:16],
        "idempotency_key": key,
        "status": "refused" if result["status"] == "ABSTAIN" else result["status"],
        "reason": result["reason"],
        "decision_id": did,
        "started_at_utc": now.isoformat(),
        "finished_at_utc": utc_now(),
        "detail": {
            "observations": len(observations),
            "fetch_errors": len(errors),
            "model_calls": model_calls,
            "sec_edgar": "configured" if settings.sec_user_agent.strip() else "disabled",
        },
    })
    return {
        "idempotency_key": key,
        "decision_id": did,
        "repeated": False,
        "reason": result["reason"],
        "receipt_id": None if receipt is None else receipt["id"],
    }


def _already_seen(store, filing: dict) -> bool:
    accession = (filing.get("payload") or {}).get("accession")
    if not accession:
        return False
    if hasattr(store, "has_accession"):
        return bool(store.has_accession(accession))
    page = store.list_events(limit=200)
    for item in page.get("items") or []:
        if (item.get("payload") or {}).get("accession") == accession:
            return True
    return False


def _counted_filings(observations: list[dict]) -> list[dict]:
    filings = [
        row for row in observations
        if row.get("event_type") == "filing" and (row.get("payload") or {}).get("qualifies") is True
    ]
    return sorted(filings, key=lambda row: row.get("event_time_utc") or "")


def _eligible_pair(observations: list[dict]) -> tuple[dict, dict] | None:
    blocked = None
    for filing in _counted_filings(observations):
        same = [
            row for row in observations
            if row.get("event_type") == "book" and row.get("instrument_id") == filing.get("instrument_id")
        ]
        if not same:
            blocked = blocked or "missing_order_book"
            continue
        reason = _book_reason(same[0].get("payload") or {})
        if reason == "no_qualifying_event":
            return filing, same[0]
        blocked = blocked or reason
    return None


def _decide_or_abstain(settings, store, observations, loaded, rows, now, transport, market_fetch=None) -> tuple[dict, int]:
    filings = _counted_filings(observations)
    pair = _eligible_pair(observations)
    if pair is None and filings:
        reason = "missing_order_book"
        for filing in filings:
            same = [
                row for row in observations
                if row.get("event_type") == "book" and row.get("instrument_id") == filing.get("instrument_id")
            ]
            if same:
                reason = _book_reason(same[0].get("payload") or {})
                break
        return abstain(reason, rows), 0
    if pair is None:
        return abstain(cycle_reason(observations), rows), 0
    filing, _book = pair
    if not _document_ready(filing):
        return abstain("filing_document_missing", rows), 0
    cap = int(getattr(settings, "llm_daily_cap", 3))
    used = store.model_calls_on_day(now.strftime("%Y-%m-%d"))
    result = decide_bounded(
        settings,
        loaded,
        symbol=filing["instrument_id"],
        transport=transport,
        calls_today=used,
        daily_cap=cap,
    )
    if result.get("reason") == "awaiting_next_book" and result.get("proposal"):
        result = _hold_if_approved(result, loaded, rows, store, now, _market_fetch(settings, store, market_fetch))
    return result, 1 if result.get("model_called") else 0


def _document_ready(filing: dict) -> bool:
    payload = filing.get("payload") or {}
    digest = payload.get("document_sha256")
    excerpt = payload.get("excerpt")
    return (
        isinstance(digest, str)
        and len(digest) == 64
        and isinstance(excerpt, str)
        and bool(excerpt.strip())
        and payload.get("excerpt_untrusted") is True
    )


def _precedent_count(store) -> int:
    if hasattr(store, "count_reactions"):
        return int(store.count_reactions())
    count = 0
    for item in (store.list_events(limit=200).get("items") or []):
        payload = item.get("payload") or {}
        reaction = payload.get("reaction_bp")
        if payload.get("counted") is True and isinstance(reaction, (int, float)) and not isinstance(reaction, bool):
            count += 1
    return count


def _market_fetch(settings, store, injected):
    if injected is not None:
        return injected
    if getattr(settings, "env", "test") == "test":
        return None

    def fetch(symbol, now):
        from .connectors import BitgetConnector, market_from_public

        cache = Path("/tmp/aftermath-cache") if Path("/tmp").is_dir() else Path(".") / "cache"
        cache.mkdir(parents=True, exist_ok=True)
        return market_from_public(BitgetConnector(cache), symbol, int(now.timestamp() * 1000), _precedent_count(store))

    return fetch


def _hold_if_approved(result: dict, loaded: list[dict], rows, store, now, market_fetch) -> dict:
    from .positions import portfolio_state

    proposal = dict(result["proposal"])
    if proposal.get("action") in ("LONG", "SHORT"):
        proposal["size_frac"] = 0.05
        proposal["horizon_hours"] = 24.0
    result["proposal"] = proposal
    events = [row["event"] for row in loaded if isinstance(row.get("event"), dict)]
    market = None
    if market_fetch is not None:
        fetched = market_fetch(proposal.get("symbol"), now)
        if not isinstance(fetched, dict):
            refused = abstain("incomplete_market:source", rows, result["prompt_hash"])
            refused["decision_source"] = "model"
            refused["model_called"] = True
            return refused
        state = portfolio_state(store, now)
        by_symbol = state.pop("symbol_pnl_by_symbol", {})
        if state.get("day_pnl") is None or state.get("drawdown") is None:
            refused = abstain("incomplete_market:pnl", rows, result["prompt_hash"])
            refused["decision_source"] = "model"
            refused["model_called"] = True
            return refused
        symbol = proposal.get("symbol")
        state["symbol_pnl_today"] = float(by_symbol.get(symbol, 0.0))
        market = {**state, **fetched}
    derived = derive_execution(proposal, events, "model", now=now, market=market)
    if derived["error"]:
        refused = abstain(derived["error"], rows, result["prompt_hash"])
        refused["decision_source"] = "model"
        refused["model_called"] = True
        return refused
    try:
        verdict = govern(result["proposal"], derived["context"])
    except (KeyError, TypeError, ValueError):
        refused = abstain("invalid_risk_context", rows, result["prompt_hash"])
        refused["decision_source"] = "model"
        refused["model_called"] = True
        return refused
    if verdict.get("verdict") != "APPROVED":
        refused = abstain(",".join(verdict.get("reasons") or ["refused"]), rows, result["prompt_hash"])
        refused["decision_source"] = "model"
        refused["model_called"] = True
        return refused
    result["pending_entry"] = {
        "symbol": result["proposal"]["symbol"],
        "action": result["proposal"]["action"],
        "side": derived["side"],
        "notional": float(verdict["size_frac"]) * PAPER_EQUITY,
        "horizon_hours": 24.0,
        "proposal_book_hash": derived["book_hash"],
        "proposal_fetched_at": derived["proposal_fetched_at"],
        "fee_rate": derived["fee_rate"],
    }
    return result
