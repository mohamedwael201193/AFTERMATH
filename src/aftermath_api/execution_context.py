"""Server-derived paper execution inputs. The caller does not supply the book."""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone

CALLER_FIELDS = ("risk_context", "book", "ref_price", "side", "fee_rate", "notional")
PAPER_EQUITY = 10_000.0
DEFAULT_TAKER_FEE = 0.0006


def caller_controlled(body: dict) -> list[str]:
    return [name for name in CALLER_FIELDS if name in body]


def derive_execution(
    proposal: dict,
    events: list[dict],
    decision_source: str,
    now: datetime | None = None,
    market: dict | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    action = proposal.get("action")
    symbol = proposal.get("symbol")
    if action not in ("LONG", "SHORT"):
        return {"error": "side_not_in_proposal"}
    if not isinstance(symbol, str) or not symbol:
        return {"error": "symbol_missing"}
    books = [event for event in events if _valid_book(event.get("payload") or {})]
    matched = [event for event in books if event.get("instrument_id") == symbol]
    if not matched:
        return {"error": "symbol_mismatch" if books else "missing_order_book"}
    event = matched[0]
    payload = event["payload"]
    bid = float(payload["bid"])
    ask = float(payload["ask"])
    mid = (bid + ask) / 2
    if not math.isfinite(mid) or mid <= 0:
        return {"error": "invalid_book"}
    stored_mid = payload.get("mid")
    if stored_mid is not None and abs(float(stored_mid) - mid) / mid * 1e4 > 1:
        return {"error": "book_mid_mismatch"}
    profile = {"bids": _profile(payload.get("bids") or [], mid), "asks": _profile(payload.get("asks") or [], mid)}
    if not profile["bids"] or not profile["asks"]:
        return {"error": "invalid_book"}
    fee_rate = _fee(payload)
    if fee_rate is None:
        return {"error": "invalid_fee"}
    fetched = _parse(event.get("fetched_at_utc"))
    occurred = _filing_time(events, symbol) or _parse(event.get("event_time_utc")) or fetched
    if fetched is None:
        return {"error": "missing_provenance"}
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {"status": "unknown", "is_rwa": "NO"}
    context = {
        "symbol": symbol,
        "source": "llm" if decision_source == "model" else "rule",
        "emergency_stop": os.environ.get("AFTERMATH_KILL") == "1",
        "contract": {"status": contract.get("status"), "is_rwa": contract.get("is_rwa")},
        "spread_bp": (ask - bid) / mid * 1e4,
        "depth_band_usdt": float(payload.get("depth_usdt") or 0),
        "data_age_min": max(0.0, (now - fetched).total_seconds() / 60),
        "event_age_min": max(0.0, (now - (occurred or fetched)).total_seconds() / 60),
        "equity": PAPER_EQUITY,
        "gross_open_usdt": 0.0,
        "n_open": 0,
        "open_symbols": [],
        "symbol_pnl_today": 0.0,
        "day_pnl": 0.0,
        "drawdown": 0.0,
        "n_precedents": 0,
        "hedge_beta": 0.0,
        "hedge_r2": None,
    }
    applied = _apply_market(context, market)
    if applied.get("error"):
        return {"error": applied["error"]}
    return {
        "error": None,
        "side": 1 if action == "LONG" else -1,
        "ref_price": mid,
        "fee_rate": fee_rate if applied.get("fee_rate") is None else applied["fee_rate"],
        "profile": profile,
        "book_hash": payload.get("raw_sha256"),
        "proposal_fetched_at": fetched.isoformat(),
        "context": applied["context"],
    }


def _filing_time(events: list[dict], symbol: str) -> datetime | None:
    times = []
    for event in events:
        if event.get("event_type") != "filing" or event.get("instrument_id") != symbol:
            continue
        if (event.get("payload") or {}).get("qualifies") is not True:
            continue
        parsed = _parse(event.get("event_time_utc"))
        if parsed is not None:
            times.append(parsed)
    return min(times) if times else None


def _apply_market(context: dict, market: dict | None) -> dict:
    if market is None:
        return {"context": context}
    missing = []
    contract = market.get("contract")
    if not isinstance(contract, dict) or contract.get("status") != "normal" or contract.get("is_rwa") not in ("YES", "NO"):
        missing.append("contract")
    precedents = market.get("n_precedents")
    if not isinstance(precedents, int) or isinstance(precedents, bool) or precedents < 0:
        missing.append("n_precedents")
    hedge_r2 = market.get("hedge_r2")
    if not isinstance(hedge_r2, (int, float)) or isinstance(hedge_r2, bool) or not math.isfinite(float(hedge_r2)):
        missing.append("hedge_r2")
    hedge_beta = market.get("hedge_beta")
    if not isinstance(hedge_beta, (int, float)) or isinstance(hedge_beta, bool) or not math.isfinite(float(hedge_beta)):
        missing.append("hedge_beta")
    if missing:
        return {"error": "incomplete_market:" + ",".join(missing)}
    fee_rate = None
    raw_fee = contract.get("taker_fee_rate")
    if raw_fee is not None:
        try:
            fee_rate = float(raw_fee)
        except (TypeError, ValueError):
            return {"error": "incomplete_market:fee"}
        if not math.isfinite(fee_rate) or fee_rate < 0 or fee_rate > 0.01:
            return {"error": "incomplete_market:fee"}
    context["contract"] = {"status": contract["status"], "is_rwa": contract["is_rwa"]}
    context["n_precedents"] = precedents
    context["hedge_r2"] = float(hedge_r2)
    context["hedge_beta"] = float(hedge_beta)
    context["emergency_stop"] = context["emergency_stop"] or bool(market.get("emergency_stop"))
    for key in ("gross_open_usdt", "symbol_pnl_today", "day_pnl", "drawdown"):
        if key in market:
            try:
                value = float(market[key])
            except (TypeError, ValueError):
                return {"error": "incomplete_market:" + key}
            if not math.isfinite(value):
                return {"error": "incomplete_market:" + key}
            context[key] = value
    if "n_open" in market:
        if not isinstance(market["n_open"], int) or isinstance(market["n_open"], bool):
            return {"error": "incomplete_market:n_open"}
        context["n_open"] = market["n_open"]
    if isinstance(market.get("open_symbols"), list):
        context["open_symbols"] = [str(item) for item in market["open_symbols"]]
    return {"context": context, "fee_rate": fee_rate}


def _fee(payload: dict) -> float | None:
    raw = payload.get("taker_fee_rate", DEFAULT_TAKER_FEE)
    try:
        fee = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(fee) or fee < 0 or fee > 0.01:
        return None
    return fee


def _valid_book(payload: dict) -> bool:
    try:
        bid = float(payload["bid"])
        ask = float(payload["ask"])
    except (KeyError, TypeError, ValueError):
        return False
    return math.isfinite(bid) and math.isfinite(ask) and bid > 0 and ask > bid


def _profile(levels: list, mid: float) -> list[tuple[float, float]]:
    rows = []
    for level in levels:
        try:
            price, qty = float(level[0]), float(level[1])
        except (TypeError, ValueError, IndexError):
            continue
        if not math.isfinite(price) or not math.isfinite(qty) or price <= 0 or qty <= 0:
            continue
        rows.append((abs(price - mid) / mid * 1e4, price * qty))
    return rows


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
