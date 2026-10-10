import pandas as pd
def T(x):
    """UTC-aware Timestamp from anything (naive input is interpreted as UTC)."""
    t = pd.Timestamp(x)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
