from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from aftermath_api.app import create_app
from aftermath_api.config import Settings
from aftermath_api.ids import snapshot_hash
from aftermath_api.store import Immutable, MemoryStore


def settings(**kwargs) -> Settings:
    base = dict(
        env="test",
        database_url="",
        direct_url="",
        llm_api_key="",
        llm_base_url="",
        llm_model="",
        llm_configured=False,
        reader_token="reader-token",
        decision_token="decision-token",
        job_token="job-token",
        signing_key_path="",
        sec_user_agent="",
        web_origin="https://app.example",
        decisions="abstain_only",
    )
    base.update(kwargs)
    return Settings(**base)


def client(store=None, **kwargs):
    return TestClient(create_app(settings(**kwargs), store or MemoryStore()))


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def test_health_and_ready_without_llm():
    http = client()
    assert http.get("/health").status_code == 200
    ready = http.get("/ready").json()
    assert ready["llm"] == "absent"
    assert ready["decisions"] == "abstain_only"
    assert ready["ready"] is True


def test_prod_missing_signing_key_is_not_ready():
    http = client(env="prod", database_url="postgres", signing_key_path="")
    assert http.get("/health").status_code == 200
    ready = http.get("/ready")
    assert ready.status_code == 503
    assert "signing_key" in ready.json()["problems"]


def test_reader_cannot_decide_and_missing_bearer_is_401():
    http = client()
    assert http.get("/v1/events").status_code == 401
    denied = http.post("/v1/decisions", headers={"Authorization": "Bearer reader-token", "Idempotency-Key": "k"}, json={"evidence_ids": ["ev_x"]})
    assert denied.status_code == 403
    job = http.get("/v1/events", headers={"Authorization": "Bearer job-token"})
    assert job.status_code == 403


def test_abstain_when_llm_missing_and_idempotent(tmp_path):
    store = MemoryStore()
    http = client(store)
    now = _now()
    ingested = http.post(
        "/v1/events",
        headers={"Authorization": "Bearer decision-token"},
        json={
            "source": "bitget-rest",
            "instrument_id": "NVDAUSDT",
            "event_type": "ticker",
            "event_time_utc": now,
            "fetched_at_utc": now,
            "payload": {"last": 100.0},
            "mapping_confidence": 1.0,
        },
    )
    assert ingested.status_code == 200
    evid = ingested.json()["evidence"]["id"]
    body = {"evidence_ids": [evid]}
    headers = {"Authorization": "Bearer decision-token", "Idempotency-Key": "same-key"}
    first = http.post("/v1/decisions", headers=headers, json=body)
    second = http.post("/v1/decisions", headers=headers, json=body)
    assert first.status_code == 200
    decision = first.json()["decision"]
    assert decision["status"] == "ABSTAIN"
    assert decision["decision_source"] == "abstain"
    assert decision["reason"] == "llm_unconfigured"
    assert decision["evidence_ids"] == [evid]
    assert second.json()["decision"]["id"] == decision["id"]
    assert len(store.decisions) == 1
    expected = snapshot_hash(1, decision["prompt_hash"], [(evid, ingested.json()["evidence"]["payload_hash"])])
    assert decision["input_snapshot_hash"] == expected


def test_events_are_immutable():
    store = MemoryStore()
    store.insert_event({"id": "evn_1", "event_time_utc": "2026-01-01T00:00:00+00:00", "payload": {}})
    try:
        store.update_event("evn_1", {"payload": {"changed": True}})
    except Immutable:
        return
    raise AssertionError("update was accepted")


def test_low_confidence_and_future_rejected():
    http = client()
    now = _now()
    low = http.post(
        "/v1/events",
        headers={"Authorization": "Bearer decision-token"},
        json={"source": "x", "instrument_id": "NVDAUSDT", "event_type": "ticker", "event_time_utc": now, "fetched_at_utc": now, "payload": {"last": 1}, "mapping_confidence": 0.5},
    )
    assert low.status_code == 422
    assert low.json()["error"]["code"] == "UNMAPPED_SYMBOL"
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    bad = http.post(
        "/v1/events",
        headers={"Authorization": "Bearer decision-token"},
        json={"source": "x", "instrument_id": "NVDAUSDT", "event_type": "ticker", "event_time_utc": future, "fetched_at_utc": now, "payload": {"last": 1}},
    )
    assert bad.status_code == 422


