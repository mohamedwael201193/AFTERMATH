"""Preregistered S-A comparison. A small sample stays INSUFFICIENT_DATA."""

from __future__ import annotations

import random
import statistics

MIN_PAIRS = 30
MIN_NONZERO = 15
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_SEED = 20261011
ARMS = ("agent", "fixed_sign", "llm_off", "random", "no_trade")


def evaluate(pairs: list[dict]) -> dict:
    rows = [row for row in pairs if _complete(row)]
    rows.sort(key=lambda row: str(row.get("closed_at") or ""))
    nonzero = [row for row in rows if abs(_num(row, "agent_bp") - _num(row, "fixed_sign_bp")) > 1e-9]
    report = {
        "status": "INSUFFICIENT_DATA",
        "sample_size": len(rows),
        "nonzero_pairs": len(nonzero),
        "minimum_pairs": MIN_PAIRS,
        "minimum_nonzero_pairs": MIN_NONZERO,
        "calculation_version": 2,
        "label": "observed",
        "sharpe_definition": "per-trade sample standard deviation, not annualized",
        "sortino_definition": "per-trade downside deviation below zero, divided by the full sample",
        "note": "Below the preregistered minimum of 30 paired outcomes and 15 non-zero pairs.",
    }
    if len(rows) < MIN_PAIRS or len(nonzero) < MIN_NONZERO:
        return report
    report["status"] = "OBSERVED"
    report["arms"] = {name: _arm([_num(row, f"{name}_bp") for row in rows]) for name in ARMS}
    differences = [_num(row, "agent_bp") - _num(row, "fixed_sign_bp") for row in rows]
    report["paired_agent_minus_fixed_bp"] = {
        "mean": round(statistics.fmean(differences), 4),
        "bootstrap_95": _bootstrap(differences),
    }
    report["max_drawdown_bp"] = _drawdown([_num(row, "agent_bp") for row in rows])
    report["note"] = "Observed paper comparison on the registered window. This is not a profitability claim."
    return report


def _arm(values: list[float]) -> dict:
    ordered = sorted(values)
    midpoint = ordered[len(values) // 2] if len(values) % 2 else (ordered[len(values) // 2 - 1] + ordered[len(values) // 2]) / 2
    wins = sum(1 for value in values if value > 0)
    deviation = statistics.stdev(values) if len(values) > 1 else 0.0
    downside = (sum(min(value, 0.0) ** 2 for value in values) / len(values)) ** 0.5
    mean = statistics.fmean(values)
    return {
        "mean_net_bp": round(mean, 4),
        "median_net_bp": round(midpoint, 4),
        "win_rate": round(wins / len(values), 4),
        "sharpe": None if deviation == 0 else round(mean / deviation, 4),
        "sortino": None if downside == 0 else round(mean / downside, 4),
    }


def _drawdown(values: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return round(worst, 4)


def _bootstrap(differences: list[float]) -> dict:
    rng = random.Random(BOOTSTRAP_SEED)
    means = []
    width = len(differences)
    for _draw in range(BOOTSTRAP_DRAWS):
        sample = [differences[rng.randrange(width)] for _item in range(width)]
        means.append(statistics.fmean(sample))
    means.sort()
    low = means[int(0.025 * (BOOTSTRAP_DRAWS - 1))]
    high = means[int(0.975 * (BOOTSTRAP_DRAWS - 1))]
    return {"low": round(low, 4), "high": round(high, 4), "draws": BOOTSTRAP_DRAWS, "seed": BOOTSTRAP_SEED}


def _complete(row: dict) -> bool:
    return all(f"{name}_bp" in row for name in ARMS)


def _num(row: dict, key: str) -> float:
    return float(row[key])
