"""H-BR-1 beta-adjusted residual shock. Pure functions only.

This module does not call the network, does not call an LLM, and does not
write the S-A ledger. The frozen rules are HISTORY/BR1_PREREG.md.
"""

from __future__ import annotations

import hashlib
import math
import statistics
from decimal import Decimal

HOUR_MS = 3_600_000
WINDOW = 168
MIN_VALID_BARS = 150
Z_THRESHOLD = 3.0
HOLD_HOURS = 4
MIN_SCORED = 30
PRIMARY_HALF_SPREAD_BP = 1
HALF_SPREADS_BP = (0, 1, 2)
N_VARIANTS = 4
STRATEGY_ID = "H-BR-1"
BENCHMARK = "QQQUSDT"
UNIVERSE = (
    "NVDAUSDT",
    "TSLAUSDT",
    "AAPLUSDT",
    "AMZNUSDT",
    "MSFTUSDT",
    "METAUSDT",
    "GOOGLUSDT",
    "COINUSDT",
    "MSTRUSDT",
)
VARIANT_ORDER = (
    "continuation_unhedged",
    "reversal_unhedged",
    "continuation_hedged",
    "reversal_hedged",
)


def _decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str):
        return Decimal(value)
    return Decimal(str(value))


def _positive(value) -> bool:
    try:
        number = _decimal(value)
    except Exception:
        return False
    return number.is_finite() and number > 0


def close_to_close_return(previous_close, close) -> float | None:
    """Simple return. None when either close is not strictly positive."""
    if not _positive(previous_close) or not _positive(close):
        return None
    ratio = _decimal(close) / _decimal(previous_close) - 1
    return float(ratio)


def adjacent_close_returns(bars: list[dict]) -> dict[int, float]:
    """Map each bar's open_ms to its close-to-close return when the previous hour exists."""
    by_time = {}
    for bar in bars:
        opened = int(bar["open_ms"])
        if opened in by_time:
            if str(by_time[opened]["close"]) != str(bar["close"]):
                raise ValueError(f"conflicting close at {opened}")
            continue
        by_time[opened] = bar
    returns = {}
    for opened, bar in by_time.items():
        previous = by_time.get(opened - HOUR_MS)
        if previous is None:
            continue
        value = close_to_close_return(previous["close"], bar["close"])
        if value is None:
            continue
        returns[opened] = value
    return returns


def fit_ols_beta(xs: list[float], ys: list[float]) -> float | None:
    """OLS slope with intercept. None when the regressor has zero variance."""
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x == 0:
        return None
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    return cov / var_x


def residual_sigma(xs: list[float], ys: list[float], beta: float) -> float | None:
    """Sample stdev of y - beta * x. The intercept is not removed."""
    if len(xs) < 2:
        return None
    residuals = [y - beta * x for x, y in zip(xs, ys)]
    sigma = statistics.stdev(residuals)
    if math.isnan(sigma):
        return None
    return sigma


def contiguous_prior(return_times: set[int], signal_open_ms: int, window: int) -> list[int]:
    """Up to `window` return timestamps ending at signal-1h. A gap stops the walk."""
    found = []
    cursor = int(signal_open_ms) - HOUR_MS
    while len(found) < int(window) and cursor in return_times:
        found.append(cursor)
        cursor -= HOUR_MS
    found.reverse()
    return found


def _window_stats(
    stock_returns: dict[int, float],
    bench_returns: dict[int, float],
    signal_open_ms: int,
    *,
    window: int,
    min_bars: int,
) -> dict | None:
    shared = set(stock_returns) & set(bench_returns)
    signal_open_ms = int(signal_open_ms)
    if signal_open_ms not in shared:
        return None
    times = contiguous_prior(shared, signal_open_ms, window)
    if len(times) < min_bars:
        return None
    xs = [bench_returns[ts] for ts in times]
    ys = [stock_returns[ts] for ts in times]
    beta = fit_ols_beta(xs, ys)
    if beta is None:
        return None
    sigma = residual_sigma(xs, ys, beta)
    residual = stock_returns[signal_open_ms] - beta * bench_returns[signal_open_ms]
    return {
        "signal_open_ms": signal_open_ms,
        "window_start_ms": times[0],
        "window_end_ms": times[-1],
        "window_n": len(times),
        "beta": beta,
        "sigma": sigma,
        "residual": residual,
        "window_times": times,
    }


