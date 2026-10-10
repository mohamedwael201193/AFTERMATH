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


def contract_from_record(rec: dict, symbol: str) -> dict:
    data = rec.get("data")
    rows = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    row = next((item for item in rows if isinstance(item, dict) and item.get("symbol") == symbol), None)
    if row is None and len(rows) == 1 and isinstance(rows[0], dict):
        row = rows[0]
    if not isinstance(row, dict):
        raise ApiError("SCHEMA", "contract payload empty", 422)
    if row.get("symbol") not in (None, symbol):
        raise ApiError("SCHEMA", "contract symbol mismatch", 422)
    status = row.get("symbolStatus")
    is_rwa = row.get("isRwa")
    try:
        fee = float(row.get("takerFeeRate"))
    except (TypeError, ValueError) as exc:
        raise ApiError("SCHEMA", "contract fee missing", 422) from exc
    if status != "normal" or is_rwa not in ("YES", "NO") or not _finite_number(fee) or fee < 0 or fee > 0.01:
        raise ApiError("SCHEMA", "contract metadata incomplete", 422)
    return {
        "symbol": symbol,
        "status": status,
        "is_rwa": is_rwa,
        "taker_fee_rate": fee,
        "source": "bitget-live-contracts",
        "sha256": rec.get("sha256"),
    }


def closed_candles(rec: dict, end_ms: int) -> list[list]:
    rows = []
    for raw in rec.get("data") or []:
        try:
            opened = int(raw[0])
            close = float(raw[4])
        except (TypeError, ValueError, IndexError) as exc:
            raise ApiError("SCHEMA", "candle row invalid", 422) from exc
        if opened + 3_600_000 > int(end_ms):
            continue
        if not _finite_number(close) or close <= 0:
            raise ApiError("SCHEMA", "candle close invalid", 422)
        rows.append([opened, close])
    if not rows:
        raise ApiError("SOURCE_UNAVAILABLE", "no closed candles", 503)
    return rows


def funding_from_record(rec: dict, symbol: str) -> dict:
    data = rec.get("data")
    row = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else None
    if not isinstance(row, dict):
        raise ApiError("SCHEMA", "funding payload empty", 422)
    try:
        rate = float(row.get("fundingRate"))
    except (TypeError, ValueError) as exc:
        raise ApiError("SCHEMA", "funding rate missing", 422) from exc
    if not _finite_number(rate):
        raise ApiError("SCHEMA", "funding rate invalid", 422)
    return {"symbol": symbol, "funding_rate": rate, "source": "bitget-live-funding", "sha256": rec.get("sha256")}


def market_from_public(connector, symbol: str, end_ms: int, n_precedents: int) -> dict | None:
    """Live contract and closed candles. A missing series returns None instead of a zero hedge."""
    if not isinstance(n_precedents, int) or isinstance(n_precedents, bool) or n_precedents < 0:
        return None
    try:
        contract = connector.contract(symbol)
        symbol_rows = connector.candles(symbol, end_ms=end_ms, limit=1000)
        reference_rows = connector.candles("QQQUSDT", end_ms=end_ms, limit=1000)
    except ApiError:
        return None
    fit = hedge_fit(symbol_rows, reference_rows)
    if fit["hedge_r2"] is None or fit["hedge_beta"] is None:
        return None
    return {
        "contract": {
            "status": contract["status"],
            "is_rwa": contract["is_rwa"],
            "taker_fee_rate": contract["taker_fee_rate"],
        },
        "n_precedents": n_precedents,
        "hedge_r2": fit["hedge_r2"],
        "hedge_beta": fit["hedge_beta"],
        "hedge_pairs": fit["pairs"],
        "reference": "QQQUSDT",
    }


def hedge_fit(symbol_rows: list[list], reference_rows: list[list]) -> dict:
    symbol = {int(row[0]): float(row[1]) for row in symbol_rows}
    reference = {int(row[0]): float(row[1]) for row in reference_rows}
    stamps = sorted(set(symbol) & set(reference))
    ys = []
    xs = []
    for left, right in zip(stamps, stamps[1:]):
        if symbol[left] <= 0 or reference[left] <= 0:
            continue
        ys.append(symbol[right] / symbol[left] - 1)
        xs.append(reference[right] / reference[left] - 1)
    if len(xs) < 24:
        return {"hedge_beta": None, "hedge_r2": None, "pairs": len(xs)}
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x == 0:
        return {"hedge_beta": None, "hedge_r2": None, "pairs": len(xs)}
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    beta = cov / var_x
    var_y = sum((y - mean_y) ** 2 for y in ys)
    r2 = 0.0 if var_y == 0 else (cov * cov) / (var_x * var_y)
    return {"hedge_beta": beta, "hedge_r2": r2, "pairs": len(xs)}


def _finite_number(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))


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

    def contract(self, symbol: str) -> dict:
        if symbol.startswith("fixture:"):
            raise ApiError("SCHEMA", "fixture instruments are refused", 422)
        try:
            rec = self.client.contract(symbol)
        except Exception as exc:
            raise ApiError("SOURCE_UNAVAILABLE", "bitget contract failed", 503, retryable=True) from exc
        return contract_from_record(rec, symbol)

    def candles(self, symbol: str, *, end_ms: int, limit: int = 200) -> list[list]:
        if symbol.startswith("fixture:"):
            raise ApiError("SCHEMA", "fixture instruments are refused", 422)
        try:
            rec = self.client.candles(symbol, granularity="1H", limit=str(limit), end_ms=end_ms)
        except Exception as exc:
            raise ApiError("SOURCE_UNAVAILABLE", "bitget candles failed", 503, retryable=True) from exc
        return closed_candles(rec, end_ms)

    def funding(self, symbol: str) -> dict:
        if symbol.startswith("fixture:"):
            raise ApiError("SCHEMA", "fixture instruments are refused", 422)
        try:
            rec = self.client.funding_current(symbol)
        except Exception as exc:
            raise ApiError("SOURCE_UNAVAILABLE", "bitget funding failed", 503, retryable=True) from exc
        return funding_from_record(rec, symbol)

    def depth(self, symbol: str) -> dict:
        if symbol.startswith("fixture:"):
            raise ApiError("SCHEMA", "fixture instruments are refused", 422)
        try:
            rec = self.client.depth(symbol, limit="15")
        except Exception as exc:
            raise ApiError("SOURCE_UNAVAILABLE", "bitget depth failed", 503, retryable=True) from exc
        return observation_from_depth(rec)
