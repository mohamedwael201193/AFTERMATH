"""Server-derived paper execution inputs. The caller does not supply the book."""

from __future__ import annotations

import math
from datetime import datetime, timezone

CALLER_FIELDS = ("risk_context", "book", "ref_price", "side", "fee_rate", "notional")
PAPER_EQUITY = 10_000.0
DEFAULT_TAKER_FEE = 0.0006


def caller_controlled(body: dict) -> list[str]:
    return [name for name in CALLER_FIELDS if name in body]


def derive_execution(proposal: dict, events: list[dict], decision_source: str, now: datetime | None = None) -> dict:
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
    occurred = _parse(event.get("event_time_utc")) or fetched
    if fetched is None:
        return {"error": "missing_provenance"}
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {"status": "unknown", "is_rwa": "NO"}
    return {
        "error": None,
        "side": 1 if action == "LONG" else -1,
        "ref_price": mid,
        "fee_rate": fee_rate,
        "profile": profile,
        "book_hash": payload.get("raw_sha256"),
        "proposal_fetched_at": fetched.isoformat(),
        "context": {
            "symbol": symbol,
            "source": "llm" if decision_source == "model" else "rule",
            "emergency_stop": False,
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
        },
    }


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
