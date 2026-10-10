import random
import statistics

from aftermath_api.metrics import BOOTSTRAP_DRAWS, BOOTSTRAP_SEED, evaluate


def _pair(agent: float, closed_at: str, fixed: float = 0.0) -> dict:
    return {
        "closed_at": closed_at,
        "agent_bp": agent,
        "fixed_sign_bp": fixed,
        "llm_off_bp": 0.0,
        "random_bp": 0.0,
        "no_trade_bp": 0.0,
    }


def test_two_trades_stay_insufficient():
    report = evaluate([_pair(25, "2026-10-01T00:00:00+00:00"), _pair(-5, "2026-10-02T00:00:00+00:00")])
    assert report["status"] == "INSUFFICIENT_DATA"
    assert report["sample_size"] == 2
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
    assert agent["sharpe"] == round(statistics.fmean(values) / statistics.stdev(values), 4)
    downside = (sum(min(value, 0.0) ** 2 for value in values) / 30) ** 0.5
    assert agent["sortino"] == round(statistics.fmean(values) / downside, 4)
    assert report["max_drawdown_bp"] == 50
    assert report["arms"]["no_trade"]["mean_net_bp"] == 0
    rng = random.Random(BOOTSTRAP_SEED)
    means = []
    differences = values
    for _draw in range(BOOTSTRAP_DRAWS):
        means.append(statistics.fmean(differences[rng.randrange(30)] for _item in range(30)))
    means.sort()
    assert report["paired_agent_minus_fixed_bp"]["bootstrap_95"]["low"] == round(means[int(0.025 * (BOOTSTRAP_DRAWS - 1))], 4)
    assert report["paired_agent_minus_fixed_bp"]["bootstrap_95"]["high"] == round(means[int(0.975 * (BOOTSTRAP_DRAWS - 1))], 4)