def lagged_window(
    stock_bars: list[dict],
    bench_bars: list[dict],
    signal_open_ms: int,
    *,
    window: int = WINDOW,
    min_bars: int = MIN_VALID_BARS,
) -> dict | None:
    """Beta, sigma, and the current residual. The window excludes the signal hour."""
    if min_bars < 2:
        raise ValueError("min_bars must be at least 2")
    return _window_stats(
        adjacent_close_returns(stock_bars),
        adjacent_close_returns(bench_bars),
        signal_open_ms,
        window=window,
        min_bars=min_bars,
    )


def assert_no_lookahead(shock: dict) -> None:
    """Beta/sigma end at t-1. Entry is the next bar's open, after the signal bar opens."""
    signal = int(shock["signal_open_ms"])
    close_ms = signal + HOUR_MS
    if int(shock["signal_close_ms"]) != close_ms:
        raise AssertionError("signal close must be one hour after the signal open")
    if int(shock["window_end_ms"]) != signal - HOUR_MS:
        raise AssertionError("beta/sigma window must end at t-1")
    if int(shock["window_start_ms"]) != int(shock["window_end_ms"]) - (int(shock["window_n"]) - 1) * HOUR_MS:
        raise AssertionError("beta/sigma window is not a contiguous hour run")
    if signal in set(shock.get("window_times") or []):
        raise AssertionError("signal hour leaked into the beta window")
    if int(shock["entry_open_ms"]) != close_ms:
        raise AssertionError("entry must be the open of bar t+1")
    if int(shock["entry_open_ms"]) <= signal:
        raise AssertionError("entry must be strictly after the signal bar opens")
    hold = int(shock["hold_hours"])
    if int(shock["exit_open_ms"]) != int(shock["entry_open_ms"]) + hold * HOUR_MS:
        raise AssertionError("exit must be the open H hours after entry")
    if shock.get("entry_price_field") not in (None, "open"):
        raise AssertionError("entry price must be the next bar's open")


def detect_shocks(
    stock_bars: list[dict],
    bench_bars: list[dict],
    *,
    window: int = WINDOW,
    min_bars: int = MIN_VALID_BARS,
    z_threshold: float = Z_THRESHOLD,
    hold_hours: int = HOLD_HOURS,
) -> list[dict]:
    """Shocks where |residual| / lagged sigma clears the threshold. No network."""
    stock_returns = adjacent_close_returns(stock_bars)
    bench_returns = adjacent_close_returns(bench_bars)
    shared = set(stock_returns) & set(bench_returns)
    shocks = []
    for signal_open_ms in sorted(shared):
        stats = _window_stats(
            stock_returns,
            bench_returns,
            signal_open_ms,
            window=window,
            min_bars=min_bars,
        )
        if stats is None or stats["sigma"] is None or stats["sigma"] == 0:
            continue
        residual = stats["residual"]
        sigma = stats["sigma"]
        z_value = abs(residual) / sigma
        if z_value < float(z_threshold):
            continue
        shock = {
            "signal_open_ms": signal_open_ms,
            "signal_close_ms": signal_open_ms + HOUR_MS,
            "window_start_ms": stats["window_start_ms"],
            "window_end_ms": stats["window_end_ms"],
            "window_n": stats["window_n"],
            "window_times": stats["window_times"],
            "beta": stats["beta"],
            "sigma": sigma,
            "residual": residual,
            "z": z_value,
            "entry_open_ms": signal_open_ms + HOUR_MS,
            "exit_open_ms": signal_open_ms + HOUR_MS + int(hold_hours) * HOUR_MS,
            "hold_hours": int(hold_hours),
            "entry_price_field": "open",
            "strategy_id": STRATEGY_ID,
        }
        assert_no_lookahead(shock)
        shocks.append(shock)
    return shocks


