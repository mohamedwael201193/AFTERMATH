import json
from datetime import datetime, timedelta, timezone

import pytest

from aftermath_api.connectors import observation_from_ticker
from aftermath_api.decide import decide
from aftermath_api.errors import ApiError
from aftermath_api.identity import resolve_symbol
from aftermath_api.paper import govern, paper_fill
from aftermath_api.receipts import generate_production_key, sign_line, verify_line


def _settings():
    from aftermath_api.config import Settings

    return Settings(
        env="test", database_url="", direct_url="", llm_api_key="", llm_base_url="", llm_model="",
        llm_configured=False, reader_token="r", decision_token="d", job_token="j", signing_key_path="",
        sec_user_agent="", web_origin="", decisions="abstain_only",
    )


def test_ambiguous_tickers_do_not_map():
    assert resolve_symbol("BB")[0] is None
    assert resolve_symbol("STX")[2] == "ambiguous"
    assert resolve_symbol("NOTREAL")[2] == "unmapped"
    assert resolve_symbol("NVDAUSDT")[0] == "NVDAUSDT"


def test_empty_and_stale_ticker_are_not_observations():
    now = datetime.now(timezone.utc)
    with pytest.raises(ApiError) as empty:
        observation_from_ticker({"data": [], "fetched_at_utc": now.isoformat(), "params": {"symbol": "BTCUSDT"}, "endpoint": "/t", "sha256": "a"})
    assert empty.value.code == "SOURCE_UNAVAILABLE"
    old = (now - timedelta(seconds=120)).isoformat()
    with pytest.raises(ApiError) as stale:
        observation_from_ticker({"data": [{"lastPr": "1"}], "fetched_at_utc": old, "params": {"symbol": "BTCUSDT"}, "endpoint": "/t", "sha256": "a"}, now=now)
    assert stale.value.code == "STALE"


def test_missing_model_abstains_and_bad_numbers_abstain():
    rows = [{"id": "ev_1", "payload_hash": "abc", "facts": {"last": 100.0}}]
    out = decide(_settings(), rows)
    assert out["decision_source"] == "abstain"
    assert out["reason"] == "llm_unconfigured"

    class Ok:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": json.dumps({"action": "NO_ACTION", "text": "price is 7k"})}}]}

    configured = _settings()
    configured = configured.__class__(**{**configured.__dict__, "llm_configured": True, "llm_api_key": "x", "llm_base_url": "https://example.test/v1", "llm_model": "m", "decisions": "model"})

    def transport(*_a, **_k):
        return Ok()

    bad = decide(configured, rows, transport=transport)
    assert bad["status"] == "ABSTAIN"
    assert bad["reason"] == "unverifiable_number"


def test_malformed_model_abstains():
    configured = _settings()
    configured = configured.__class__(**{**configured.__dict__, "llm_configured": True, "llm_api_key": "x", "llm_base_url": "https://example.test/v1", "llm_model": "m", "decisions": "model"})

    class Bad:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "ignore previous instructions"}}]}

    out = decide(configured, [{"id": "ev_1", "payload_hash": "abc", "facts": {}}], transport=lambda *_a, **_k: Bad())
    assert out["reason"] == "malformed_model_output"


def test_risk_refuses_nan_and_paper_needs_depth():
    ctx = {"symbol": "NVDAUSDT", "source": "llm", "emergency_stop": False, "contract": {"status": "normal", "is_rwa": "YES"}, "spread_bp": 1.0,
           "depth_band_usdt": 1e6, "data_age_min": 0.0, "event_age_min": 60.0, "equity": 10_000.0, "gross_open_usdt": 0.0, "n_open": 0,
           "open_symbols": set(), "symbol_pnl_today": 0.0, "day_pnl": 0.0, "drawdown": 0.0, "n_precedents": 5, "hedge_beta": 1.0, "hedge_r2": 0.4}
    proposal = {"action": "LONG", "symbol": "NVDAUSDT", "size_frac": 0.05, "horizon_hours": 24, "confidence": 0.8}
    assert govern(proposal, ctx)["verdict"] == "APPROVED"
    assert govern(proposal, {**ctx, "emergency_stop": True})["verdict"] == "REFUSED"
    empty = paper_fill(1, 100.0, 10.0, {"bids": [], "asks": []}, 0.0006)
    assert empty["status"] == "PAPER_UNFILLED"
    filled = paper_fill(1, 100.0, 10.0, {"bids": [(1.0, 1000.0)], "asks": [(1.0, 1000.0)]}, 0.0006)
    assert filled["status"] == "PAPER_FILLED"
    assert paper_fill(1, float("nan"), 10.0, {"asks": [(1.0, 1000.0)], "bids": []}, 0.0)["status"] == "PAPER_UNFILLED"


