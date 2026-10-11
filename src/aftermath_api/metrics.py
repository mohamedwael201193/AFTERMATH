"""Preregistered S-A comparison. A small sample stays INSUFFICIENT_DATA."""

from __future__ import annotations

import math
import random
import statistics
from datetime import datetime, timedelta, timezone

MIN_PAIRS = 30
MIN_NONZERO = 15
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_SEED = 20261011
ARMS = ("agent", "fixed_sign", "llm_off", "random", "no_trade")
BASELINES = ("fixed_sign", "llm_off", "random", "no_trade")
COST_KEYS = ("fees_bp", "funding_bp", "slippage_bp")


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
    agent_values = [_num(row, "agent_bp") for row in rows]
    report["status"] = "OBSERVED"
    report["arms"] = {name: _arm([_num(row, f"{name}_bp") for row in rows]) for name in ARMS}
    agent = report["arms"]["agent"]
    report["net_return_bp"] = round(sum(agent_values), 4)
    report["win_rate"] = agent["win_rate"]
    report["sharpe"] = agent["sharpe"]
    report["paired_comparisons"] = {
        baseline: _paired_comparison(rows, baseline) for baseline in BASELINES
    }
    differences = [_num(row, "agent_bp") - _num(row, "fixed_sign_bp") for row in rows]
    report["paired_agent_minus_fixed_bp"] = report["paired_comparisons"]["fixed_sign"]
    report["max_drawdown_bp"] = _drawdown(agent_values)
    costs = _cost_summary(rows)
    if costs is not None:
        report["costs"] = costs
        if all("spread_bp" in row for row in rows):
            report["costs"]["spread_bp_mean"] = round(statistics.fmean(_num(row, "spread_bp") for row in rows), 4)
            report["costs"]["spread_note"] = "Quoted bid-ask width. The net return already includes the book walk, so this is not added again."
    violations = sum(1 for row in rows if row.get("risk_control_violation") is True)
    report["risk_control_violation_rate"] = round(violations / len(rows), 4)
    exposure = _exposure_block(rows)
    if exposure is not None:
        report["exposure"] = exposure
    report["selection"] = _selection(agent_values)
    report["note"] = "Observed paper comparison on the registered window. This is not a profitability claim."
    return report


def _paired_comparison(rows: list[dict], baseline: str) -> dict:
    differences = [_num(row, "agent_bp") - _num(row, f"{baseline}_bp") for row in rows]
    return {
        "mean": round(statistics.fmean(differences), 4),
        "bootstrap_95": _bootstrap(differences),
    }


def _cost_summary(rows: list[dict]) -> dict | None:
    if not all(all(key in row for key in COST_KEYS) for row in rows):
        return None
    return {
        "fees_bp_mean": round(statistics.fmean(_num(row, "fees_bp") for row in rows), 4),
        "funding_bp_mean": round(statistics.fmean(_num(row, "funding_bp") for row in rows), 4),
        "slippage_bp_mean": round(statistics.fmean(_num(row, "slippage_bp") for row in rows), 4),
    }


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


def _exposure_block(rows: list[dict]) -> dict | None:
    """Hold time over the span from the first open to the last close. Missing hours are omitted, not zero."""
    if any("hold_hours" not in row for row in rows):
        return None
    spans = []
    for row in rows:
        end = _parse_iso(row.get("closed_at"))
        try:
            hold = float(row["hold_hours"])
        except (TypeError, ValueError):
            return None
        if end is None or hold < 0 or hold != hold:
            return None
        spans.append((end - timedelta(hours=hold), end, hold))
    window = (max(end for _start, end, _hold in spans) - min(start for start, _end, _hold in spans)).total_seconds() / 3600
    if window <= 0:
        return None
    held = sum(hold for _start, _end, hold in spans)
    block = {
        "hold_hours": round(held, 4),
        "window_hours": round(window, 4),
        "exposure": round(exposure_fraction(held, window), 4),
    }
    if all("notional_usdt" in row for row in rows):
        try:
            notional = sum(float(row["notional_usdt"]) for row in rows)
        except (TypeError, ValueError):
            return block
        if notional == notional and notional >= 0:
            block["turnover_per_hour"] = round(turnover_rate(notional, window), 4)
    return block


def _selection(values: list[float]) -> dict:
    """One preregistered comparison. The benchmark Sharpe is 0, and Bonferroni uses k = 1."""
    raw = sharpe_ratio(values)
    moments = moment_skew_kurtosis(values)
    deflated = None if raw is None or moments is None else deflated_sharpe(raw, len(values), 1, moments[0], moments[1])
    probability = one_sided_bootstrap_p(values)
    return {
        "n_trials": 1,
        "deflated_sharpe": None if deflated is None else round(deflated, 4),
        "bootstrap_p_mean_gt_0": round(probability, 4),
        "bonferroni_p": round(bonferroni(probability, 1), 4),
    }


def _parse_iso(value) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _complete(row: dict) -> bool:
    return all(f"{name}_bp" in row for name in ARMS)