def random_direction(symbol: str, signal_open_ms: int) -> int:
    """Even first SHA-256 byte is long. The seed string is frozen in the preregistration."""
    digest = hashlib.sha256(f"H-BR-1|{symbol}|{int(signal_open_ms)}".encode()).digest()
    return 1 if digest[0] % 2 == 0 else -1


def direction_for(rule: str, residual: float, symbol: str, signal_open_ms: int) -> int:
    """+1 long stock, -1 short stock, 0 no-trade."""
    if rule == "no_trade":
        return 0
    if rule == "random":
        return random_direction(symbol, signal_open_ms)
    sign = 1 if residual > 0 else -1
    if rule == "continuation":
        return sign
    if rule == "reversal":
        return -sign
    raise ValueError(f"unknown direction rule: {rule}")


def funding_cost_bp(direction: int, stock_rate_sum, *, beta: float = 0.0, bench_rate_sum=0, hedged: bool = False):
    """Positive means the position pays. A long pays a positive stock funding rate."""
    stock_cost = _decimal(direction) * _decimal(stock_rate_sum) * Decimal(10_000)
    if not hedged:
        return stock_cost
    bench_cost = _decimal(-beta) * _decimal(direction) * _decimal(bench_rate_sum) * Decimal(10_000)
    return stock_cost + bench_cost


def fee_cost_bp(taker_fee_stock, *, taker_fee_bench=0, beta: float = 0.0, hedged: bool = False) -> Decimal:
    stock = _decimal(taker_fee_stock) * 2 * Decimal(10_000)
    if not hedged:
        return stock
    bench = _decimal(taker_fee_bench) * 2 * Decimal(10_000) * abs(_decimal(str(beta)))
    return stock + bench


def spread_cost_bp(half_spread_bp: float, *, beta: float = 0.0, hedged: bool = False) -> Decimal:
    per_side = _decimal(str(half_spread_bp))
    legs = Decimal(1) if not hedged else Decimal(1) + abs(_decimal(str(beta)))
    return per_side * 2 * legs


def net_from_parts(gross_bp: Decimal, fee_bp: Decimal, spread_bp: Decimal, funding_bp: Decimal) -> Decimal:
    """gross - round-trip fee - total spread - funding cost."""
    return gross_bp - fee_bp - spread_bp - funding_bp


def gross_bp(direction: int, stock_return, *, qqq_return=0, beta: float = 0.0, hedged: bool = False) -> Decimal:
    stock = _decimal(stock_return)
    if hedged:
        hedged_return = stock - _decimal(str(beta)) * _decimal(qqq_return)
        return _decimal(direction) * hedged_return * Decimal(10_000)
    return _decimal(direction) * stock * Decimal(10_000)


def _index_bars(bars: list[dict]) -> dict[int, dict]:
    indexed = {}
    for bar in bars:
        opened = int(bar["open_ms"])
        if opened in indexed and str(indexed[opened]["open"]) != str(bar["open"]):
            raise ValueError(f"conflicting open at {opened}")
        indexed[opened] = bar
    return indexed


def _open_return(indexed: dict[int, dict], entry_ms: int, exit_ms: int):
    entry = indexed.get(entry_ms)
    exit_bar = indexed.get(exit_ms)
    if entry is None or exit_bar is None:
        return None
    if not _positive(entry["open"]) or not _positive(exit_bar["open"]):
        return None
    return _decimal(exit_bar["open"]) / _decimal(entry["open"]) - 1, entry["open"]


def hole_hits_hold(gap_start: int, gap_end: int, entry_ms: int, exit_ms: int) -> bool:
    """True when an open hole could hide a settlement the hold would cross."""
    if gap_end <= entry_ms or gap_start >= exit_ms:
        return False
    return True


