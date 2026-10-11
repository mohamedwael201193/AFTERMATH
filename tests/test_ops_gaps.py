"""Trailing-hour operation gaps. Offline MemoryStore only."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from aftermath_api.app import create_app
from aftermath_api.config import Settings
from aftermath_api.store import MemoryStore, build_operation_status

NOW = datetime(2026, 10, 11, 6, 22, tzinfo=timezone.utc)


def _settings(**kwargs):
    base = dict(
        env="test", database_url="", direct_url="", llm_api_key="", llm_base_url="", llm_model="",
        llm_configured=False, reader_token="reader-token", decision_token="decision-token", job_token="job-token",
        signing_key_path="", sec_user_agent="", web_origin="https://app.example", decisions="abstain_only",
    )
    base.update(kwargs)
    return Settings(**base)


def _http(store=None):
    client = TestClient(create_app(_settings(), store or MemoryStore()))
    client.app.state.ops_clock = lambda: NOW
    return client


def _hour(offset: int) -> datetime:
    base = NOW.replace(minute=0, second=0, microsecond=0)
    return base + timedelta(hours=offset)


def _token(offset: int) -> str:
    return _hour(offset).strftime("%Y-%m-%dT%H")


def _run(store: MemoryStore, offset: int, **fields) -> dict:
    hour = _hour(offset)
    started = fields.pop("started", hour + timedelta(minutes=17))
    seconds = fields.pop("seconds", 40)
    row = {
        "id": fields.pop("id", "run_" + hour.strftime("%Y%m%d%H")),
        "idempotency_key": "paper-cycle:v2:" + hour.strftime("%Y-%m-%dT%H"),
        "status": fields.pop("status", "refused"),
        "reason": fields.pop("reason", "no_qualifying_event"),
        "decision_id": None,
        "started_at_utc": started.isoformat(),
        "finished_at_utc": (started + timedelta(seconds=seconds)).isoformat(),
        "detail": fields.pop("detail", {"model_calls": 0, "fetch_errors": 0}),
    }
    store.insert_run(row)
    return row


def _status(store: MemoryStore) -> dict:
    response = _http(store).get("/v1/ops/status", headers={"Authorization": "Bearer reader-token"})
    assert response.status_code == 200
    return response.json()


def test_open_hour_without_a_run_is_not_missing_and_gaps_are_newest_first():
    store = MemoryStore()
    _run(store, -1, seconds=90, detail={"model_calls": 0, "fetch_errors": 1})
    _run(
        store,
        -1,
        id="run_duplicate",
        seconds=5,
        detail={"model_calls": 9, "fetch_errors": 4},
    )
    _run(
        store,
        -3,
        started=_hour(-2) + timedelta(minutes=10),
        reason="document_not_ready",
        detail={"model_calls": 0, "fetch_errors": 0},
    )
    _run(
        store,
        -5,
        reason="malformed_model_output",
        detail={"model_calls": 2, "fetch_errors": 0},
    )
    store.insert_decision({
        "id": "dec_risk",
        "status": "RISK_REJECTED",
        "decision_source": "model",
        "reason": "spread_ok,depth_ok",
        "idempotency_key": "paper-cycle:v2:" + _token(-1),
        "created_at_utc": "2026-10-11T05:40:00+00:00",
    }, [])
    store.insert_decision({
        "id": "dec_other",
        "status": "ABSTAIN",
        "decision_source": "model",
        "reason": "totally_unknown_reason",
        "idempotency_key": "paper-cycle:v2:" + _token(-5),
        "created_at_utc": "2026-10-11T01:40:00+00:00",
    }, [])
    store.insert_decision({
        "id": "dec_hold",
        "status": "ABSTAIN",
        "decision_source": "model",
        "reason": "awaiting_next_book",
        "idempotency_key": "paper-cycle:v2:" + _token(-3) + ":hold",
        "created_at_utc": "2026-10-11T01:41:00+00:00",
    }, [])
    store.insert_decision({
        "id": "dec_rule",
        "status": "ABSTAIN",
        "decision_source": "abstain",
        "reason": "spread_ok",
        "idempotency_key": "manual-rule",
        "created_at_utc": "2026-10-11T05:10:00+00:00",
    }, [])
    store.insert_fill({
        "id": "fill_open",
        "decision_id": "dec_risk",
        "idempotency_key": "paper-cycle:v2:" + _token(-1) + ":entry",
        "status": "PAPER_FILLED",
        "cost_json": {},
        "created_at_utc": "2026-10-11T05:45:00+00:00",
    })
    store.insert_fill({
        "id": "fill_closed",
        "decision_id": "dec_risk",
        "idempotency_key": "paper-cycle:v2:" + _token(-3) + ":exit",
        "status": "CLOSED",
        "cost_json": {},
        "created_at_utc": "2026-10-11T04:12:00+00:00",
    })
    store.insert_fill({
        "id": "fill_wait",
        "decision_id": "dec_risk",
        "idempotency_key": "paper-cycle:v2:" + _token(-5) + ":entry",
        "status": "PENDING_ENTRY",
        "cost_json": {},
        "created_at_utc": "2026-10-11T01:50:00+00:00",
    })

    body = _status(store)
    operation = body["operation"]
    missing = operation["missing_hours"]
    assert body["continuous_operation"] is False
    assert body["continuous_operation_observed"] is False
    assert operation["continuous_operation_observed"] is False
    assert operation["window_hours"] == 48
    assert operation["expected_hours"] == 5
    assert operation["before_first_run_hours"] == 43
    assert operation["recorded_hours"] == 3
    assert operation["counters"]["scheduled_cycles"] == 3
    assert _token(0) not in missing
    assert missing == [_token(-2), _token(-4)]
    assert _token(-6) not in missing
    assert _token(-48) not in missing
    assert operation["first_recorded_hour"] == _token(-5)
    assert operation["last_recorded_hour"] == _token(-1)
    assert operation["consecutive_recorded_hours_ending_now"] == 1
    assert operation["gap_free_since"] == _token(-1)
    assert operation["latest_duration_seconds"] == 90
    assert operation["counters"]["llm_decisions"] == 1
    assert operation["counters"]["pre_model_refusals"] == 2
    assert operation["counters"]["risk_refusals"] == 1
    assert operation["counters"]["other"] == 1
    assert operation["counters"]["paper_fills"] == 2
    assert operation["counters"]["fetch_error_runs"] == 1


def test_duplicate_hour_rows_count_once():
    hour = _hour(-1)
    started = hour + timedelta(minutes=17)
    key = "paper-cycle:v2:" + _token(-1)
    first = {
        "idempotency_key": key,
        "status": "refused",
        "reason": "no_qualifying_event",
        "started_at_utc": started.isoformat(),
        "finished_at_utc": (started + timedelta(seconds=12)).isoformat(),
        "detail": {"model_calls": 0, "fetch_errors": 0},
    }
    duplicate = {**first, "id": "run_other", "detail": {"model_calls": 5, "fetch_errors": 3}}
    report = build_operation_status([first, duplicate], [], 0, NOW)
    assert report["recorded_hours"] == 1
    assert report["counters"]["scheduled_cycles"] == 1
    assert report["counters"]["llm_decisions"] == 0
    assert report["counters"]["fetch_error_runs"] == 0
    assert report["latest_duration_seconds"] == 12


def test_a_cycle_written_with_the_earlier_key_counts_as_a_recorded_hour():
    hour = _hour(-2)
    started = hour + timedelta(minutes=36)
    run = {
        "idempotency_key": "paper-cycle:" + _token(-2),
        "status": "refused",
        "reason": "missing_order_book",
        "started_at_utc": started.isoformat(),
        "finished_at_utc": (started + timedelta(seconds=20)).isoformat(),
        "detail": {"model_calls": 0, "fetch_errors": 0},
    }
    report = build_operation_status([run], [], 0, NOW)
    assert report["recorded_hours"] == 1
    assert report["first_recorded_hour"] == _token(-2)
    assert report["counters"]["scheduled_cycles"] == 1
    assert report["counters"]["pre_model_refusals"] == 1


def test_twenty_four_consecutive_completed_hours_are_observed():
    store = MemoryStore()
    for offset in range(1, 24):
        calls = 4 if offset == 1 else 0
        _run(
            store,
            -offset,
            reason="no_qualifying_event" if calls == 0 else "malformed_model_output",
            detail={"model_calls": calls, "fetch_errors": 0},
        )
    _run(store, -1, id="run_dup", detail={"model_calls": 9, "fetch_errors": 2}, reason="malformed_model_output")
    short = _status(store)
    assert short["continuous_operation"] is False
    assert short["continuous_operation_observed"] is False
    assert short["operation"]["consecutive_recorded_hours_ending_now"] == 23
    assert short["operation"]["counters"]["llm_decisions"] == 1
    assert short["operation"]["recorded_hours"] == 23
    assert _token(0) not in short["operation"]["missing_hours"]

    _run(store, -24, detail={"model_calls": 0, "fetch_errors": 0})
    full = _status(store)
    assert full["continuous_operation"] is False
    assert full["continuous_operation_observed"] is True
    assert full["operation"]["consecutive_recorded_hours_ending_now"] == 24
    assert full["operation"]["gap_free_since"] == _token(-24)
    assert full["operation"]["counters"]["llm_decisions"] == 1
    assert full["operation"]["recorded_hours"] == 24
