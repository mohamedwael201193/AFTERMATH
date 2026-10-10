"""Core-evidence gate. It runs before a model call and can only refuse."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

MAX_DATA_AGE_S = 90 * 60


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def core_blockers(events: list[dict], now: datetime | None = None) -> str | None:
    now = now or datetime.now(timezone.utc)
    if not events:
        return "insufficient_evidence"
    if any(bool(event.get("conflict")) for event in events):
        return "conflict"
    for event in events:
        if not str(event.get("source") or "").strip():
            return "missing_provenance"
        if not event.get("fetched_at_utc") or not event.get("payload_hash"):
            return "missing_provenance"
        fetched = parse_utc(str(event["fetched_at_utc"]))
        if fetched > now + timedelta(seconds=5):
            return "future_evidence"
        if (now - fetched).total_seconds() > MAX_DATA_AGE_S:
            return "stale_evidence"
        if event.get("event_type") == "ticker" and _invalid_price(event.get("payload") or {}):
            return "missing_price"
    return None


def has_order_book(events: list[dict]) -> bool:
    for event in events:
        if event.get("event_type") == "book":
            return True
        payload = event.get("payload") or {}
        if payload.get("bids") and payload.get("asks"):
            return True
    return False


def _invalid_price(payload: dict) -> bool:
    try:
        price = float(payload["last"])
    except (KeyError, TypeError, ValueError):
        return True
    return not math.isfinite(price) or price <= 0
