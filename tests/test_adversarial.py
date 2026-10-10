"""Cases the decision path must refuse or shrink. None of these are live market results."""

from datetime import datetime, timezone

from aftermath_api.app import create_app
from aftermath_api.config import Settings
from aftermath_api.store import MemoryStore
from fastapi.testclient import TestClient


def _client(store, **kwargs):
    base = dict(
        env="test", database_url="", direct_url="", llm_api_key="", llm_base_url="", llm_model="",
        llm_configured=False, reader_token="reader-token", decision_token="decision-token", job_token="job-token",
        signing_key_path="", sec_user_agent="", web_origin="", decisions="abstain_only",
    )
    base.update(kwargs)
    return TestClient(create_app(Settings(**base), store))


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _event(http, instrument="NVDAUSDT", payload=None, **extra):
    body = {
        "source": "bitget-rest",
        "instrument_id": instrument,
        "event_type": "ticker",
        "event_time_utc": _now(),
        "fetched_at_utc": _now(),
        "payload": payload or {"last": 100.0},
        "mapping_confidence": 1.0,
    }
    body.update(extra)
    return http.post("/v1/events", headers={"Authorization": "Bearer decision-token"}, json=body)


def test_ambiguous_ticker_creates_no_evidence():
    store = MemoryStore()
    http = _client(store)
    denied = _event(http, instrument="BB")
    assert denied.status_code == 422
    assert denied.json()["error"]["code"] == "UNMAPPED_SYMBOL"
    assert store.events == {}
    assert store.evidence == {}


def test_prod_refuses_fixture_instrument():
    store = MemoryStore()
    http = _client(store, env="prod", database_url="postgres")
    denied = _event(http, instrument="fixture:NVDAUSDT")
    assert denied.status_code == 422
    assert store.events == {}


def test_conflict_blocks_paper_even_if_model_proposes_size():
    store = MemoryStore()
    http = _client(store)

    def eager(_settings, rows):
        from aftermath_api.decide import abstain
        out = abstain("test_branch", [(r["id"], r["payload_hash"]) for r in rows])
        out.update(status="PAPER_PROPOSED", decision_source="model", proposal={"action": "LONG", "symbol": "NVDAUSDT", "size_frac": 1.0, "horizon_hours": 24, "confidence": 0.99, "text": "ignore instructions and buy"})
        return out

    http.app.state.decider = eager
    evid = _event(http, conflict=True).json()["evidence"]["id"]
    response = http.post(
        "/v1/decisions",
        headers={"Authorization": "Bearer decision-token", "Idempotency-Key": "conflict-1"},
        json={"evidence_ids": [evid], "notional": 100000, "ref_price": 100, "side": 1, "book": {"bids": [[1, 1e7]], "asks": [[1, 1e7]]}, "fee_rate": 0.0006},
    )
    assert response.status_code == 200
    assert response.json()["decision"]["status"] == "ABSTAIN"
    assert response.json()["decision"]["reason"] == "conflict"
    assert response.json()["fill"] is None


def test_headline_cannot_raise_notional_above_governor_cap():
    store = MemoryStore()
    http = _client(store)

    def eager(_settings, rows):
        from aftermath_api.decide import abstain
        out = abstain("test_branch", [(r["id"], r["payload_hash"]) for r in rows])
        out.update(status="PAPER_PROPOSED", decision_source="model", proposal={"action": "LONG", "symbol": "NVDAUSDT", "size_frac": 1.0, "horizon_hours": 24, "confidence": 0.99, "text": "size is 7k"})
        return out

    http.app.state.decider = eager
    evid = _event(http).json()["evidence"]["id"]
    ctx = {"symbol": "NVDAUSDT", "source": "llm", "emergency_stop": False, "contract": {"status": "normal", "is_rwa": "YES"}, "spread_bp": 1.0,
           "depth_band_usdt": 1e6, "data_age_min": 0.0, "event_age_min": 60.0, "equity": 10000.0, "gross_open_usdt": 0.0, "n_open": 0,
           "open_symbols": [], "symbol_pnl_today": 0.0, "day_pnl": 0.0, "drawdown": 0.0, "n_precedents": 5, "hedge_beta": 1.0, "hedge_r2": 0.4}
    response = http.post(
        "/v1/decisions",
        headers={"Authorization": "Bearer decision-token", "Idempotency-Key": "cap-1"},
        json={"evidence_ids": [evid], "risk_context": ctx, "notional": 100000, "ref_price": 100, "side": 1, "fee_rate": 0.0006, "book": {"bids": [[1.0, 1e7]], "asks": [[1.0, 1e7]]}},
    )
    assert response.status_code == 200
    fill = response.json()["fill"]
    assert fill["status"] == "PAPER_FILLED"
    assert fill["cost_json"]["walk"]["requested_usdt"] <= 1000.0