def _num(row: dict, key: str) -> float:
    return float(row[key])


# Additive helpers for H-BR-1. They do not change evaluate().
# Euler-Mascheroni constant used by Bailey & Lopez de Prado (2014), equation for E[max SR].
_EULER = 0.57721566490153286060651209008240243


def per_trade_sharpe(values: list[float]) -> float | None:
    """Mean / sample standard deviation, rounded to 4 decimals. Not annualized."""
    raw = sharpe_ratio(values)
    if raw is None:
        return None
    return round(raw, 4)


def sharpe_ratio(values: list[float]) -> float | None:
    """Unrounded per-trade Sharpe. None when n < 2 or the sample deviation is 0."""
    if len(values) < 2:
        return None
    deviation = statistics.stdev(values)
    if deviation == 0:
        return None
    return statistics.fmean(values) / deviation


def max_drawdown(cumulative: list[float]) -> float:
    """Peak-to-trough decline of an already-cumulative series.

    The series is not differenced. An empty series, or a series that never
    falls below its running peak, has drawdown 0. Callers who want the
    drawdown of a trade list from a flat start should prepend 0.
    """
    if not cumulative:
        return 0.0
    peak = cumulative[0]
    worst = 0.0
    for value in cumulative:
        if value > peak:
            peak = value
        drop = peak - value
        if drop > worst:
            worst = drop
    return round(worst, 4)


def exposure_fraction(hours_in_position: float, hours_available: float) -> float:
    """Fraction of available hours that are in a position."""
    if hours_available <= 0:
        raise ValueError("hours_available must be positive")
    return hours_in_position / hours_available


def turnover_rate(notional_traded: float, hours_available: float) -> float:
    """Notional traded per available hour. The caller defines one round trip's notional."""
    if hours_available <= 0:
        raise ValueError("hours_available must be positive")
    return notional_traded / hours_available


def bonferroni(p: float, k: int) -> float:
    """Family-wise adjustment min(1, p * k). k is the number of variants, not a p-value."""
    if k < 1:
        raise ValueError("k must be >= 1")
    if p < 0:
        raise ValueError("p must be >= 0")
    return min(1.0, float(p) * int(k))


def moment_skew_kurtosis(values: list[float]) -> tuple[float, float] | None:
    """Pearson skew and kurtosis with divisor n. A normal distribution has kurtosis 3.

    Returns None when n < 2 or the second moment is 0.
    """
    n = len(values)
    if n < 2:
        return None
    mean = statistics.fmean(values)
    m2 = sum((value - mean) ** 2 for value in values) / n
    if m2 == 0:
        return None
    m3 = sum((value - mean) ** 3 for value in values) / n
    m4 = sum((value - mean) ** 4 for value in values) / n
    skew = m3 / (m2 ** 1.5)
    kurtosis = m4 / (m2 ** 2)
    return skew, kurtosis


def deflated_sharpe(sharpe: float, n: int, n_trials: int, skew: float, kurtosis: float) -> float | None:
    """Bailey & Lopez de Prado (2014) deflated Sharpe ratio, as a probability.

    Kurtosis is the Pearson fourth moment (normal = 3). For a single trial,
    the selection benchmark SR* is 0. For N > 1, the cross-trial variance is
    the null sampling variance 1/(n-1): this helper has no separate variance
    argument, and that is the variance of the Sharpe estimator when the true
    Sharpe is 0. Returns None when n < 2 or the non-normality term is not positive.
    """
    if n < 2 or n_trials < 1:
        return None
    if n_trials == 1:
        sr_star = 0.0
    else:
        scale = (1.0 / (n - 1)) ** 0.5
        normal = statistics.NormalDist()
        z1 = normal.inv_cdf(1.0 - 1.0 / n_trials)
        z2 = normal.inv_cdf(1.0 - 1.0 / (n_trials * math.e))
        sr_star = scale * ((1.0 - _EULER) * z1 + _EULER * z2)
    inside = 1.0 - skew * sharpe + ((kurtosis - 1.0) / 4.0) * sharpe * sharpe
    if inside <= 0.0:
        return None
    z = ((sharpe - sr_star) * math.sqrt(n - 1)) / math.sqrt(inside)
    return statistics.NormalDist().cdf(z)


def one_sided_bootstrap_p(values: list[float], *, draws: int = BOOTSTRAP_DRAWS, seed: int = BOOTSTRAP_SEED) -> float:
    """Conservative one-sided bootstrap p for the alternative that the mean is > 0.

    p = (1 + count of resampled means that are <= 0) / (draws + 1).
    """
    if draws < 1:
        raise ValueError("draws must be >= 1")
    if not values:
        return 1.0
    rng = random.Random(seed)
    width = len(values)
    nonpositive = 0
    for _draw in range(draws):
        sample_mean = statistics.fmean(values[rng.randrange(width)] for _item in range(width))
        if sample_mean <= 0:
            nonpositive += 1
    return (1 + nonpositive) / (draws + 1)
