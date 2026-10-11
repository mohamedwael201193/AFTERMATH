from aftermath_api.strategies.hf1 import THRESHOLD_BP, hourly_residual_events


def test_hourly_residual_event_uses_only_adjacent_closed_hours():
    stock = [[0, 100.0], [3_600_000, 101.0], [10_800_000, 110.0]]
    ref = [[0, 400.0], [3_600_000, 400.0], [10_800_000, 400.0]]
    events = hourly_residual_events(stock, ref)
    assert THRESHOLD_BP == 50.0
    assert len(events) == 1
    assert events[0]["signal_open_ms"] == 3_600_000
    assert events[0]["residual_bp"] == 100.0
    assert events[0]["counted_outcome"] is False
    assert events[0]["strategy_id"] == "H-HF-1"


def test_a_gap_or_a_small_move_is_not_an_event():
    stock = [[0, 100.0], [7_200_000, 110.0]]
    ref = [[0, 400.0], [7_200_000, 400.0]]
    assert hourly_residual_events(stock, ref) == []
    aligned = [[0, 100.0], [3_600_000, 100.4]]
    reference = [[0, 400.0], [3_600_000, 400.0]]
    assert hourly_residual_events(aligned, reference) == []


def test_a_missing_reference_bar_stays_missing():
    stock = [[0, 100.0], [3_600_000, 110.0]]
    ref = [[3_600_000, 400.0]]
    assert hourly_residual_events(stock, ref) == []
