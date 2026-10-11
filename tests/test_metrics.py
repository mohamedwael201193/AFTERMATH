import json
import random
import statistics
from pathlib import Path

from aftermath_api.metrics import (
    BOOTSTRAP_DRAWS,
    BOOTSTRAP_SEED,
    bonferroni,
    deflated_sharpe,
    evaluate,
    exposure_fraction,
    max_drawdown,
    moment_skew_kurtosis,
    one_sided_bootstrap_p,
    per_trade_sharpe,
    turnover_rate,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _pair(
    agent: float,
    closed_at: str,
    fixed: float = 0.0,
    *,
    fees_bp: float | None = None,
    funding_bp: float | None = None,
    slippage_bp: float | None = None,
    risk_control_violation: bool = False,
) -> dict:
    row = {
        "closed_at": closed_at,
        "agent_bp": agent,
        "fixed_sign_bp": fixed,
        "llm_off_bp": 0.0,
        "random_bp": 0.0,
        "no_trade_bp": 0.0,
    }
    if fees_bp is not None:
        row["fees_bp"] = fees_bp
    if funding_bp is not None:
        row["funding_bp"] = funding_bp
    if slippage_bp is not None:
        row["slippage_bp"] = slippage_bp
    if risk_control_violation:
        row["risk_control_violation"] = True
    return row


def _bootstrap_bounds(differences: list[float]) -> tuple[float, float]:
    rng = random.Random(BOOTSTRAP_SEED)
    means = []
    width = len(differences)
    for _draw in range(BOOTSTRAP_DRAWS):
        means.append(statistics.fmean(differences[rng.randrange(width)] for _item in range(width)))
    means.sort()
    low = means[int(0.025 * (BOOTSTRAP_DRAWS - 1))]
    high = means[int(0.975 * (BOOTSTRAP_DRAWS - 1))]
    return round(low, 4), round(high, 4)


def test_two_trades_stay_insufficient():
    report = evaluate([_pair(25, "2026-10-01T00:00:00+00:00"), _pair(-5, "2026-10-02T00:00:00+00:00")])
    assert report["status"] == "INSUFFICIENT_DATA"
    assert report["sample_size"] == 2
    assert "arms" not in report


def test_thirty_pairs_with_only_fourteen_nonzero_stays_insufficient():
    rows = []
    for index in range(16):
        rows.append(_pair(5.0, f"2026-05-{index + 1:02d}T00:00:00+00:00", fixed=5.0))
    for index in range(14):
        rows.append(_pair(5.0, f"2026-06-{index + 1:02d}T00:00:00+00:00", fixed=0.0))
    report = evaluate(rows)
    assert report["status"] == "INSUFFICIENT_DATA"
    assert report["sample_size"] == 30
    assert report["nonzero_pairs"] == 14
    assert "arms" not in report


def test_registered_sample_matches_the_hand_calculation():
    rows = []
    for index in range(10):
        rows.append(_pair(10, f"2026-01-{index + 1:02d}T00:00:00+00:00"))
    for index in range(10):
        rows.append(_pair(-5, f"2026-02-{index + 1:02d}T00:00:00+00:00"))
    for index in range(10):
        rows.append(_pair(0, f"2026-03-{index + 1:02d}T00:00:00+00:00"))
    report = evaluate(rows)
    assert report["status"] == "OBSERVED"
    assert report["sample_size"] == 30
    assert report["nonzero_pairs"] == 20
    agent = report["arms"]["agent"]
    assert agent["mean_net_bp"] == 1.6667
    assert agent["median_net_bp"] == 0
    assert agent["win_rate"] == 0.3333
    values = [10.0] * 10 + [-5.0] * 10 + [0.0] * 10
    assert report["net_return_bp"] == round(sum(values), 4)
    assert report["win_rate"] == agent["win_rate"]
    assert report["sharpe"] == agent["sharpe"]
    assert agent["sharpe"] == round(statistics.fmean(values) / statistics.stdev(values), 4)
    downside = (sum(min(value, 0.0) ** 2 for value in values) / 30) ** 0.5
    assert agent["sortino"] == round(statistics.fmean(values) / downside, 4)
    assert report["max_drawdown_bp"] == 50
    assert report["arms"]["no_trade"]["mean_net_bp"] == 0
    assert report["risk_control_violation_rate"] == 0.0
    differences = values
    low, high = _bootstrap_bounds(differences)
    assert report["paired_agent_minus_fixed_bp"]["bootstrap_95"]["low"] == low
    assert report["paired_agent_minus_fixed_bp"]["bootstrap_95"]["high"] == high


def test_golden_fixture_matches_hand_formulas():
    payload = json.loads((FIXTURES / "metrics_golden_pairs.json").read_text(encoding="utf-8"))
    rows = payload["pairs"]
    n = len(rows)
    assert n == 30

    agent_values = [float(row["agent_bp"]) for row in rows]
    fixed_values = [float(row["fixed_sign_bp"]) for row in rows]

    expected_net_return = round(sum(agent_values), 4)
    expected_mean_agent = round(statistics.fmean(agent_values), 4)
    expected_win_rate = round(sum(1 for value in agent_values if value > 0) / n, 4)
    expected_sharpe = None
    if statistics.stdev(agent_values) != 0:
        expected_sharpe = round(statistics.fmean(agent_values) / statistics.stdev(agent_values), 4)
    expected_paired_mean = round(statistics.fmean(a - f for a, f in zip(agent_values, fixed_values)), 4)
    expected_violation_rate = round(sum(1 for row in rows if row.get("risk_control_violation")) / n, 4)
    expected_costs = {
        "fees_bp_mean": round(statistics.fmean(float(row["fees_bp"]) for row in rows), 4),
        "funding_bp_mean": round(statistics.fmean(float(row["funding_bp"]) for row in rows), 4),
        "slippage_bp_mean": round(statistics.fmean(float(row["slippage_bp"]) for row in rows), 4),
    }
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for value in agent_values:
        equity += value
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    expected_drawdown = round(worst, 4)

    report = evaluate(rows)
    assert report["status"] == "OBSERVED"
    assert report["sample_size"] == 30
    assert report["nonzero_pairs"] == 30
    assert report["net_return_bp"] == expected_net_return
    assert report["arms"]["agent"]["mean_net_bp"] == expected_mean_agent
    assert report["win_rate"] == expected_win_rate
    assert report["sharpe"] == expected_sharpe
    assert report["paired_agent_minus_fixed_bp"]["mean"] == expected_paired_mean
    assert report["costs"] == expected_costs
    assert report["risk_control_violation_rate"] == expected_violation_rate
    assert report["max_drawdown_bp"] == expected_drawdown

    differences = [a - f for a, f in zip(agent_values, fixed_values)]
    low, high = _bootstrap_bounds(differences)
    assert report["paired_agent_minus_fixed_bp"]["bootstrap_95"]["low"] == low
    assert report["paired_agent_minus_fixed_bp"]["bootstrap_95"]["high"] == high


def test_additive_drawdown_exposure_turnover_and_bonferroni():
    # Cumulative series [0, 10, 7, 12, 4].
    # Peaks: 0, 10, 10, 12, 12. Drops: 0, 0, 3, 0, 8. Max drawdown is 8.
    assert max_drawdown([0, 10, 7, 12, 4]) == 8
    assert max_drawdown([1, 2, 3]) == 0
    assert max_drawdown([]) == 0
    # 8 position-hours out of 200 available hours is 0.04.
    assert exposure_fraction(8, 200) == 0.04
    # 4 units of notional over 200 hours is 0.02 per hour.
    assert turnover_rate(4, 200) == 0.02
    # 0.02 * 4 variants = 0.08. 0.4 * 4 caps at 1.
    assert bonferroni(0.02, 4) == 0.08
    assert bonferroni(0.4, 4) == 1.0


def test_moments_and_the_house_per_trade_sharpe():
    # values 1, 2, 3. mean 2. Second moment 2/3. Fourth moment 2/3.
    # kurtosis = (2/3) / (2/3)^2 = 1.5. Skew is 0.
    assert moment_skew_kurtosis([1, 2, 3]) == (0.0, 1.5)
    values = [10.0] * 10 + [-5.0] * 10 + [0.0] * 10
    # mean 50/30. Sample stdev gives Sharpe 0.2628 at 4 decimal places.
    assert per_trade_sharpe(values) == 0.2628


def test_deflated_sharpe_on_a_known_input():
    # One trial and a zero Sharpe: SR* = 0, z = 0, Phi(0) = 0.5.
    assert deflated_sharpe(0.0, 100, 1, 0.0, 3.0) == 0.5
    # N=4, n=30, SR=0.5, skew=0, kurtosis=3 (Pearson, normal = 3).
    # V = 1/29. scale = sqrt(1/29) = 0.18569533817705186.
    # Phi^{-1}(0.75) = 0.6744897501960817.
    # Phi^{-1}(1 - 1/(4e)) = Phi^{-1}(0.908031535) = 1.3287219496247633.
    # Euler gamma = 0.5772156649015329.
    # SR* = 0.18569533817705186 * ((1-gamma)*z1 + gamma*z2) = 0.195374303641627.
    # Denominator sqrt(1 + ((3-1)/4)*0.5^2) = sqrt(1.125).
    # z = (0.5 - 0.195374303641627) * sqrt(29) / sqrt(1.125) = 1.5466401237874416.
    # Phi(z) = 0.9390249756 at 10 decimal places.
    assert round(deflated_sharpe(0.5, 30, 4, 0.0, 3.0), 10) == 0.9390249756
    # Same n and N, so the same SR*. skew=-1, kurtosis=6, SR=0.4.
    # inside = 1 - (-1)*0.4 + ((6-1)/4)*0.16 = 1.6.
    # Phi(z) = 0.8081672869 at 10 decimal places.
    assert round(deflated_sharpe(0.4, 30, 4, -1.0, 6.0), 10) == 0.8081672869


def test_one_sided_bootstrap_p_is_conservative():
    # Every resample of a strictly positive sample has a positive mean.
    # p = 1 / 2001.
    assert one_sided_bootstrap_p([1.0, 2.0, 3.0]) == 1 / (BOOTSTRAP_DRAWS + 1)
    assert one_sided_bootstrap_p([-2.0, -1.0]) == 1.0
    assert BOOTSTRAP_SEED == 20261011
    assert BOOTSTRAP_DRAWS == 2000
