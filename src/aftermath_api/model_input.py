"""Versioned model input. The symbol comes from the server map. Bar math uses only closed hours."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .connectors import hedge_fit
from .execution_context import PAPER_EQUITY
from .sources.edgar import CIK_TO_SYMBOL
from .sources.warmup import residual_bp

BAR_MS = 3_600_000
SIZE_FRAC = 0.05
HORIZON_HOURS = 24.0
INPUT_VERSION = "decision_v4"
_EASTERN = ZoneInfo("America/New_York")
MAPPED_SYMBOLS = set(CIK_TO_SYMBOL.values())


def mapped_symbol(symbol: str) -> str | None:
    if symbol in MAPPED_SYMBOLS:
        return symbol
    return None


def build_decision_input(evidence_rows: list[dict], symbol: str, market: dict | None, now: datetime) -> dict:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    filing = _filing(evidence_rows, symbol)
    payload = filing.get("payload") or {}
    accepted = _parse(filing.get("event_time_utc"))
    book = _book(evidence_rows, symbol)
    contract = (market or {}).get("contract") if isinstance((market or {}).get("contract"), dict) else {}
    bars = _closed_pairs(
        (market or {}).get("symbol_bars") or [],
        (market or {}).get("reference_bars") or [],
        int(now.timestamp() * 1000),
    )
    residual = _residual(bars, accepted, now)
    excerpt = payload.get("exhibit_excerpt") or payload.get("excerpt")
    if not isinstance(excerpt, str) or excerpt.lstrip().startswith("<?xml"):
        excerpt = None
    return {
        "version": INPUT_VERSION,
        "event": {
            "accession": payload.get("accession"),
            "items": payload.get("items"),
            "accepted_at_utc": None if accepted is None else accepted.isoformat(),
            "clock_source": payload.get("clock_source"),
            "source_url": payload.get("source_url"),
            "exhibit_url": payload.get("exhibit_url"),
            "exhibit_sha256": payload.get("exhibit_sha256"),
            "exhibit_excerpt": excerpt,
            "excerpt_untrusted": True,
        },
        "instrument": {
            "symbol": symbol,
            "status": contract.get("status"),
            "is_rwa": contract.get("is_rwa"),
            "min_order_qty": (market or {}).get("min_order_qty"),
            "min_trade_usdt": (market or {}).get("min_trade_usdt") or contract.get("min_trade_usdt"),
            "taker_fee_rate": contract.get("taker_fee_rate"),
            "funding_interval_hours": (market or {}).get("funding_interval_hours"),
            "funding_rate": (market or {}).get("funding_rate"),
        },
        "residual": residual,
        "costs": {
            "taker_fee_rate": contract.get("taker_fee_rate"),
            "spread_bp": (book.get("payload") or {}).get("spread_bp"),
            "notional_usdt": PAPER_EQUITY * SIZE_FRAC,
        },
        "uncertainty": {
            "hedge_r2": None if residual is None else residual.get("r2"),
            "pairs": None if residual is None else residual.get("n"),
            "sigma_bp": None if residual is None else residual.get("sigma_bp"),
        },
        "fixed": {"notional_usdt": PAPER_EQUITY * SIZE_FRAC, "size_frac": SIZE_FRAC, "horizon_hours": HORIZON_HOURS},
        "evidence": [
            {
                "id": row.get("id"),
                "payload_hash": row.get("payload_hash"),
                "event_type": (row.get("event") or {}).get("event_type"),
            }
            for row in evidence_rows
        ],
    }


def _filing(rows: list[dict], symbol: str) -> dict:
    for row in rows:
        event = row.get("event") or {}
        if event.get("event_type") == "filing" and event.get("instrument_id") == symbol:
            return event
    return {}


def _book(rows: list[dict], symbol: str) -> dict:
    for row in rows:
        event = row.get("event") or {}
        if event.get("event_type") == "book" and event.get("instrument_id") == symbol:
            return event
    return {}


def _closed_pairs(symbol_rows, reference_rows, decision_ms: int) -> tuple[list, list]:
    symbol = [row for row in symbol_rows if _closed(row, decision_ms)]
    reference = [row for row in reference_rows if _closed(row, decision_ms)]
    return symbol, reference


def _closed(row, decision_ms: int) -> bool:
    try:
        opened = int(row[0])
        close = float(row[1])
    except (TypeError, ValueError, IndexError):
        return False
    return opened + BAR_MS <= decision_ms and math.isfinite(close) and close > 0


def _residual(bars: tuple[list, list], accepted: datetime | None, now: datetime) -> dict | None:
    symbol_rows, reference_rows = bars
    fit = hedge_fit(symbol_rows, reference_rows)
    flags = _flags(accepted)
    base = {
        "reference": "QQQUSDT",
        "beta": fit["hedge_beta"],
        "r2": fit["hedge_r2"],
        "n": fit["pairs"],
        "sigma_bp": _sigma_bp(symbol_rows, reference_rows, fit["hedge_beta"]),
        "pre_bp": None,
        "post_bp": None,
        "residual_bp": None,
        "z": None,
        **flags,
    }
    if accepted is None:
        return base
    move = _move(symbol_rows, reference_rows, accepted, now)
    if move is None:
        return base
    stock_before, stock_after, ref_before, ref_after = move
    residual = residual_bp(stock_before, stock_after, ref_before, ref_after)
    sigma = base["sigma_bp"]
    z = None
    if residual is not None and isinstance(sigma, float) and sigma > 0:
        z = residual / sigma
    base.update({
        "pre_bp": None,
        "post_bp": residual,
        "residual_bp": residual,
        "z": z,
    })
    return base


def _move(symbol_rows, reference_rows, accepted: datetime, now: datetime):
    symbol = {int(row[0]): float(row[1]) for row in symbol_rows}
    reference = {int(row[0]): float(row[1]) for row in reference_rows}
    shared = sorted(set(symbol) & set(reference))
    event_ms = int(accepted.timestamp() * 1000)
    decision_ms = int(now.timestamp() * 1000)
    before = [stamp for stamp in shared if stamp + BAR_MS <= event_ms]
    after = [stamp for stamp in shared if stamp >= event_ms and stamp + BAR_MS <= decision_ms]
    if not before or not after:
        return None
    left = before[-1]
    right = after[0]
    return symbol[left], symbol[right], reference[left], reference[right]


def _sigma_bp(symbol_rows, reference_rows, beta) -> float | None:
    if not isinstance(beta, float) or not math.isfinite(beta):
        return None
    symbol = {int(row[0]): float(row[1]) for row in symbol_rows}
    reference = {int(row[0]): float(row[1]) for row in reference_rows}
    stamps = sorted(set(symbol) & set(reference))
    gaps = []
    for left, right in zip(stamps, stamps[1:]):
        if symbol[left] <= 0 or reference[left] <= 0:
            continue
        stock = symbol[right] / symbol[left] - 1
        ref = reference[right] / reference[left] - 1
        gaps.append((stock - beta * ref) * 1e4)
    if len(gaps) < 24:
        return None
    mean = sum(gaps) / len(gaps)
    var = sum((gap - mean) ** 2 for gap in gaps) / len(gaps)
    if var <= 0:
        return 0.0
    return math.sqrt(var)


def _flags(accepted: datetime | None) -> dict:
    if accepted is None:
        return {"session": None, "weekend": None}
    local = accepted.astimezone(_EASTERN)
    minutes = local.hour * 60 + local.minute
    return {
        "session": local.weekday() < 5 and 9 * 60 + 30 <= minutes < 16 * 60,
        "weekend": local.weekday() >= 5,
    }


def _parse(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
