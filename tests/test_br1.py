import math
import statistics
from decimal import Decimal

from aftermath_api.metrics import MIN_PAIRS
from aftermath_api.strategies.br1 import (
    HOLD_HOURS,
    HOUR_MS,
    MIN_SCORED,
    MIN_VALID_BARS,
    VARIANT_ORDER,
    WINDOW,
    Z_THRESHOLD,
    contiguous_prior,
    detect_shocks,
    funding_cost_bp,
    funding_status,
    lagged_window,
    net_from_parts,
    price_trade,
    preregistered_verdict,
    random_direction,
    select_variant,
    chronological_splits,
    simulate_symbol,
)

H = HOUR_MS


def _bar(hour: int, open_px, close_px) -> dict:
    return {"open_ms": hour * H, "open": str(open_px), "close": str(close_px)}


def _series(closes: list, opens=None) -> list[dict]:
    rows = []
    for hour, close in enumerate(closes):
        open_px = close if opens is None else opens[hour]
        rows.append(_bar(hour, open_px, close))
    return rows


def _shock(**overrides) -> dict:
    shock = {
        "signal_open_ms": 0,
        "signal_close_ms": H,
        "window_start_ms": -3 * H,
        "window_end_ms": -H,
        "window_n": 3,
        "window_times": [-3 * H, -2 * H, -H],
        "beta": 1.0,
        "sigma": 1.0,
        "residual": 1.0,
        "z": 3.0,
        "entry_open_ms": H,
        "exit_open_ms": 5 * H,
        "hold_hours": 4,
        "entry_price_field": "open",
    }
    shock.update(overrides)
    return shock


def test_frozen_thresholds_match_the_preregistration():
    assert WINDOW == 168
    assert MIN_VALID_BARS == 150
    assert Z_THRESHOLD == 3.0
    assert HOLD_HOURS == 4
    assert MIN_SCORED == 30
    assert MIN_SCORED == MIN_PAIRS
    assert len(VARIANT_ORDER) == 4


def test_beta_and_residual_on_a_five_bar_toy_series():
    # Five closes. Returns at hours 1, 2, 3, 4.
    # QQQ: 100, 200, 600, 2400, 4800 -> returns 1, 2, 3, 1.
    # Stock: 10, 30, 150, 1050, 5250 -> returns 2, 4, 6, 4.
    # Window at hour 4 uses hours 1, 2, 3 only.
    # mean_x = 2, mean_y = 4.
    # cov = (1-2)*(2-4) + (2-2)*(4-4) + (3-2)*(6-4) = 2 + 0 + 2 = 4.
    # var_x = 1 + 0 + 1 = 2. beta = 4/2 = 2.
    # Residual at hour 4 = 4 - 2 * 1 = 2.
    # Window residuals are 0, 0, 0, so sigma is 0 and this is not a shock.
    qqq = _series([100, 200, 600, 2400, 4800])
    stock = _series([10, 30, 150, 1050, 5250])
    stats = lagged_window(stock, qqq, 4 * H, window=3, min_bars=3)
    assert stats["beta"] == 2.0
    assert stats["residual"] == 2.0
    assert stats["sigma"] == 0.0
    assert stats["window_end_ms"] == 3 * H
    assert 4 * H not in stats["window_times"]
    assert detect_shocks(stock, qqq, window=3, min_bars=3, z_threshold=3.0) == []


def test_shock_sigma_excludes_the_current_bar():
    # QQQ returns 1, 2, 3, 1. Stock returns 1, 2, 6, 10.
    # Window hours 1..3: x = [1, 2, 3], y = [1, 2, 6].
    # mean_x = 2, mean_y = 3. cov = 2 + 0 + 3 = 5. var_x = 2. beta = 2.5.
    # Residuals y - 2.5x = [-1.5, -3, -1.5].
    # Sample variance = (0.25 + 1 + 0.25) / 2 = 0.75. sigma = sqrt(0.75).
    # Current residual = 10 - 2.5 * 1 = 7.5, and it is not in sigma.
    qqq = _series([100, 200, 600, 2400, 4800])
    stock = _series([10, 20, 60, 420, 4620])
    stats = lagged_window(stock, qqq, 4 * H, window=3, min_bars=3)
    hand_sigma = math.sqrt(0.75)
    included = statistics.stdev([-1.5, -3.0, -1.5, 7.5])
    assert stats["beta"] == 2.5
    assert stats["sigma"] == hand_sigma
    assert stats["residual"] == 7.5
    assert stats["sigma"] != included
    assert stats["window_end_ms"] == 3 * H
    moved = _series([10, 20, 60, 420, 4200])
    moved_stats = lagged_window(moved, qqq, 4 * H, window=3, min_bars=3)
    assert moved_stats["beta"] == stats["beta"]
    assert moved_stats["sigma"] == stats["sigma"]
    # 4200/420 - 1 = 9, and 9 - 2.5 * 1 = 6.5. Beta and sigma stay on the lagged window.
    assert moved_stats["residual"] == 6.5
    shocks = detect_shocks(stock, qqq, window=3, min_bars=3, z_threshold=3.0)
    assert len(shocks) == 1
    assert shocks[0]["entry_open_ms"] == shocks[0]["signal_close_ms"]
    assert shocks[0]["entry_open_ms"] > shocks[0]["signal_open_ms"]
    assert shocks[0]["entry_price_field"] == "open"


