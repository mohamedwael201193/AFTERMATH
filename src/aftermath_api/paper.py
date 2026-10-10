"""Paper fills through the vendored book walk. No private order URL."""

from __future__ import annotations

import math
import sys
from pathlib import Path

VENDOR = Path(__file__).resolve().parents[2] / "third_party" / "aftermath"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

from FINAL_CANDIDATE.t2.execution import walk_book  # noqa: E402
from FINAL_CANDIDATE.t2.governor import check as governor_check  # noqa: E402


def safe_context(ctx: dict) -> dict:
    out = dict(ctx)
    for key, value in list(out.items()):
        if isinstance(value, float) and not math.isfinite(value):
            out[key] = value
    return out


def govern(proposal: dict | None, ctx: dict) -> dict:
    return governor_check(proposal, safe_context(ctx))


def paper_fill(side: int, notional: float, ref_price: float, profile: dict, fee_rate: float) -> dict:
    if not math.isfinite(notional) or not math.isfinite(ref_price) or notional <= 0 or ref_price <= 0:
        return {"status": "PAPER_UNFILLED", "reason": "invalid_price_or_size"}
    result = walk_book(side, notional, ref_price, profile, fee_rate)
    if isinstance(result.get("vwap"), float) and not math.isfinite(result["vwap"]):
        result["vwap"] = None
    if result.get("slippage_bp") is not None and isinstance(result["slippage_bp"], float) and not math.isfinite(result["slippage_bp"]):
        result["slippage_bp"] = None
    status = "PAPER_FILLED" if result["filled_usdt"] > 0 and result["unfilled_usdt"] <= 1e-6 else "PAPER_UNFILLED"
    return {"status": status, "walk": result}