def test_job_route_rejects_reader_and_repeats_hour_key():
    http = client()
    denied = http.post("/internal/jobs/paper-cycle", headers={"Authorization": "Bearer reader-token"})
    assert denied.status_code == 403
    headers = {"Authorization": "Bearer job-token"}
    first = http.post("/internal/jobs/paper-cycle", headers=headers)
    second = http.post("/internal/jobs/paper-cycle", headers=headers)
    assert first.json()["repeated"] is False
    assert second.json()["repeated"] is True
    assert first.json()["decision_id"] == second.json()["decision_id"]


def test_approved_paper_fill_is_idempotent():
    store = MemoryStore()
    http = client(store)

    def fake_decide(_settings, rows):
        from aftermath_api.decide import abstain

        out = abstain("test_branch", [(r["id"], r["payload_hash"]) for r in rows])
        out["decision_source"] = "model"
        out["status"] = "PAPER_PROPOSED"
        out["reason"] = "test_branch"
        out["proposal"] = {"action": "LONG", "symbol": "NVDAUSDT", "size_frac": 0.05, "horizon_hours": 24, "confidence": 0.8}
        return out

    http.app.state.decider = fake_decide
    now = _now()
    evid = http.post(
        "/v1/events",
        headers={"Authorization": "Bearer decision-token"},
        json={"source": "fixture", "instrument_id": "NVDAUSDT", "event_type": "book", "event_time_utc": now, "fetched_at_utc": now, "payload": {"last": 100.0}},
    ).json()["evidence"]["id"]
    ctx = {"symbol": "NVDAUSDT", "source": "llm", "emergency_stop": False, "contract": {"status": "normal", "is_rwa": "YES"}, "spread_bp": 1.0,
           "depth_band_usdt": 1e6, "data_age_min": 0.0, "event_age_min": 60.0, "equity": 10000.0, "gross_open_usdt": 0.0, "n_open": 0,
           "open_symbols": [], "symbol_pnl_today": 0.0, "day_pnl": 0.0, "drawdown": 0.0, "n_precedents": 5, "hedge_beta": 1.0, "hedge_r2": 0.4}
    body = {"evidence_ids": [evid], "risk_context": ctx, "side": 1, "notional": 100, "ref_price": 100, "fee_rate": 0.0006, "book": {"bids": [[1.0, 1000.0]], "asks": [[1.0, 1000.0]]}}
    headers = {"Authorization": "Bearer decision-token", "Idempotency-Key": "paper-1"}
    first = http.post("/v1/decisions", headers=headers, json=body)
    second = http.post("/v1/decisions", headers=headers, json=body)
    assert first.status_code == 200
    assert first.json()["decision"]["status"] == "PAPER_FILLED"
    assert first.json()["fill"]["status"] == "PAPER_FILLED"
    assert second.json()["decision"]["id"] == first.json()["decision"]["id"]
    assert len(store.fills) == 1


def test_signed_receipt_verifies_and_replay_does_not_extend_the_chain(tmp_path):
    from aftermath_api.receipts import generate_production_key

    private = tmp_path / "production_ed25519.key"
    generate_production_key(private, tmp_path / "production_ed25519.pub")
    store = MemoryStore()
    http = client(store, signing_key_path=str(private))
    now = _now()
    evid = http.post(
        "/v1/events",
        headers={"Authorization": "Bearer decision-token"},
        json={"source": "bitget-rest", "instrument_id": "NVDAUSDT", "event_type": "ticker", "event_time_utc": now, "fetched_at_utc": now, "payload": {"last": 10}},
    ).json()["evidence"]["id"]
    headers = {"Authorization": "Bearer decision-token", "Idempotency-Key": "signed-1"}
    first = http.post("/v1/decisions", headers=headers, json={"evidence_ids": [evid]})
    second = http.post("/v1/decisions", headers=headers, json={"evidence_ids": [evid]})
    assert first.status_code == 200
    receipt = first.json()["receipt"]
    assert receipt["ots_status"] == "not_anchored"
    assert second.json()["receipt"]["id"] == receipt["id"]
    assert len(store.ledger) == 1
    checked = http.post(f"/v1/receipts/{receipt['id']}/verify", headers={"Authorization": "Bearer reader-token"})
    assert checked.json()["verified"] is True
    store.ledger[0]["body"] = {"decision_id": "tampered"}
    tampered = http.post(f"/v1/receipts/{receipt['id']}/verify", headers={"Authorization": "Bearer reader-token"})
    assert tampered.json()["verified"] is False


