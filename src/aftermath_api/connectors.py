"""Bitget public REST via the vendored client. Failures are not observations."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
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


FUTURES_CATEGORY = "USDT-FUTURES"
_PROVENANCE_KEYS = (
    "instrument_category",
    "metadata_source",
    "funding_interval_hours",
    "price_precision",
    "quantity_precision",
    "min_order_qty",
    "field_sources",
    "venue_status",
    "quote_coin",
    "symbol",
)


def _contract_rows(data) -> list[dict]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _public_url(endpoint: object) -> str:
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ApiError("SCHEMA", "contract endpoint missing", 422)
    bare = endpoint.split("?", 1)[0].strip()
    if bare.startswith("https://") or bare.startswith("http://"):
        url = bare
    elif bare.startswith("/"):
        url = "https://api.bitget.com" + bare
    else:
        raise ApiError("SCHEMA", "contract endpoint missing", 422)
    host = url.split("://", 1)[-1].split("/", 1)[0]
    if "@" in host or "?" in url or "/api/" not in url:
        raise ApiError("SCHEMA", "contract endpoint missing", 422)
    return url


def _required_decimal(value: object, label: str) -> float:
    if isinstance(value, bool) or value in (None, ""):
        raise ApiError("SCHEMA", f"contract {label} missing", 422)
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ApiError("SCHEMA", f"contract {label} missing", 422) from exc
    if not _finite_number(number):
        raise ApiError("SCHEMA", f"contract {label} missing", 422)
    return number


def _required_whole(value: object, label: str, *, minimum: int) -> int:
    number = _required_decimal(value, label)
    if number < minimum or int(number) != number:
        raise ApiError("SCHEMA", f"contract {label} missing", 422)
    return int(number)


def _optional_hours(value: object) -> int | None:
    if isinstance(value, bool) or value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not _finite_number(number) or number <= 0 or int(number) != number:
        return None
    return int(number)


def contract_from_record(rec: dict, symbol: str) -> dict:
    """USDT-FUTURES contract only. isRwa is read from this futures row when the venue sends it.

    Live v2 mix contracts and v3 UTA instruments both return isRwa on USDT-FUTURES (YES on the
    stock perps, NO on BTCUSDT). Spot instruments do not. A SPOT row is refused even if it
    carries isRwa or isReality. Missing fee, funding interval, precision, or min qty is an
    error; nothing is filled with zero or a generic fee.
    """
    rows = _contract_rows(rec.get("data"))
    matched = [item for item in rows if item.get("symbol") == symbol]
    if len(matched) != 1:
        if any(item.get("symbol") not in (None, "", symbol) for item in rows):
            raise ApiError("SCHEMA", "contract symbol mismatch", 422)
        raise ApiError("SCHEMA", "contract payload empty", 422)
    row = matched[0]
    params = rec.get("params") if isinstance(rec.get("params"), dict) else {}
    if params.get("symbol") not in (None, "", symbol):
        raise ApiError("SCHEMA", "contract symbol mismatch", 422)
    row_category = row.get("category")
    param_category = params.get("productType") or params.get("category")
    if row_category not in (None, "") and param_category not in (None, "") and row_category != param_category:
        raise ApiError("SCHEMA", "contract category mismatch", 422)
    category = row_category or param_category
    if category != FUTURES_CATEGORY:
        raise ApiError("SCHEMA", "contract category is not USDT-FUTURES", 422)
    source = _public_url(rec.get("endpoint"))
    raw_status = row.get("symbolStatus")
    status_field = "symbolStatus"
    if raw_status in (None, ""):
        raw_status = row.get("status")
        status_field = "status"
    if raw_status not in ("normal", "online"):
        raise ApiError("SCHEMA", "contract status not tradeable", 422)
    contract_type = row.get("type")
    symbol_type = row.get("symbolType")
    if contract_type not in (None, ""):
        if str(contract_type).lower() != "perpetual":
            raise ApiError("SCHEMA", "contract is not a perpetual", 422)
    elif symbol_type is None or str(symbol_type).lower() != "perpetual":
        raise ApiError("SCHEMA", "contract is not a perpetual", 422)
    if row.get("quoteCoin") != "USDT":
        raise ApiError("SCHEMA", "contract quote is not USDT", 422)
    is_rwa = row.get("isRwa")
    if is_rwa not in ("YES", "NO"):
        raise ApiError("SCHEMA", "futures isRwa missing", 422)
    fee = _required_decimal(row.get("takerFeeRate"), "fee")
    if fee < 0 or fee > 0.01:
        raise ApiError("SCHEMA", "contract fee invalid", 422)
    hours = _required_whole(row.get("fundInterval"), "funding interval", minimum=1)
    if row.get("pricePrecision") not in (None, "") or row.get("quantityPrecision") not in (None, ""):
        price_field, qty_field = "pricePrecision", "quantityPrecision"
    elif row.get("pricePlace") not in (None, "") or row.get("volumePlace") not in (None, ""):
        price_field, qty_field = "pricePlace", "volumePlace"
    else:
        raise ApiError("SCHEMA", "contract precision missing", 422)
    price_precision = _required_whole(row.get(price_field), "price precision", minimum=0)
    quantity_precision = _required_whole(row.get(qty_field), "quantity precision", minimum=0)
    if row.get("minOrderQty") not in (None, ""):
        qty_name = "minOrderQty"
    elif row.get("minTradeNum") not in (None, ""):
        qty_name = "minTradeNum"
    else:
        raise ApiError("SCHEMA", "contract min qty missing", 422)
    min_qty = _required_decimal(row.get(qty_name), "min qty")
    if min_qty <= 0:
        raise ApiError("SCHEMA", "contract min qty missing", 422)
    maker = row.get("makerFeeRate")
    maker_fee = None
    if maker not in (None, ""):
        maker_fee = _required_decimal(maker, "maker fee")
        if maker_fee < 0 or maker_fee > 0.01:
            raise ApiError("SCHEMA", "contract fee invalid", 422)
    def field(name: str) -> dict:
        return {"category": FUTURES_CATEGORY, "endpoint": source, "field": name}
    parsed = {
        "symbol": symbol,
        "status": "normal",
        "venue_status": raw_status,
        "is_rwa": is_rwa,
        "taker_fee_rate": fee,
        "instrument_category": FUTURES_CATEGORY,
        "metadata_source": source,
        "funding_interval_hours": hours,
        "price_precision": price_precision,
        "quantity_precision": quantity_precision,
        "min_order_qty": min_qty,
        "quote_coin": "USDT",
        "symbol_type": None if symbol_type in (None, "") else str(symbol_type),
        "contract_type": "perpetual",
        "source": "bitget-live-contracts",
        "sha256": rec.get("sha256"),
        "field_sources": {
            "status": field(status_field),
            "is_rwa": field("isRwa"),
            "taker_fee_rate": field("takerFeeRate"),
            "funding_interval_hours": field("fundInterval"),
            "price_precision": field(price_field),
            "quantity_precision": field(qty_field),
            "min_order_qty": field(qty_name),
            "quote_coin": field("quoteCoin"),
        },
    }
    if maker_fee is not None:
        parsed["maker_fee_rate"] = maker_fee
        parsed["field_sources"]["maker_fee_rate"] = field("makerFeeRate")
    return parsed


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
    params = rec.get("params") if isinstance(rec.get("params"), dict) else {}
    category = params.get("productType") or params.get("category")
    if category not in (None, "", FUTURES_CATEGORY):
        raise ApiError("SCHEMA", "funding category is not USDT-FUTURES", 422)
    data = rec.get("data")
    row = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else None
    if not isinstance(row, dict):
        raise ApiError("SCHEMA", "funding payload empty", 422)
    if row.get("symbol") not in (None, "", symbol):
        raise ApiError("SCHEMA", "funding symbol mismatch", 422)
    try:
        rate = float(row.get("fundingRate"))
    except (TypeError, ValueError) as exc:
        raise ApiError("SCHEMA", "funding rate missing", 422) from exc
    if isinstance(row.get("fundingRate"), bool) or not _finite_number(rate):
        raise ApiError("SCHEMA", "funding rate invalid", 422)
    parsed = {"symbol": symbol, "funding_rate": rate, "source": "bitget-live-funding", "sha256": rec.get("sha256")}
    if category:
        parsed["instrument_category"] = category
    interval = row.get("fundingRateInterval")
    interval_field = "fundingRateInterval"
    if interval in (None, ""):
        interval = row.get("fundInterval")
        interval_field = "fundInterval"
    if interval not in (None, ""):
        hours = _optional_hours(interval)
        if hours is None:
            raise ApiError("SCHEMA", "funding interval missing", 422)
        parsed["funding_interval_hours"] = hours
        if isinstance(rec.get("endpoint"), str) and rec.get("endpoint").strip():
            source = _public_url(rec.get("endpoint"))
            parsed["metadata_source"] = source
            parsed["field_sources"] = {
                "funding_rate": {"category": category or FUTURES_CATEGORY, "endpoint": source, "field": "fundingRate"},
                "funding_interval_hours": {"category": category or FUTURES_CATEGORY, "endpoint": source, "field": interval_field},
            }
    return parsed


def funding_history_from_record(rec: dict, symbol: str) -> list[dict]:
    """Chronological venue settlements. An empty page is an empty list, not a zero rate."""
    params = rec.get("params") if isinstance(rec.get("params"), dict) else {}
    category = params.get("productType") or params.get("category")
    if category not in (None, "", FUTURES_CATEGORY):
        raise ApiError("SCHEMA", "funding category is not USDT-FUTURES", 422)
    data = rec.get("data")
    if data is None:
        data = []
    if not isinstance(data, list):
        raise ApiError("SCHEMA", "funding history empty", 422)
    prints = []
    for row in data:
        if not isinstance(row, dict):
            raise ApiError("SCHEMA", "funding history row invalid", 422)
        if row.get("symbol") not in (None, "", symbol):
            raise ApiError("SCHEMA", "funding symbol mismatch", 422)
        raw = row.get("fundingRate")
        if isinstance(raw, bool):
            raise ApiError("SCHEMA", "funding rate invalid", 422)
        try:
            rate = float(raw)
            stamp = datetime.fromtimestamp(int(row["fundingTime"]) / 1000, timezone.utc)
        except (TypeError, ValueError, KeyError, OSError) as exc:
            raise ApiError("SCHEMA", "funding history row invalid", 422) from exc
        if not _finite_number(rate):
            raise ApiError("SCHEMA", "funding rate invalid", 422)
        prints.append({"funding_time_utc": stamp.isoformat(), "rate": rate})
    prints.sort(key=lambda item: item["funding_time_utc"])
    return prints


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
    session = hedge_fit(
        [row for row in symbol_rows if _regular_session(row[0])],
        [row for row in reference_rows if _regular_session(row[0])],
    )
    built = {
        "contract": {
            "status": contract["status"],
            "is_rwa": contract["is_rwa"],
            "taker_fee_rate": contract["taker_fee_rate"],
        },
        "n_precedents": n_precedents,
        "hedge_r2": fit["hedge_r2"],
        "hedge_r2_all_hours": fit["hedge_r2"],
        "hedge_r2_session": session["hedge_r2"],
        "hedge_beta": fit["hedge_beta"],
        "hedge_pairs": fit["pairs"],
        "reference": "QQQUSDT",
    }
    for key in _PROVENANCE_KEYS:
        if contract.get(key) is not None:
            built[key] = contract[key]
    return built


def _regular_session(open_ms) -> bool:
    """US cash session in America/New_York. The governor still uses the all-hours fit."""
    try:
        instant = datetime.fromtimestamp(int(open_ms) / 1000, ZoneInfo("America/New_York"))
    except (TypeError, ValueError, OSError):
        return False
    if instant.weekday() >= 5:
        return False
    minutes = instant.hour * 60 + instant.minute
    return 9 * 60 + 30 <= minutes < 16 * 60


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

    def funding_history(self, symbol: str) -> list[dict]:
        if symbol.startswith("fixture:"):
            raise ApiError("SCHEMA", "fixture instruments are refused", 422)
        try:
            rec = self.client.funding_history(symbol, page_size=100)
        except Exception as exc:
            raise ApiError("SOURCE_UNAVAILABLE", "bitget funding history failed", 503, retryable=True) from exc
        return funding_history_from_record(rec, symbol)

    def depth(self, symbol: str) -> dict:
        if symbol.startswith("fixture:"):
            raise ApiError("SCHEMA", "fixture instruments are refused", 422)
        try:
            rec = self.client.depth(symbol, limit="15")
        except Exception as exc:
            raise ApiError("SOURCE_UNAVAILABLE", "bitget depth failed", 503, retryable=True) from exc
        return observation_from_depth(rec)