def test_a_gap_breaks_the_window():
    full_times = {hour * H for hour in range(1, 11)}
    # Missing bar 5 deletes the returns at hours 5 and 6.
    gapped_times = {hour * H for hour in (1, 2, 3, 4, 7, 8, 9, 10)}
    assert contiguous_prior(full_times, 10 * H, 6) == [hour * H for hour in range(4, 10)]
    assert contiguous_prior(gapped_times, 10 * H, 6) == [7 * H, 8 * H, 9 * H]
    closes = [100 + hour for hour in range(11)]
    full = _series(closes)
    gapped_hours = [0, 1, 2, 3, 4, 6, 7, 8, 9, 10]
    gapped = [_bar(hour, 100 + hour, 100 + hour) for hour in gapped_hours]
    # Four pre-gap returns exist, but the contiguous run into the signal is only 3.
    assert lagged_window(gapped, gapped, 10 * H, window=6, min_bars=4) is None
    whole = lagged_window(full, full, 10 * H, window=6, min_bars=4)
    assert whole is not None and whole["window_n"] == 6
    short = lagged_window(gapped, gapped, 10 * H, window=6, min_bars=3)
    assert short["window_n"] == 3
    assert short["window_start_ms"] == 7 * H
    assert short["window_end_ms"] == 9 * H
    assert 1 * H not in short["window_times"]


def test_trade_net_bp_matches_the_hand_calculation():
    # gross = (101/100 - 1) * 1e4 = 100 bp
    # fee = 2 * 0.0006 * 1e4 = 12 bp
    # spread = 2 * 1 bp half-spread = 2 bp
    # funding = 0.0001 * 1e4 = 1 bp for a long
    # net = 100 - 12 - 2 - 1 = 85 bp
    assert net_from_parts(Decimal(100), Decimal(12), Decimal(2), Decimal(1)) == Decimal(85)
    # Short receives the positive funding rate, so the funding cost is -1.
    # net = -100 - 12 - 2 - (-1) = -113 bp
    assert net_from_parts(Decimal(-100), Decimal(12), Decimal(2), Decimal(-1)) == Decimal(-113)
    assert funding_cost_bp(1, "0.0001") == Decimal("1")
    assert funding_cost_bp(-1, "0.0001") == Decimal("-1")

    qqq = [
        _bar(0, 100, 100),
        _bar(1, 200, 200),
        _bar(2, 600, 600),
        _bar(3, 2400, 2400),
        _bar(4, 2400, 2400),
        _bar(5, 2400, 2400),
        _bar(9, 2400, 2400),
    ]
    stock = [
        _bar(0, 10, 10),
        _bar(1, 20, 20),
        _bar(2, 60, 60),
        _bar(3, 420, 420),
        _bar(4, 1680, 1680),
        _bar(5, 100, 100),
        _bar(9, 101, 101),
    ]
    settlements = [
        {"time_ms": 0, "rate": "0.0001"},
        {"time_ms": 7 * H, "rate": "0.0001"},
        {"time_ms": 14 * H, "rate": "0.0001"},
    ]
    common = dict(
        stock_bars=stock,
        bench_bars=qqq,
        symbol="NVDAUSDT",
        hedged=False,
        half_spread_bp=1,
        taker_fee_stock="0.0006",
        taker_fee_bench="0.0006",
        stock_settlements=settlements,
        bench_settlements=settlements,
        stock_coverage_complete=True,
        bench_coverage_complete=True,
        window=3,
        min_bars=3,
        z_threshold=3,
    )
    shocks = detect_shocks(stock, qqq, window=3, min_bars=3, z_threshold=3)
    assert len(shocks) >= 1
    assert shocks[0]["signal_open_ms"] == 4 * H
    assert shocks[0]["residual"] == 3.0
    long_book = simulate_symbol(shocks, rule="continuation", **{k: common[k] for k in common if k not in ("window", "min_bars", "z_threshold")})
    assert long_book["excluded_missing_funding"] == 0
    assert len(long_book["scored"]) == 1
    trade = long_book["scored"][0]
    assert trade["entry_open"] == "100"
    assert trade["entry_open"] != "1680"
    assert trade["gross_bp"] == 100.0
    assert trade["fee_bp"] == 12.0
    assert trade["spread_bp"] == 2.0
    assert trade["funding_bp"] == 1.0
    assert trade["net_bp"] == 85.0
    short_book = simulate_symbol(shocks, rule="reversal", **{k: common[k] for k in common if k not in ("window", "min_bars", "z_threshold")})
    short = short_book["scored"][0]
    assert short["direction"] == -1
    assert short["funding_bp"] == -1.0
    assert short["net_bp"] == -113.0


