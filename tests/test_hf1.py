from aftermath_api.config import Settings
from aftermath_api.cycle import WHITELIST, run_paper_cycle
from aftermath_api.store import MemoryStore
from aftermath_api.strategies.hf1 import REFERENCE, THRESHOLD_BP, UNIVERSE, hourly_residual_events, prospective_scan


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


def test_only_hours_that_close_after_the_commit_are_prospective():
    assert set(UNIVERSE) == set(WHITELIST)
    assert REFERENCE == "QQQUSDT"
    bars = {
        "QQQUSDT": [[0, 400.0], [3_600_000, 400.0], [7_200_000, 400.0]],
        "NVDAUSDT": [[0, 100.0], [3_600_000, 101.0], [7_200_000, 102.0]],
    }
    before = prospective_scan(bars, now_ms=7_200_000, counted_after_ms=7_200_000)
    assert before["events"] == []
    assert before["latest"] == []
    after = prospective_scan(bars, now_ms=10_800_000, counted_after_ms=7_200_000)
    assert len(after["events"]) == 1
    assert after["events"][0]["signal_open_ms"] == 7_200_000
    assert after["counted_outcome"] is False
    assert after["model_called"] is False
    open_bar = prospective_scan(
        {"QQQUSDT": [[0, 400.0], [3_600_000, 400.0]], "NVDAUSDT": [[0, 100.0], [3_600_000, 110.0]]},
        now_ms=3_600_000,
        counted_after_ms=0,
    )
    assert open_bar["events"] == []


def test_an_hf1_signal_does_not_enter_the_paper_ledger():
    store = MemoryStore()
    settings = Settings(
        env="test", database_url="", direct_url="", llm_api_key="", llm_base_url="", llm_model="",
        llm_configured=False, reader_token="reader-token", decision_token="decision-token", job_token="job-token",
        signing_key_path="", sec_user_agent="", web_origin="https://app.example", decisions="abstain_only",
    )
    calls = []

    def scanner(now):
        calls.append(now)
        return {
            "strategy_id": "H-HF-1",
            "counted_outcome": True,
            "selected": True,
            "model_called": True,
            "events": [{"symbol": "NVDAUSDT", "residual_bp": 100.0, "counted_outcome": True}],
        }

    def fetch():
        return ([{
            "source": "bitget-rest",
            "instrument_id": "NVDAUSDT",
            "event_type": "ticker",
            "event_time_utc": "2026-10-11T02:00:00+00:00",
            "fetched_at_utc": "2026-10-11T02:00:00+00:00",
            "payload": {"last": 101.5},
            "mapping_confidence": 1.0,
        }], [])

    first = run_paper_cycle(settings, store, fetch=fetch, hf1_scan=scanner)
    second = run_paper_cycle(settings, store, fetch=fetch, hf1_scan=scanner)
    assert first["reason"] == "missing_order_book"
    assert second["repeated"] is True
    assert calls == [calls[0]]
    assert store.fills == {}
    detail = store.latest_run()["detail"]
    assert detail["model_calls"] == 0
    assert detail["hf1"]["counted_outcome"] is False
    assert detail["hf1"]["selected"] is False
    assert detail["hf1"]["model_called"] is False
    assert detail["hf1"]["events"][0]["residual_bp"] == 100.0