def test_prod_without_signing_key_writes_nothing():
    store = MemoryStore()
    http = client(store, env="prod", database_url="postgres", signing_key_path="")
    denied = http.post(
        "/v1/decisions",
        headers={"Authorization": "Bearer decision-token", "Idempotency-Key": "no-key"},
        json={"evidence_ids": ["ev_missing"]},
    )
    assert denied.status_code == 503
    assert store.decisions == {}


def test_snapshot_mismatch_is_rejected_before_insert():
    store = MemoryStore()
    http = client(store)
    now = _now()
    evid = http.post(
        "/v1/events",
        headers={"Authorization": "Bearer decision-token"},
        json={"source": "bitget-rest", "instrument_id": "NVDAUSDT", "event_type": "ticker", "event_time_utc": now, "fetched_at_utc": now, "payload": {"last": 10}},
    ).json()["evidence"]["id"]
    rejected = http.post(
        "/v1/decisions",
        headers={"Authorization": "Bearer decision-token", "Idempotency-Key": "bad-hash"},
        json={"evidence_ids": [evid], "input_snapshot_hash": "0" * 64},
    )
    assert rejected.status_code == 422
    assert store.decisions == {}


def test_reader_rate_limit():
    http = client()
    http.app.state.limiter.limit = 2
    headers = {"Authorization": "Bearer reader-token"}
    assert http.get("/v1/events", headers=headers).status_code == 200
    assert http.get("/v1/events", headers=headers).status_code == 200
    blocked = http.get("/v1/events", headers=headers)
    assert blocked.status_code == 429
    assert blocked.json()["error"]["retryable"] is True


def test_unknown_route_uses_error_schema():
    http = client()
    missing = http.get("/v1/missing")
    assert missing.status_code == 404
    assert set(missing.json()["error"]) == {"code", "message", "retryable"}


def test_decision_list_returns_each_rows_receipt_without_calling_the_model():
    store = MemoryStore()
    http = client(store)
    now = _now()
    ingested = http.post(
        "/v1/events",
        headers={"Authorization": "Bearer decision-token"},
        json={
            "source": "bitget-rest",
            "instrument_id": "NVDAUSDT",
            "event_type": "ticker",
            "event_time_utc": now,
            "fetched_at_utc": now,
            "payload": {"last": 100.0},
            "mapping_confidence": 1.0,
        },
    )
    created = http.post(
        "/v1/decisions",
        headers={"Authorization": "Bearer decision-token", "Idempotency-Key": "list-one"},
        json={"evidence_ids": [ingested.json()["evidence"]["id"]]},
    )
    assert created.status_code == 200
    decision = created.json()["decision"]
    receipt = created.json()["receipt"]
    listed = http.get("/v1/decisions?limit=5", headers={"Authorization": "Bearer reader-token"})
    assert listed.status_code == 200
    item = listed.json()["items"][0]
    assert item["id"] == decision["id"]
    assert item["model_called"] is False
    assert item["reason"] == "llm_unconfigured"
    assert item["receipt_id"] == (None if receipt is None else receipt["id"])
    assert "evidence_ids" not in item


def test_logs_redact_bearer(caplog):
    import logging

    caplog.set_level(logging.INFO)
    http = client()
    http.get("/v1/events", headers={"Authorization": "Bearer reader-token"})
    text = caplog.text
    assert "reader-token" not in text
