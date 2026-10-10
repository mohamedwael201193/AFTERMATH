import os
from datetime import datetime, timedelta, timezone

import pytest

from aftermath_api.config import Settings
from aftermath_api.connectors import closed_candles, contract_from_record, funding_from_record, hedge_fit, market_from_public
from aftermath_api.cycle import run_paper_cycle
from aftermath_api.errors import ApiError
from aftermath_api.execution_context import derive_execution
from aftermath_api.positions import lifecycle_intact
from aftermath_api.store import MemoryStore


def _book_event():
    now = datetime.now(timezone.utc)
    return {
        "instrument_id": "NVDAUSDT",
        "event_type": "book",
        "event_time_utc": now.isoformat(),
        "fetched_at_utc": now.isoformat(),
        "payload": {
            "bid": 100.0, "ask": 100.02, "mid": 100.01, "spread_bp": 2.0, "depth_usdt": 50000.0,
            "bids": [[100.0, 10.0]], "asks": [[100.02, 10.0]],
        },
    }


def _proposal():
    return {"action": "LONG", "symbol": "NVDAUSDT", "size_frac": 0.05, "confidence": 0.8, "horizon_hours": 24}


def test_event_age_uses_filing_acceptance_not_the_book_clock():
    book = _book_event()
    accepted = datetime.now(timezone.utc) - timedelta(minutes=40)
    filing = {
        "instrument_id": "NVDAUSDT",
        "event_type": "filing",
        "event_time_utc": accepted.isoformat(),
        "fetched_at_utc": book["fetched_at_utc"],
        "payload": {"qualifies": True, "accession": "acc"},
    }
    derived = derive_execution(_proposal(), [filing, book], "model")
    assert derived["error"] is None
    assert derived["context"]["event_age_min"] == pytest.approx(40, abs=0.2)
    assert derived["context"]["hedge_r2"] is None


def test_incomplete_market_is_not_zero_filled():
    derived = derive_execution(_proposal(), [_book_event()], "model", market={"n_precedents": 0})
    assert derived["error"].startswith("incomplete_market:")
    assert "hedge_r2" in derived["error"]
    assert "contract" in derived["error"]


def test_complete_market_and_kill_switch_are_visible():
    market = {
        "contract": {"status": "normal", "is_rwa": "YES", "taker_fee_rate": 0.0004},
        "n_precedents": 4,
        "hedge_r2": 0.42,
        "hedge_beta": 1.1,
        "n_open": 1,
        "open_symbols": ["TSLAUSDT"],
    }
    os.environ["AFTERMATH_KILL"] = "1"
    try:
        derived = derive_execution(_proposal(), [_book_event()], "model", market=market)
    finally:
        os.environ.pop("AFTERMATH_KILL", None)
    assert derived["error"] is None
    assert derived["fee_rate"] == pytest.approx(0.0004)
    assert derived["context"]["n_precedents"] == 4
    assert derived["context"]["hedge_r2"] == pytest.approx(0.42)
    assert derived["context"]["emergency_stop"] is True
    assert derived["context"]["open_symbols"] == ["TSLAUSDT"]


def test_contract_candles_and_funding_reject_bad_payloads():
    with pytest.raises(ApiError):
        contract_from_record({"data": [{"symbol": "NVDAUSDT", "symbolStatus": "normal", "isRwa": "YES"}]}, "NVDAUSDT")
    parsed = contract_from_record(
        {"data": [{"symbol": "NVDAUSDT", "symbolStatus": "normal", "isRwa": "YES", "takerFeeRate": "0.0006"}], "sha256": "abc"},
        "NVDAUSDT",
    )
    assert parsed["is_rwa"] == "YES"
    end = 3_600_000 * 3
    rows = closed_candles({"data": [[0, 1, 1, 1, 10, 1, 1], [end, 1, 1, 1, 11, 1, 1]]}, end)
    assert rows == [[0, 10.0]]
    with pytest.raises(ApiError):
        funding_from_record({"data": [{}]}, "NVDAUSDT")
    assert funding_from_record({"data": [{"fundingRate": "0.0001"}]}, "NVDAUSDT")["funding_rate"] == pytest.approx(0.0001)


def _settings():
    return Settings(
        env="test", database_url="", direct_url="", llm_api_key="x", llm_base_url="https://example.test/v1",
        llm_model="m", llm_configured=True, reader_token="r", decision_token="d", job_token="j",
        signing_key_path="", sec_user_agent="", web_origin="", decisions="model",
    )


def _complete_market(_symbol, _now):
    return {
        "contract": {"status": "normal", "is_rwa": "YES", "taker_fee_rate": 0.0006},
        "n_precedents": 4,
        "hedge_r2": 0.4,
        "hedge_beta": 0.9,
    }