def test_missing_funding_excludes_the_trade_and_does_not_substitute_zero():
    stock = [_bar(0, 100, 100), _bar(1, 100, 100), _bar(5, 101, 101)]
    bench = [_bar(0, 50, 50), _bar(1, 50, 50), _bar(5, 50, 50)]
    shock = _shock()
    covered = [
        {"time_ms": 0, "rate": "0.0001"},
        {"time_ms": 3 * H, "rate": "0.0001"},
        {"time_ms": 10 * H, "rate": "0.0001"},
    ]
    kwargs = dict(
        symbol="NVDAUSDT",
        rule="continuation",
        hedged=False,
        half_spread_bp=1,
        taker_fee_stock="0.0006",
        taker_fee_bench="0.0006",
        stock_settlements=covered,
        bench_settlements=covered,
        bench_coverage_complete=True,
    )
    missing = price_trade(shock, stock, bench, stock_coverage_complete=False, **kwargs)
    assert missing is not None
    assert missing["funding_missing"] is True
    assert missing["funding_bp"] is None
    assert missing["net_bp"] is None
    book = simulate_symbol([shock], stock, bench, stock_coverage_complete=False, **kwargs)
    assert book["excluded_missing_funding"] == 1
    assert book["scored"] == []
    present = price_trade(shock, stock, bench, stock_coverage_complete=True, **kwargs)
    assert present["funding_missing"] is False
    assert present["funding_bp"] == 1.0
    assert present["net_bp"] == 85.0


def test_a_schedule_hole_is_missing_and_a_normal_gap_is_a_real_zero():
    stamps = [hour * 8 * H for hour in range(11)]
    settlements = [{"time_ms": stamp, "rate": "0.0002"} for stamp in stamps if stamp != 40 * H]
    quiet = funding_status(settlements, 1 * H, 5 * H, coverage_complete=True)
    assert quiet["missing"] is False
    assert quiet["rates"] == []
    hole = funding_status(settlements, 36 * H, 40 * H, coverage_complete=True)
    assert hole["missing"] is True
    assert hole["rates"] is None


def test_overlapping_signal_is_not_a_second_position():
    shocks = [
        _shock(),
        _shock(
            signal_open_ms=H,
            signal_close_ms=2 * H,
            window_end_ms=0,
            window_start_ms=-2 * H,
            window_times=[-2 * H, -H, 0],
            entry_open_ms=2 * H,
            exit_open_ms=6 * H,
        ),
    ]
    bars = [_bar(1, 100, 100), _bar(5, 101, 101)]
    settlements = [{"time_ms": 0, "rate": "0"}, {"time_ms": 20 * H, "rate": "0"}]
    book = simulate_symbol(
        shocks,
        bars,
        bars,
        symbol="NVDAUSDT",
        rule="continuation",
        hedged=False,
        half_spread_bp=0,
        taker_fee_stock="0.0006",
        taker_fee_bench="0.0006",
        stock_settlements=settlements,
        bench_settlements=settlements,
        stock_coverage_complete=True,
        bench_coverage_complete=True,
    )
    assert book["overlap_skipped"] == 1
    assert len(book["scored"]) == 1
    assert book["scored"][0]["signal_open_ms"] == 0


def test_random_direction_is_the_sha256_parity():
    # sha256("H-BR-1|NVDAUSDT|0") first byte is 105, which is odd, so short.
    assert random_direction("NVDAUSDT", 0) == -1
    assert random_direction("NVDAUSDT", 0) == -1


def test_split_and_selection_follow_the_preregistration():
    stamps = list(range(100))
    splits = chronological_splits(stamps)
    assert splits["train"] == list(range(50))
    assert splits["validation"] == list(range(50, 75))
    assert splits["holdout"] == list(range(75, 100))
    rows = [
        {"variant": "continuation_unhedged", "mean_net_bp": 1.0, "sharpe": 0.1, "n": 30, "half_spread_bp": 1},
        {"variant": "reversal_unhedged", "mean_net_bp": 2.0, "sharpe": 0.1, "n": 30, "half_spread_bp": 1},
        {"variant": "continuation_hedged", "mean_net_bp": 2.0, "sharpe": 0.2, "n": 30, "half_spread_bp": 1},
        {"variant": "reversal_hedged", "mean_net_bp": 5.0, "sharpe": 1.0, "n": 29, "half_spread_bp": 1},
        {"variant": "continuation_unhedged", "mean_net_bp": 9.0, "sharpe": 1.0, "n": 40, "half_spread_bp": 2},
    ]
    assert select_variant(rows) == "continuation_hedged"
    assert select_variant([{"variant": "continuation_unhedged", "mean_net_bp": 1.0, "sharpe": 0.1, "n": 29, "half_spread_bp": 1}]) is None
    assert preregistered_verdict(1.0, 0.04, 30, selected=True) == "promising"
    assert preregistered_verdict(1.0, 0.05, 30, selected=True) == "rejected"
    assert preregistered_verdict(0.0, 0.01, 40, selected=True) == "rejected"
    assert preregistered_verdict(1.0, 0.01, 29, selected=True) == "insufficient"
    assert preregistered_verdict(1.0, 0.01, 40, selected=False) == "insufficient"
