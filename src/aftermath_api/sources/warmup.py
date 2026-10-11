"""Historical Item 2.02 reactions. They can satisfy the precedent count and are not outcomes."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone

from .edgar import MAX_EVENT_AGE

def residual_bp(stock_before, stock_after, ref_before, ref_after) -> float | None:
    """Return the stock-minus-reference move in basis points. A missing price stays missing."""
    try:
        values = [float(stock_before), float(stock_after), float(ref_before), float(ref_after)]
    except (TypeError, ValueError):
        return None
    if any(isinstance(value, bool) or not math.isfinite(value) or value <= 0 for value in values):
        return None
    stock = values[1] / values[0] - 1
    reference = values[3] / values[2] - 1
    return round((stock - reference) * 1e4, 4)


def warmup_event(
    *,
    symbol: str,
    accession: str,
    event_time: datetime,
    stock_before,
    stock_after,
    ref_before,
    ref_after,
    now: datetime,
    items: str = "2.02",
) -> dict | None:
    """Build a stored reaction older than the trade window. A fresh filing is refused."""
    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if now - event_time <= MAX_EVENT_AGE:
        return None
    reaction = residual_bp(stock_before, stock_after, ref_before, ref_after)
    if reaction is None or not accession:
        return None
    return {
        "id": "evw_" + uuid.uuid4().hex[:16],
        "source": "sec-edgar",
        "instrument_id": symbol,
        "event_type": "filing",
        "event_time_utc": event_time.isoformat(),
        "fetched_at_utc": now.isoformat(),
        "mapping_confidence": 1.0,
        "payload": {
            "form": "8-K",
            "items": items,
            "accession": accession,
            "counted": True,
            "warmup": True,
            "counted_outcome": False,
            "reaction_bp": reaction,
        },
    }


def store_warmup(store, event: dict | None) -> bool:
    """Insert one warm-up row. It does not create a fill or a decision."""
    if not event:
        return False
    accession = (event.get("payload") or {}).get("accession")
    if accession and store.has_accession(accession):
        return False
    store.insert_event(event)
    return True
