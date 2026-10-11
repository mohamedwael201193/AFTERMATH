import json
import random
import statistics
from pathlib import Path

from aftermath_api.metrics import BOOTSTRAP_DRAWS, BOOTSTRAP_SEED, evaluate

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