def funding_status(settlements: list[dict], entry_ms: int, exit_ms: int, *, coverage_complete: bool) -> dict:
    """Crossed rates, or missing. An empty crossed list is a real zero, not a fill."""
    if not coverage_complete or not settlements:
        return {"missing": True, "rates": None, "reason": "coverage"}
    indexed = {}
    for row in settlements:
        stamp = int(row["time_ms"])
        if stamp in indexed and str(indexed[stamp]["rate"]) != str(row["rate"]):
            raise ValueError(f"conflicting funding rate at {stamp}")
        indexed[stamp] = row
    ordered = sorted(indexed.values(), key=lambda row: int(row["time_ms"]))
    times = [int(row["time_ms"]) for row in ordered]
    coverage_start = times[0]
    coverage_end = times[-1]
    if int(entry_ms) < coverage_start or int(exit_ms) > coverage_end:
        return {"missing": True, "rates": None, "reason": "outside_coverage"}
    gaps = [right - left for left, right in zip(times, times[1:]) if right > left]
    if len(gaps) >= 2:
        median_gap = statistics.median(gaps)
        limit = 1.5 * median_gap
        for left, right in zip(times, times[1:]):
            if right - left > limit and hole_hits_hold(left, right, int(entry_ms), int(exit_ms)):
                return {"missing": True, "rates": None, "reason": "hole"}
    rates = []
    for row in ordered:
        stamp = int(row["time_ms"])
        if int(entry_ms) < stamp <= int(exit_ms):
            rate = row["rate"]
            if not _decimal(rate).is_finite():
                return {"missing": True, "rates": None, "reason": "rate"}
            rates.append(rate)
    return {"missing": False, "rates": rates, "reason": "ok"}


def _rate_sum(rates: list) -> Decimal:
    total = Decimal(0)
    for rate in rates:
        total += _decimal(rate)
    return total


def price_trade(
    shock: dict,
    stock_bars: list[dict],
    bench_bars: list[dict],
    *,
    symbol: str,
    rule: str,
    hedged: bool,
    half_spread_bp: float,
    taker_fee_stock,
    taker_fee_bench,
    stock_settlements: list[dict],
    bench_settlements: list[dict],
    stock_coverage_complete: bool,
    bench_coverage_complete: bool,
) -> dict | None:
    """One position, or None when the entry or exit open is missing.

    funding_missing True excludes the trade from the scored sample. Funding is
    not stored as zero in that case.
    """
    assert_no_lookahead(shock)
    entry_ms = int(shock["entry_open_ms"])
    exit_ms = int(shock["exit_open_ms"])
    stock = _index_bars(stock_bars)
    bench = _index_bars(bench_bars)
    stock_leg = _open_return(stock, entry_ms, exit_ms)
    if stock_leg is None:
        return None
    stock_return, entry_open = stock_leg
    qqq_return = Decimal(0)
    if hedged:
        bench_leg = _open_return(bench, entry_ms, exit_ms)
        if bench_leg is None:
            return None
        qqq_return = bench_leg[0]
    direction = direction_for(rule, float(shock["residual"]), symbol, int(shock["signal_open_ms"]))
    stock_funding = funding_status(
        stock_settlements, entry_ms, exit_ms, coverage_complete=stock_coverage_complete,
    )
    bench_funding = {"missing": False, "rates": [], "reason": "unused"}
    if hedged:
        bench_funding = funding_status(
            bench_settlements, entry_ms, exit_ms, coverage_complete=bench_coverage_complete,
        )
    missing = bool(stock_funding["missing"] or (hedged and bench_funding["missing"]))
    beta = float(shock["beta"])
    record = {
        "symbol": symbol,
        "signal_open_ms": int(shock["signal_open_ms"]),
        "window_end_ms": int(shock["window_end_ms"]),
        "entry_open_ms": entry_ms,
        "exit_open_ms": exit_ms,
        "beta": beta,
        "residual": float(shock["residual"]),
        "sigma": None if shock["sigma"] is None else float(shock["sigma"]),
        "z": float(shock["z"]),
        "stock_return": stock_return,
        "qqq_return": qqq_return,
        "direction": direction,
        "hedged": bool(hedged),
        "half_spread_bp": float(half_spread_bp),
        "taker_fee_stock": str(_decimal(taker_fee_stock)),
        "taker_fee_bench": str(_decimal(taker_fee_bench)),
        "rule": rule,
        "hold_hours": int(shock["hold_hours"]),
        "entry_price_field": "open",
        "entry_open": str(entry_open),
        "funding_missing": missing,
        "strategy_id": STRATEGY_ID,
    }
    if direction == 0:
        record.update({
            "gross_bp": 0.0,
            "fee_bp": 0.0,
            "spread_bp": 0.0,
            "funding_bp": 0.0,
            "net_bp": 0.0,
            "funding_missing": False,
        })
        return record
    if missing:
        record.update({"gross_bp": None, "fee_bp": None, "spread_bp": None, "funding_bp": None, "net_bp": None})
        return record
    stock_sum = _rate_sum(stock_funding["rates"])
    bench_sum = _rate_sum(bench_funding["rates"]) if hedged else Decimal(0)
    gross = gross_bp(direction, stock_return, qqq_return=qqq_return, beta=beta, hedged=hedged)
    fee = fee_cost_bp(taker_fee_stock, taker_fee_bench=taker_fee_bench, beta=beta, hedged=hedged)
    spread = spread_cost_bp(half_spread_bp, beta=beta, hedged=hedged)
    funding = funding_cost_bp(direction, stock_sum, beta=beta, bench_rate_sum=bench_sum, hedged=hedged)
    net = net_from_parts(gross, fee, spread, funding)
    record.update({
        "gross_bp": float(gross),
        "fee_bp": float(fee),
        "spread_bp": float(spread),
        "funding_bp": float(funding),
        "net_bp": float(net),
        "stock_funding_rate_sum": stock_sum,
        "qqq_funding_rate_sum": bench_sum,
    })
    return record


