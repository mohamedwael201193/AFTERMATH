"""Bitget public REST via the vendored client. Failures are not observations."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / "third_party" / "aftermath"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

from FINAL_CANDIDATE.t2.marketdata import BitgetPublic, book_from_depth  # noqa: E402

from .errors import ApiError


def _age_seconds(fetched_at_utc: str, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    ts = datetime.fromisoformat(fetched_at_utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds()


def observation_from_ticker(rec: dict, *, now: datetime | None = None, max_age_s: float = 60.0) -> dict:
    data = rec.get("data")
    row = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else None
    if not row or row.get("lastPr") in (None, ""):
        raise ApiError("SOURCE_UNAVAILABLE", "ticker payload empty", 503, retryable=True)
    try:
        price = float(row["lastPr"])
    except (TypeError, ValueError) as exc:
        raise ApiError("SCHEMA", "ticker price not numeric", 422) from exc
    if price <= 0 or price != price or price == float("inf"):
        raise ApiError("SCHEMA", "ticker price invalid", 422)
    age = _age_seconds(rec["fetched_at_utc"], now)
    if age > max_age_s:
        raise ApiError("STALE", "ticker older than 60 seconds", 409)
    return {
        "source": "bitget-rest",
        "endpoint": rec["endpoint"],
        "instrument_id": rec["params"]["symbol"],
        "event_type": "ticker",
        "event_time_utc": rec["fetched_at_utc"],
        "fetched_at_utc": rec["fetched_at_utc"],
        "payload": {"last": price, "raw_sha256": rec["sha256"]},
        "mapping_confidence": 1.0,
    }


def require_sec_user_agent(user_agent: str) -> None:
    if not user_agent.strip():
        raise ApiError("SOURCE_UNAVAILABLE", "sec_user_agent_missing", 503)


def interpret_mcp(payload: dict) -> dict:
    if not isinstance(payload, dict) or payload.get("ok") is not True or payload.get("error"):
        raise ApiError("SOURCE_UNAVAILABLE", "mcp result is not usable", 503)
    if payload.get("data") in (None, [], {}):
        raise ApiError("SOURCE_UNAVAILABLE", "mcp payload empty", 503)
    return payload


def observation_from_depth(rec: dict, *, now: datetime | None = None, max_age_s: float = 60.0) -> dict:
    try:
        book = book_from_depth(rec)
        bids = book["bids"]
        asks = book["asks"]
        bid, _bid_size = bids[0]
        ask, _ask_size = asks[0]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ApiError("SOURCE_UNAVAILABLE", "depth payload empty", 503, retryable=True) from exc
    if not _finite_positive(bid) or not _finite_positive(ask) or ask <= bid:
        raise ApiError("SCHEMA", "depth quotes invalid", 422)
    mid = (bid + ask) / 2
    spread_bp = (ask - bid) / mid * 1e4
    depth_usdt = 0.0
    for price, size in list(bids) + list(asks):
        if not _finite_positive(price) or not _finite_positive(size):
            continue
        if abs(price - mid) / mid * 1e4 <= 25:
            depth_usdt += price * size
    age = _age_seconds(rec["fetched_at_utc"], now)
    if age > max_age_s:
        raise ApiError("STALE", "depth older than 60 seconds", 409)
    return {
        "source": "bitget-rest",
        "endpoint": rec["endpoint"],
        "instrument_id": rec["params"]["symbol"],
        "event_type": "book",
        "event_time_utc": rec["fetched_at_utc"],
        "fetched_at_utc": rec["fetched_at_utc"],
        "payload": {
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "spread_bp": round(spread_bp, 4),
            "depth_usdt": round(depth_usdt, 2),
            "bids": bids[:5],
            "asks": asks[:5],
            "raw_sha256": rec["sha256"],
        },
        "mapping_confidence": 1.0,
    }


def _finite_positive(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf")) and value > 0


class BitgetConnector:
    def __init__(self, cache_dir: Path, mode: str = "live", fetch=None):
        self.client = BitgetPublic(cache_dir, mode=mode, fetch=fetch)

    def ticker(self, symbol: str) -> dict:
        if symbol.startswith("fixture:"):
            raise ApiError("SCHEMA", "fixture instruments are refused", 422)
        try:
            rec = self.client.ticker(symbol)
        except Exception as exc:
            raise ApiError("SOURCE_UNAVAILABLE", "bitget ticker failed", 503, retryable=True) from exc
        return observation_from_ticker(rec)

    def depth(self, symbol: str) -> dict:
        if symbol.startswith("fixture:"):
            raise ApiError("SCHEMA", "fixture instruments are refused", 422)
        try:
            rec = self.client.depth(symbol, limit="15")
        except Exception as exc:
            raise ApiError("SOURCE_UNAVAILABLE", "bitget depth failed", 503, retryable=True) from exc
        return observation_from_depth(rec)
