"""H-HF-1 event detector. This is not S-A and it is not selected.

A completed hourly residual versus QQQUSDT of at least 50 basis points is one event.
The threshold is frozen. A missing or gapped bar is not an event and is not filled with zero.
This module does not call the model, does not write the S-A ledger, and does not score a trade.
Counted evaluation, if it starts, uses only hours that close after the commit that adds this file.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

HOUR_MS = 3_600_000
THRESHOLD_BP = 50.0
REFERENCE = "QQQUSDT"
UNIVERSE = (
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
# Commit 29ecf0db2a60114e95a8a41f6a339bf18e443a58, the commit that added this file.
COUNTED_AFTER = datetime(2026, 10, 11, 1, 26, 21, tzinfo=timezone.utc)


def hourly_residual_events(stock_rows: list, ref_rows: list, threshold_bp: float = THRESHOLD_BP) -> list[dict]:
    """Return signal hours where the completed residual clears the frozen threshold.

    Each row is [open_ms, close]. Both symbols must share that open time.
    Adjacent hours must be exactly one hour apart. A gap stays a gap.
    """
    stock = _closes(stock_rows)
    ref = _closes(ref_rows)
    shared = sorted(set(stock) & set(ref))
    events = []
    for previous, current in zip(shared, shared[1:]):
        if current - previous != HOUR_MS:
            continue
        values = (stock[previous], stock[current], ref[previous], ref[current])
        if any(value <= 0 for value in values):
            continue
        stock_return = values[1] / values[0] - 1
        reference_return = values[3] / values[2] - 1
        residual = (stock_return - reference_return) * 1e4
        if abs(residual) < float(threshold_bp):
            continue
        events.append({
            "signal_open_ms": current,
            "residual_bp": round(residual, 4),
            "threshold_bp": float(threshold_bp),
            "strategy_id": "H-HF-1",
            "counted_outcome": False,
        })
    return events


def prospective_scan(bars_by_symbol: dict, now_ms: int, counted_after_ms: int | None = None) -> dict:
    """Scan closed hours. The result is not a trade and is not an S-A outcome."""
    cutoff = int(COUNTED_AFTER.timestamp() * 1000) if counted_after_ms is None else int(counted_after_ms)
    ref = _closed_rows(bars_by_symbol.get(REFERENCE) or [], now_ms)
    events = []
    latest = []
    for symbol, rows in bars_by_symbol.items():
        if symbol == REFERENCE:
            continue
        stock = _closed_rows(rows, now_ms)
        found = [
            row for row in hourly_residual_events(stock, ref)
            if int(row["signal_open_ms"]) + HOUR_MS > cutoff
        ]
        events.extend({**row, "symbol": symbol} for row in found)
        residual = _latest_residual(stock, ref)
        if residual is not None and int(residual["signal_open_ms"]) + HOUR_MS > cutoff:
            latest.append({"symbol": symbol, **residual})
    return {
        "strategy_id": "H-HF-1",
        "counted_outcome": False,
        "selected": False,
        "model_called": False,
        "events": events,
        "latest": latest,
    }


def scan_live(now: datetime) -> dict:
    """Read public hourly candles. A failed symbol stays missing."""
    from ..connectors import BitgetConnector

    cache = Path("/tmp/aftermath-cache") if Path("/tmp").is_dir() else Path("cache")
    cache.mkdir(parents=True, exist_ok=True)
    connector = BitgetConnector(cache, mode="live")
    end_ms = int(now.timestamp() * 1000)
    bars = {}
    errors = []
    for symbol in (*UNIVERSE, REFERENCE):
        try:
            bars[symbol] = connector.candles(symbol, end_ms=end_ms, limit=4)
        except Exception:
            errors.append(symbol)
    report = prospective_scan(bars, end_ms)
    report["fetch_errors"] = errors
    return report


def _closed_rows(rows: list, now_ms: int) -> list:
    return [row for row in rows if int(row[0]) + HOUR_MS <= int(now_ms)]


def _latest_residual(stock_rows: list, ref_rows: list) -> dict | None:
    stock = _closes(stock_rows)
    ref = _closes(ref_rows)
    shared = sorted(set(stock) & set(ref))
    for previous, current in reversed(list(zip(shared, shared[1:]))):
        if current - previous != HOUR_MS:
            continue
        values = (stock[previous], stock[current], ref[previous], ref[current])
        if any(value <= 0 for value in values):
            continue
        residual = ((values[1] / values[0] - 1) - (values[3] / values[2] - 1)) * 1e4
        return {"signal_open_ms": current, "residual_bp": round(residual, 4), "event": abs(residual) >= THRESHOLD_BP}
    return None


def _closes(rows: list) -> dict[int, float]:
    closes = {}
    for row in rows:
        closes[int(row[0])] = float(row[1])
    return closes
