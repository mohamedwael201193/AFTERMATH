"""H-HF-1 event detector. This is not S-A and it is not selected.

A completed hourly residual versus QQQUSDT of at least 50 basis points is one event.
The threshold is frozen. A missing or gapped bar is not an event and is not filled with zero.
This module does not call the model, does not write the S-A ledger, and does not score a trade.
Counted evaluation, if it starts, uses only hours that close after the commit that adds this file.
"""

from __future__ import annotations

HOUR_MS = 3_600_000
THRESHOLD_BP = 50.0


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


def _closes(rows: list) -> dict[int, float]:
    closes = {}
    for row in rows:
        closes[int(row[0])] = float(row[1])
    return closes
