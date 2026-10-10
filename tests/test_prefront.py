"""Release-gate checks for the pre-frontend decision path. These are offline fixtures."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from aftermath_api.app import create_app
from aftermath_api.config import Settings
from aftermath_api.paper import govern
from aftermath_api.store import MemoryStore


def _settings(**kwargs):
    base = dict(
        env="test", database_url="", direct_url="", llm_api_key="", llm_base_url="", llm_model="",
        llm_configured=False, reader_token="reader-token", decision_token="decision-token", job_token="job-token",
        signing_key_path="", sec_user_agent="", web_origin="https://app.example", decisions="abstain_only",
    )
    base.update(kwargs)
    return Settings(**base)


def _http(store=None, **kwargs):
    return TestClient(create_app(_settings(**kwargs), store or MemoryStore()))


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _ingest(http, **extra):
    body = {
        "source": "bitget-rest",
        "instrument_id": "NVDAUSDT",
        "event_type": "ticker",
        "event_time_utc": _now(),
        "fetched_at_utc": _now(),
        "payload": {"last": 100.0},
        "mapping_confidence": 1.0,
    }
    body.update(extra)
    return http.post("/v1/events", headers={"Authorization": "Bearer decision-token"}, json=body)


def test_security_headers_and_role_separation():
    http = _http()
    health = http.get("/health")
    assert health.headers["x-content-type-options"] == "nosniff"
    assert health.headers["cache-control"] == "no-store"
    assert http.post("/internal/jobs/paper-cycle", headers={"Authorization": "Bearer decision-token"}).status_code == 403
    assert http.post("/v1/decisions", headers={"Authorization": "Bearer job-token", "Idempotency-Key": "job"}, json={"evidence_ids": ["x"]}).status_code == 403


def test_stale_and_missing_book_do_not_call_the_model():
    store = MemoryStore()
    http = _http(store, llm_configured=True, llm_api_key="x", llm_base_url="https://example.test/v1", llm_model="m", decisions="model")
    calls = []
    http.app.state.decider_calls = calls

    def explode(*_a, **_k):
        calls.append("model")
        raise AssertionError("model was called")

    http.app.state.decider = explode
    old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    stale = _ingest(http, event_time_utc=old, fetched_at_utc=old)
    stale_id = stale.json()["evidence"]["id"]
    refused = http.post("/v1/decisions", headers={"Authorization": "Bearer decision-token", "Idempotency-Key": "stale"}, json={"evidence_ids": [stale_id]})
    assert refused.json()["decision"]["reason"] == "stale_evidence"
    fresh = _ingest(http)
    missing = http.post(
        "/v1/decisions",
        headers={"Authorization": "Bearer decision-token", "Idempotency-Key": "nobook"},
        json={"evidence_ids": [fresh.json()["evidence"]["id"]]},
    )
    assert missing.json()["decision"]["reason"] == "missing_order_book"
    assert calls == []


def test_conflict_does_not_call_the_decider():
    http = _http()
    calls = []
    http.app.state.decider_calls = calls
    http.app.state.decider = lambda *_a, **_k: calls.append("called")
    evid = _ingest(http, conflict=True).json()["evidence"]["id"]
    response = http.post("/v1/decisions", headers={"Authorization": "Bearer decision-token", "Idempotency-Key": "c"}, json={"evidence_ids": [evid]})
    assert response.json()["decision"]["reason"] == "conflict"
    assert calls == []


def test_cycle_records_live_shape_refusal_without_a_fill(tmp_path):
    store = MemoryStore()
    private = tmp_path / "production_ed25519.key"
    from aftermath_api.receipts import generate_production_key

    generate_production_key(private, tmp_path / "production_ed25519.pub")
    http = _http(store, signing_key_path=str(private))
    now = _now()

    def fetch():
        return ([{
            "source": "bitget-rest",
            "instrument_id": "NVDAUSDT",
            "event_type": "ticker",
            "event_time_utc": now,
            "fetched_at_utc": now,
            "payload": {"last": 101.5},
            "mapping_confidence": 1.0,
        }], [])

    http.app.state.cycle_fetch = fetch
    headers = {"Authorization": "Bearer job-token"}
    first = http.post("/internal/jobs/paper-cycle", headers=headers)
    second = http.post("/internal/jobs/paper-cycle", headers=headers)
    assert first.status_code == 200
    assert first.json()["reason"] == "missing_order_book"
    assert first.json()["repeated"] is False
    assert second.json()["repeated"] is True
    assert second.json()["decision_id"] == first.json()["decision_id"]
    assert store.fills == {}
    assert store.latest_run()["detail"]["model_calls"] == 0
    status = http.get("/v1/ops/status", headers={"Authorization": "Bearer reader-token"})
    assert status.json()["latest_run"]["reason"] == "missing_order_book"
    metrics = http.get("/v1/metrics", headers={"Authorization": "Bearer reader-token"})
    assert metrics.json()["status"] == "INSUFFICIENT_DATA"
    assert metrics.json()["sample_size"] == 0
    receipt_id = first.json()["receipt_id"]
    checked = http.post(f"/v1/receipts/{receipt_id}/verify", headers={"Authorization": "Bearer reader-token"})
    assert checked.json()["verified"] is True
    replay = http.post(f"/v1/receipts/{receipt_id}/replay", headers={"Authorization": "Bearer reader-token"})
    assert replay.json()["llm_reproduction"] == "not_available"
    assert replay.json()["anchor"] == "unconfirmed"
    line = http.get(f"/v1/receipts/{receipt_id}", headers={"Authorization": "Bearer reader-token"}).json()["line"]
    tampered = {**line, "body": {**line["body"], "status": "PAPER_FILLED"}}
    denied = http.post(f"/v1/receipts/{receipt_id}/verify", headers={"Authorization": "Bearer reader-token"}, json={"line": tampered})
    assert denied.json()["verified"] is False


def test_signing_failure_does_not_leave_a_successful_decision(tmp_path):
    store = MemoryStore()
    bad = tmp_path / "bad.key"
    bad.write_text("not-a-key", encoding="ascii")
    http = _http(store, signing_key_path=str(bad))
    evid = _ingest(http).json()["evidence"]["id"]
    response = http.post("/v1/decisions", headers={"Authorization": "Bearer decision-token", "Idempotency-Key": "bad-sign"}, json={"evidence_ids": [evid]})
    assert response.status_code == 503
    assert store.decisions == {}


def test_non_finite_size_is_refused_and_no_order_route_exists():
    ctx = {
        "symbol": "NVDAUSDT", "source": "llm", "emergency_stop": False,
        "contract": {"status": "normal", "is_rwa": "YES"}, "spread_bp": 1.0, "depth_band_usdt": 1e6,
        "data_age_min": 0.0, "event_age_min": 1.0, "equity": 10000.0, "gross_open_usdt": 0.0, "n_open": 0,
        "open_symbols": [], "symbol_pnl_today": 0.0, "day_pnl": 0.0, "drawdown": 0.0, "n_precedents": 5,
        "hedge_beta": 0.0, "hedge_r2": 0.4,
    }
    verdict = govern({"action": "LONG", "symbol": "NVDAUSDT", "size_frac": float("nan"), "horizon_hours": 24, "confidence": 0.8}, ctx)
    assert verdict["verdict"] == "REFUSED"
    root = Path(__file__).resolve().parents[1] / "src"
    text = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    assert "place-order" not in text
    assert "/api/v2/mix/order" not in text
    assert "withdraw" not in text


def test_reader_rate_limit_and_database_ping_failure(tmp_path):
    from aftermath_api.app import RateLimiter

    limiter = RateLimiter(limit=2)
    assert limiter.allow("reader", 1.0) is True
    assert limiter.allow("reader", 1.0) is True
    assert limiter.allow("reader", 1.0) is False
    key = tmp_path / "production_ed25519.key"
    key.write_bytes(b"\x00" * 32)

    class Dead(MemoryStore):
        def ping(self) -> bool:
            return False

    http = _http(Dead(), env="prod", database_url="postgres", signing_key_path=str(key))
    ready = http.get("/ready")
    assert ready.status_code == 503
    assert ready.json()["problems"] == ["database"]


def test_whitelist_matches_the_vendored_governor():
    import sys

    vendor = Path(__file__).resolve().parents[1] / "third_party" / "aftermath"
    sys.path.insert(0, str(vendor))
    from FINAL_CANDIDATE.t2.governor import WHITELIST

    from aftermath_api.cycle import WHITELIST as CYCLE

    assert set(CYCLE) == set(WHITELIST)