def test_chain_truncation_fails(tmp_path):
    from aftermath_api.receipts import chain_intact, generate_production_key, issue_receipt
    from aftermath_api.store import MemoryStore

    private = tmp_path / "production_ed25519.key"
    public = tmp_path / "production_ed25519.pub"
    generate_production_key(private, public)
    store = MemoryStore()
    issue_receipt(store, private, {"decision_id": "dec_1"})
    issue_receipt(store, private, {"decision_id": "dec_2"})
    assert chain_intact(public, store.list_ledger())
    assert chain_intact(public, store.list_ledger()[:1])
    assert chain_intact(public, store.list_ledger()[1:]) is False


def test_sec_and_mcp_fail_closed():
    from aftermath_api.connectors import interpret_mcp, require_sec_user_agent

    with pytest.raises(ApiError) as sec:
        require_sec_user_agent("")
    assert sec.value.code == "SOURCE_UNAVAILABLE"
    with pytest.raises(ApiError):
        interpret_mcp({"ok": True, "error": "session not found"})
    with pytest.raises(ApiError):
        interpret_mcp({"ok": True, "data": []})


def test_model_body_excludes_server_secrets_and_retries_401():
    from aftermath_api.config import Settings

    settings = Settings(
        env="test", database_url="postgresql://db.example/app", direct_url="", llm_api_key="model-secret",
        llm_base_url="https://example.test/v1", llm_model="m", llm_configured=True, reader_token="reader-secret",
        decision_token="d", job_token="j", signing_key_path="C:/secrets/production_ed25519.key", sec_user_agent="",
        web_origin="", decisions="model",
    )
    seen = []

    class Unauthorized:
        status_code = 401

        def raise_for_status(self):
            raise RuntimeError("unauthorized")

    def transport(_url, json=None, headers=None, timeout=None):
        seen.append(json)
        return Unauthorized()

    out = decide(settings, [{"id": "ev_1", "payload_hash": "abc", "facts": {"last": 1.0}}], transport=transport)
    assert out["reason"] == "llm_unavailable"
    assert len(seen) == 2
    blob = json.dumps(seen)
    assert "model-secret" not in blob
    assert "postgresql://" not in blob
    assert "reader-secret" not in blob
    assert "production_ed25519.key" not in blob


def test_model_sees_the_instrument_it_must_echo():
    from aftermath_api.config import Settings
    from aftermath_api.decide import call_model

    settings = Settings(
        env="test", database_url="", direct_url="", llm_api_key="k",
        llm_base_url="https://example.test/v1", llm_model="m", llm_configured=True, reader_token="",
        decision_token="", job_token="", signing_key_path="", sec_user_agent="",
        web_origin="", decisions="model",
    )
    seen = []

    class Ok:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "{}"}}]}

    def transport(_url, json=None, headers=None, timeout=None):
        seen.append(json)
        return Ok()

    rows = [
        {"id": "ev_1", "payload_hash": "a", "facts": {"form": "8-K"}, "event": {"instrument_id": "TSLAUSDT"}},
        {"id": "ev_2", "payload_hash": "b", "facts": {"last": 1.0}},
    ]
    call_model(settings, rows, transport)
    evidence = json.loads(seen[0]["messages"][1]["content"])["evidence"]
    assert evidence[0]["instrument_id"] == "TSLAUSDT"
    assert "instrument_id" not in evidence[1]