def test_fixed_size_proposal_waits_for_a_later_book_when_the_market_is_complete():
    now = datetime.now(timezone.utc).isoformat()
    book = {
        "source": "bitget-rest", "instrument_id": "NVDAUSDT", "event_type": "book",
        "event_time_utc": now, "fetched_at_utc": now,
        "payload": {
            "bid": 100.0, "ask": 100.02, "mid": 100.01, "spread_bp": 2.0, "depth_usdt": 50000.0,
            "bids": [[100.0, 10.0]], "asks": [[100.02, 10.0]],
        },
        "mapping_confidence": 1.0,
    }
    filing = {
        "source": "sec-edgar", "instrument_id": "NVDAUSDT", "event_type": "filing",
        "event_time_utc": now, "fetched_at_utc": now,
        "payload": {"form": "8-K", "items": "2.02", "qualifies": True, "accession": "fresh-2.02"},
        "mapping_confidence": 1.0,
    }

    def transport(_url, json=None, headers=None, timeout=None):
        import json as jsonlib
        cited = jsonlib.loads(json["messages"][1]["content"])["evidence"][0]["id"]
        body = {
            "action": "LONG", "symbol": "NVDAUSDT", "size_frac": 0.09, "confidence": 0.8,
            "horizon_hours": 48, "thesis": "The filing supports a paper long.",
            "invalidation": "A later book that removes the residual ends the idea.",
            "cited_evidence_ids": [cited], "text": "no numeric claim",
        }

        class Ok:
            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": jsonlib.dumps(body)}}]}

        return Ok()

    store = MemoryStore()
    result = run_paper_cycle(
        _settings(), store, fetch=lambda: ([book], []), event_fetch=lambda: [filing],
        model_transport=transport, market_fetch=_complete_market,
    )
    assert result["reason"] == "awaiting_next_book"
    fill = next(iter(store.fills.values()))
    assert fill["status"] == "PENDING_ENTRY"
    assert fill["cost_json"]["notional"] == pytest.approx(500)
    assert fill["cost_json"]["horizon_hours"] == 24
    assert lifecycle_intact(store, fill["id"])
    fill["cost_json"] = {**fill["cost_json"], "notional": 1}
    assert lifecycle_intact(store, fill["id"]) is False


class _Public:
    def contract(self, symbol):
        return {"status": "normal", "is_rwa": "YES", "taker_fee_rate": 0.0005, "symbol": symbol}

    def candles(self, symbol, *, end_ms, limit=1000):
        count = 40 if limit >= 40 else 5
        return [[index * 3_600_000, 100 * (1.001 ** index)] for index in range(count)]


def test_public_market_context_uses_the_reference_and_refuses_a_short_history():
    built = market_from_public(_Public(), "NVDAUSDT", 40 * 3_600_000, 4)
    assert built["contract"]["is_rwa"] == "YES"
    assert built["reference"] == "QQQUSDT"
    assert built["n_precedents"] == 4
    assert built["hedge_r2"] == pytest.approx(1.0, abs=1e-6)

    class Short(_Public):
        def candles(self, symbol, *, end_ms, limit=1000):
            return [[index * 3_600_000, 100.0] for index in range(5)]

    assert market_from_public(Short(), "NVDAUSDT", 1, 4) is None


def test_non_test_cycle_loads_public_market_context(monkeypatch):
    def fake(_connector, symbol, _end_ms, precedents):
        assert symbol == "NVDAUSDT"
        assert precedents == 0
        return _complete_market(symbol, None)

    monkeypatch.setattr("aftermath_api.connectors.market_from_public", fake)
    now = datetime.now(timezone.utc).isoformat()
    book = {
        "source": "bitget-rest", "instrument_id": "NVDAUSDT", "event_type": "book",
        "event_time_utc": now, "fetched_at_utc": now,
        "payload": {
            "bid": 100.0, "ask": 100.02, "mid": 100.01, "spread_bp": 2.0, "depth_usdt": 50000.0,
            "bids": [[100.0, 10.0]], "asks": [[100.02, 10.0]],
        },
        "mapping_confidence": 1.0,
    }
    filing = {
        "source": "sec-edgar", "instrument_id": "NVDAUSDT", "event_type": "filing",
        "event_time_utc": now, "fetched_at_utc": now,
        "payload": {"form": "8-K", "items": "2.02", "qualifies": True, "accession": "ctx-2.02"},
        "mapping_confidence": 1.0,
    }

    def transport(_url, json=None, headers=None, timeout=None):
        import json as jsonlib
        cited = jsonlib.loads(json["messages"][1]["content"])["evidence"][0]["id"]
        body = {
            "action": "LONG", "symbol": "NVDAUSDT", "size_frac": 0.05, "confidence": 0.8,
            "horizon_hours": 24, "thesis": "The filing supports a paper long.",
            "invalidation": "A later book that removes the residual ends the idea.",
            "cited_evidence_ids": [cited], "text": "no numeric claim",
        }

        class Ok:
            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": jsonlib.dumps(body)}}]}

        return Ok()

    store = MemoryStore()
    dev = Settings(
        env="dev", database_url="", direct_url="", llm_api_key="x", llm_base_url="https://example.test/v1",
        llm_model="m", llm_configured=True, reader_token="r", decision_token="d", job_token="j",
        signing_key_path="", sec_user_agent="", web_origin="", decisions="model",
    )
    result = run_paper_cycle(
        dev, store, fetch=lambda: ([book], []), event_fetch=lambda: [filing], model_transport=transport,
    )
    assert result["reason"] == "awaiting_next_book"
    assert next(iter(store.fills.values()))["status"] == "PENDING_ENTRY"


def test_hedge_fit_drops_short_samples_instead_of_inventing_zero():
    short = [[hour * 3_600_000, 100 + hour] for hour in range(5)]
    assert hedge_fit(short, short)["hedge_r2"] is None
    symbol = [[hour * 3_600_000, 100 * (1.01 ** hour)] for hour in range(30)]
    reference = [[hour * 3_600_000, 50 * (1.01 ** hour)] for hour in range(30)]
    fit = hedge_fit(symbol, reference)
    assert fit["pairs"] == 29
    assert fit["hedge_r2"] == pytest.approx(1.0, abs=1e-9)
    assert fit["hedge_beta"] == pytest.approx(1.0, abs=1e-6)