def simulate_symbol(
    shocks: list[dict],
    stock_bars: list[dict],
    bench_bars: list[dict],
    *,
    symbol: str,
    rule: str,
    hedged: bool,
    half_spread_bp: float,
    taker_fee_stock,
    taker_fee_bench,
    stock_settlements: list[dict],
    bench_settlements: list[dict],
    stock_coverage_complete: bool,
    bench_coverage_complete: bool,
) -> dict:
    """Take non-overlapping positions in signal order. Missing funding is excluded, not zeroed."""
    trades = []
    overlap_skipped = 0
    unfilled = 0
    last_exit = None
    for shock in sorted(shocks, key=lambda row: int(row["signal_open_ms"])):
        if last_exit is not None and int(shock["entry_open_ms"]) < last_exit:
            overlap_skipped += 1
            continue
        trade = price_trade(
            shock,
            stock_bars,
            bench_bars,
            symbol=symbol,
            rule=rule,
            hedged=hedged,
            half_spread_bp=half_spread_bp,
            taker_fee_stock=taker_fee_stock,
            taker_fee_bench=taker_fee_bench,
            stock_settlements=stock_settlements,
            bench_settlements=bench_settlements,
            stock_coverage_complete=stock_coverage_complete,
            bench_coverage_complete=bench_coverage_complete,
        )
        if trade is None:
            unfilled += 1
            continue
        trades.append(trade)
        last_exit = int(shock["exit_open_ms"])
    scored = [trade for trade in trades if not trade["funding_missing"]]
    excluded = len(trades) - len(scored)
    return {
        "trades": trades,
        "scored": scored,
        "overlap_skipped": overlap_skipped,
        "unfilled": unfilled,
        "excluded_missing_funding": excluded,
    }


def chronological_splits(timestamps: list[int]) -> dict[str, list[int]]:
    """Train 50%, validation 25%, holdout the rest, by index of sorted unique timestamps."""
    stamps = sorted({int(ts) for ts in timestamps})
    n = len(stamps)
    i50 = n // 2
    i75 = i50 + n // 4
    return {
        "train": stamps[:i50],
        "validation": stamps[i50:i75],
        "holdout": stamps[i75:],
    }