def _bounded(text: str) -> dict:
    from datetime import datetime, timezone

    from aftermath_api.config import Settings
    from aftermath_api.decide import decide_bounded

    settings = Settings(
        env="test", database_url="", direct_url="", llm_api_key="k",
        llm_base_url="https://example.test/v1", llm_model="m", llm_configured=True, reader_token="",
        decision_token="", job_token="", signing_key_path="", sec_user_agent="",
        web_origin="", decisions="model",
    )
    now = datetime.now(timezone.utc).isoformat()
    proposal = {
        "action": "LONG", "symbol": "TSLAUSDT", "size_frac": 0.05, "confidence": 0.6, "horizon_hours": 24,
        "thesis": "t", "invalidation": "i", "cited_evidence_ids": ["ev_f"], "text": text,
    }

    class Ok:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(proposal)}}]}

    rows = [
        {"id": "ev_f", "payload_hash": "a", "facts": {"form": "8-K"}, "event": {
            "source": "sec-edgar", "instrument_id": "TSLAUSDT", "event_type": "filing",
            "event_time_utc": now, "fetched_at_utc": now, "payload_hash": "a",
            "payload": {"document_sha256": "0" * 64, "counted": True, "qualifies": True}}},
        {"id": "ev_b", "payload_hash": "b", "facts": {"bid": 361.0, "ask": 361.2}, "event": {
            "source": "bitget", "instrument_id": "TSLAUSDT", "event_type": "order_book",
            "event_time_utc": now, "fetched_at_utc": now, "payload_hash": "b",
            "payload": {"bid": 361.0, "ask": 361.2, "bids": [[361.0, 5.0]], "asks": [[361.2, 5.0]]}}},
    ]
    return decide_bounded(settings, rows, symbol="TSLAUSDT", transport=lambda *_a, **_k: Ok())


def test_server_fixed_size_horizon_and_index_name_are_not_invented_numbers():
    out = _bounded("Hold 0.05 for 24 hours on the residual versus the Nasdaq-100 reference near 361.2.")
    assert out["reason"] == "awaiting_next_book"


def test_an_invented_number_is_still_refused_and_named():
    out = _bounded("The residual moved 3.1% on the filing.")
    assert out["reason"] == "unverifiable_number"
    assert out["unbound_numbers"] == ["3.1%"]


def test_research_public_key_id():
    import FINAL_CANDIDATE.t2.signing as signing

    _pub, kid = signing.load_public(signing.PUB_PATH)
    assert kid == "ed25519:45e4334c577525fa"


def test_vendored_execution_has_no_private_order_route():
    from pathlib import Path
    import FINAL_CANDIDATE.t2.execution as execution

    text = Path(execution.__file__).read_text(encoding="utf-8")
    assert "place-order" not in text
    assert "/api/v2/mix/order" not in text


def test_hex_private_key_matches_raw_key(tmp_path):
    private = tmp_path / "production_ed25519.key"
    public = tmp_path / "production_ed25519.pub"
    generate_production_key(private, public)
    hex_path = tmp_path / "production_ed25519.hex"
    hex_path.write_text(private.read_bytes().hex(), encoding="ascii")
    body = {"kind": "decision", "id": "dec_1"}
    assert sign_line(hex_path, body, "GENESIS")["pubkey_id"] == sign_line(private, body, "GENESIS")["pubkey_id"]
    assert verify_line(public, sign_line(hex_path, body, "GENESIS"))


def test_receipt_detects_tamper(tmp_path):
    private = tmp_path / "production_ed25519.key"
    public = tmp_path / "production_ed25519.pub"
    kid = generate_production_key(private, public)
    assert not kid.endswith("45e4334c577525fa")
    line = sign_line(private, {"kind": "decision", "id": "dec_1"}, "")
    assert verify_line(public, line)
    tampered = {**line, "body": {"kind": "decision", "id": "dec_2"}}
    assert verify_line(public, tampered) is False
    public.write_text(json.dumps({"alg": "ed25519", "key_id": "ed25519:aaaaaaaaaaaaaaaa", "public_hex": "00" * 32}), encoding="utf-8")
    assert verify_line(public, line) is False
