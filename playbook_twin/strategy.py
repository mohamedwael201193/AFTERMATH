"""Labelled Studio twin. It does not call AFTERMATH, EDGAR, or a live order endpoint."""

LABEL = (
    "Separate Studio implementation; Bitget-managed model/data; "
    "15-minute-or-slower polling; no direct EDGAR or AFTERMATH call."
)
SIZE_FRAC = 0.05
HORIZON_HOURS = 24


def decide(evidence: dict) -> dict:
    """Return a paper proposal. Size and horizon stay fixed."""
    symbol = str(evidence.get("symbol") or "")
    residual = evidence.get("residual_bp")
    if symbol not in {
        "NVDAUSDT", "TSLAUSDT", "AAPLUSDT", "AMZNUSDT", "MSFTUSDT",
        "METAUSDT", "GOOGLUSDT", "COINUSDT", "MSTRUSDT",
    }:
        action = "NO_ACTION"
    elif not isinstance(residual, (int, float)) or isinstance(residual, bool):
        action = "NO_ACTION"
    elif residual > 0:
        action = "LONG"
    elif residual < 0:
        action = "SHORT"
    else:
        action = "NO_ACTION"
    return {
        "label": LABEL,
        "action": action,
        "symbol": symbol,
        "size_frac": SIZE_FRAC,
        "horizon_hours": HORIZON_HOURS,
        "merge_into_aftermath_metrics": False,
    }