def split_of(timestamp: int, split_sets: dict[str, set[int]]) -> str | None:
    for name in ("train", "validation", "holdout"):
        if int(timestamp) in split_sets[name]:
            return name
    return None


def trade_split(trade: dict, split_sets: dict[str, set[int]]) -> str | None:
    """Both the signal bar and the exit bar must sit in the same split."""
    signal_split = split_of(trade["signal_open_ms"], split_sets)
    exit_split = split_of(trade["exit_open_ms"], split_sets)
    if signal_split is None or signal_split != exit_split:
        return None
    return signal_split


def variant_name(rule: str, hedged: bool) -> str:
    name = f"{rule}_{'hedged' if hedged else 'unhedged'}"
    if name not in VARIANT_ORDER:
        raise ValueError(name)
    return name


def parse_variant(name: str) -> tuple[str, bool]:
    if name not in VARIANT_ORDER:
        raise ValueError(name)
    rule, hedge = name.rsplit("_", 1)
    return rule, hedge == "hedged"


def select_variant(validation_rows: list[dict]) -> str | None:
    """Highest validation mean at 1 bp half-spread, among variants with n >= 30."""
    order = {name: index for index, name in enumerate(VARIANT_ORDER)}
    eligible = [
        row for row in validation_rows
        if int(row["n"]) >= MIN_SCORED and float(row["half_spread_bp"]) == float(PRIMARY_HALF_SPREAD_BP)
    ]
    if not eligible:
        return None

    def sort_key(row: dict):
        sharpe = row["sharpe"]
        sharpe_rank = float("-inf") if sharpe is None else float(sharpe)
        return (float(row["mean_net_bp"]), sharpe_rank, -order[row["variant"]])

    return max(eligible, key=sort_key)["variant"]


def preregistered_verdict(mean_net_bp: float | None, bonferroni_p: float | None, n: int, *, selected: bool) -> str:
    """promising, rejected, or insufficient. Thresholds are the frozen ones."""
    if not selected or n < MIN_SCORED or mean_net_bp is None or bonferroni_p is None:
        return "insufficient"
    if float(mean_net_bp) > 0 and float(bonferroni_p) < 0.05:
        return "promising"
    return "rejected"


def reprice_direction(trade: dict, rule: str, *, symbol: str | None = None) -> dict | None:
    """Same event, hedge, spread, and funding. A new direction. None if funding was missing."""
    if trade["funding_missing"]:
        return None
    symbol = symbol or trade["symbol"]
    direction = direction_for(rule, float(trade["residual"]), symbol, int(trade["signal_open_ms"]))
    hedged = bool(trade["hedged"])
    beta = float(trade["beta"])
    if direction == 0:
        return {**trade, "rule": rule, "direction": 0, "gross_bp": 0.0, "fee_bp": 0.0, "spread_bp": 0.0, "funding_bp": 0.0, "net_bp": 0.0}
    gross = gross_bp(direction, trade["stock_return"], qqq_return=trade["qqq_return"], beta=beta, hedged=hedged)
    fee = fee_cost_bp(trade["taker_fee_stock"], taker_fee_bench=trade["taker_fee_bench"], beta=beta, hedged=hedged)
    spread = spread_cost_bp(trade["half_spread_bp"], beta=beta, hedged=hedged)
    funding = funding_cost_bp(
        direction,
        trade["stock_funding_rate_sum"],
        beta=beta,
        bench_rate_sum=trade.get("qqq_funding_rate_sum") or 0,
        hedged=hedged,
    )
    net = net_from_parts(gross, fee, spread, funding)
    return {
        **trade,
        "rule": rule,
        "direction": direction,
        "gross_bp": float(gross),
        "fee_bp": float(fee),
        "spread_bp": float(spread),
        "funding_bp": float(funding),
        "net_bp": float(net),
    }
