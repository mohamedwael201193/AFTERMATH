"""Instrument identity. Ambiguous tickers do not become Bitget symbols."""

from __future__ import annotations

AMBIGUOUS = {"BB", "STX"}
MIN_CONFIDENCE = 0.9


def resolve_symbol(ticker: str, aliases: dict[str, str] | None = None) -> tuple[str | None, float, str | None]:
    raw = ticker.strip().upper()
    if raw in AMBIGUOUS:
        return None, 0.0, "ambiguous"
    table = {k.upper(): v for k, v in (aliases or {}).items()}
    if raw in table:
        return table[raw], 1.0, None
    if raw.endswith("USDT") and raw.isalnum():
        return raw, 1.0, None
    return None, 0.0, "unmapped"


def accept_mapping(confidence: float) -> bool:
    return confidence >= MIN_CONFIDENCE
