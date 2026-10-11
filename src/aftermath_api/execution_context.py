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
    contract = market.get("contract") if isinstance(market.get("contract"), dict) else None
    category = _category(market, contract)
    if category is not None and category != "USDT-FUTURES":
        return {"error": "incomplete_market:category"}
    if market.get("symbol") not in (None, context["symbol"]):
        return {"error": "incomplete_market:symbol"}
    missing = []
    raw_status = contract.get("status") if contract else None
    if contract is None or raw_status not in ("normal", "online") or contract.get("is_rwa") not in ("YES", "NO"):
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
    raw_fee = contract.get("taker_fee_rate")
    if isinstance(raw_fee, bool) or raw_fee is None:
        return {"error": "incomplete_market:fee"}
    try:
        fee_rate = float(raw_fee)
    except (TypeError, ValueError):
        return {"error": "incomplete_market:fee"}
    if not math.isfinite(fee_rate) or fee_rate < 0 or fee_rate > 0.01:
        return {"error": "incomplete_market:fee"}
    context["contract"] = {"status": "normal", "is_rwa": contract["is_rwa"]}
    context["n_precedents"] = precedents
    context["hedge_r2"] = float(hedge_r2)
    context["hedge_beta"] = float(hedge_beta)
    for key in ("hedge_r2_all_hours", "hedge_r2_session"):
        value = market.get(key)
        if value is None and key in market:
            context[key] = None
        elif isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
            context[key] = float(value)
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
    copied = _copy_instrument(context, market, contract, category, raw_status)
    if copied:
        return {"error": copied}
    return {"context": context, "fee_rate": fee_rate}


def _category(market: dict, contract: dict | None) -> str | None:
    for source in (market, contract or {}):
        value = source.get("instrument_category")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _copy_instrument(context: dict, market: dict, contract: dict, category: str | None, raw_status: str) -> str | None:
    if category is not None:
        context["instrument_category"] = category
    source = _present(market, contract, "metadata_source")
    if source is not None:
        if not isinstance(source, str) or not source.startswith("https://") or "?" in source:
            return "incomplete_market:metadata_source"
        context["metadata_source"] = source
    specs = (
        ("funding_interval_hours", 1),
        ("price_precision", 0),
        ("quantity_precision", 0),
    )
    for key, minimum in specs:
        if key not in market and key not in contract:
            continue
        value = market[key] if key in market else contract.get(key)
        parsed = _whole(value, minimum)
        if parsed is None:
            return "incomplete_market:" + key
        context[key] = parsed
    if "min_order_qty" in market or "min_order_qty" in contract:
        raw_qty = market["min_order_qty"] if "min_order_qty" in market else contract.get("min_order_qty")
        qty = _positive(raw_qty)
        if qty is None:
            return "incomplete_market:min_order_qty"
        context["min_order_qty"] = qty
    venue = _present(market, contract, "venue_status")
    if isinstance(venue, str) and venue.strip():
        context["venue_status"] = venue.strip()
    elif raw_status == "online":
        context["venue_status"] = "online"
    sources = _present(market, contract, "field_sources")
    if isinstance(sources, dict):
        context["field_sources"] = sources
    quote = _present(market, contract, "quote_coin")
    if quote is not None:
        if quote != "USDT":
            return "incomplete_market:quote"
        context["quote_coin"] = "USDT"
    return None


def _present(market: dict, contract: dict, key: str):
    if key in market and market[key] is not None:
        return market[key]
    if key in contract and contract[key] is not None:
        return contract[key]
    return None


def _whole(value, minimum: int) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        number = value
    elif isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            return None
        number = int(value)
    elif isinstance(value, str):
        try:
            number = int(value, 10)
        except ValueError:
            return None
    else:
        return None
    if number < minimum:
        return None
    return number


def _positive(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


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
