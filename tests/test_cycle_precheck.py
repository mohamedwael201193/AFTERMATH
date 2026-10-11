"""Governor checks that do not depend on the model run before any model call."""

import json as jsonlib
from datetime import datetime, timedelta, timezone

from aftermath_api.config import Settings
from aftermath_api.cycle import run_paper_cycle
from aftermath_api.sources.warmup import store_warmup, warmup_event
from aftermath_api.store import MemoryStore


def _settings():
    return Settings(
        env="test", database_url="", direct_url="", llm_api_key="x", llm_base_url="https://example.test/v1",
        llm_model="m", llm_configured=True, reader_token="r", decision_token="d", job_token="j",
        signing_key_path="", sec_user_agent="", web_origin="", decisions="model",
    )


def _book():
    now = datetime.now(timezone.utc).isoformat()
    return {
        "source": "bitget-rest", "instrument_id": "NVDAUSDT", "event_type": "book",
        "event_time_utc": now, "fetched_at_utc": now,
        "payload": {
            "bid": 100.0, "ask": 100.02, "mid": 100.01, "spread_bp": 2.0, "depth_usdt": 50000.0,
            "bids": [[100.0, 10.0]], "asks": [[100.02, 10.0]],
        },
        "mapping_confidence": 1.0,
    }


def _filing():
    now = datetime.now(timezone.utc).isoformat()
    return {
        "source": "sec-edgar", "instrument_id": "NVDAUSDT", "event_type": "filing",
        "event_time_utc": now, "fetched_at_utc": now,
        "payload": {
            "form": "8-K", "items": "2.02", "qualifies": True, "accession": "precheck-2.02",
            "document_sha256": "e" * 64, "excerpt": "Item 2.02 results of operations.", "excerpt_untrusted": True,
        },
        "mapping_confidence": 1.0,
    }


def _market(r2, session=0.2):
    def fetch(_symbol, _now):
        fetch.calls += 1
        return {
            "contract": {"status": "normal", "is_rwa": "YES", "taker_fee_rate": 0.0006},
            "n_precedents": 4,
            "hedge_r2": r2,
            "hedge_r2_all_hours": r2,
            "hedge_r2_session": session,
            "hedge_beta": 0.9,
        }

    fetch.calls = 0
    return fetch


def _transport():
    def transport(_url, json=None, headers=None, timeout=None):
        transport.calls += 1
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

    transport.calls = 0
    return transport


def test_precheck_refusal_spends_no_budget():
    transport = _transport()
    market = _market(0.144)
    store = MemoryStore()
    result = run_paper_cycle(
        _settings(), store, fetch=lambda: ([_book()], []), event_fetch=lambda: [_filing()],
        model_transport=transport, market_fetch=market,
    )
    assert result["reason"] == "governor_precheck:hedge_fit_ok"
    assert transport.calls == 0
    assert market.calls == 1
    assert store.latest_run()["detail"]["model_calls"] == 0
    assert store.latest_run()["detail"]["precheck"]["hedge_r2_all_hours"] == 0.144
    assert store.fills == {}


def test_nvda_passes_precheck_one_call():
    transport = _transport()
    market = _market(0.42, session=0.31)
    store = MemoryStore()
    result = run_paper_cycle(
        _settings(), store, fetch=lambda: ([_book()], []), event_fetch=lambda: [_filing()],
        model_transport=transport, market_fetch=market,
    )
    assert result["reason"] == "awaiting_next_book"
    assert transport.calls == 1
    assert market.calls == 1
    assert store.latest_run()["detail"]["model_calls"] == 1
    assert store.latest_run()["detail"]["precheck"]["hedge_r2_session"] == 0.31


def test_other_symbol_precedents_do_not_qualify_nvda():
    now = datetime.now(timezone.utc)
    store = MemoryStore()
    for index in range(3):
        event = warmup_event(
            symbol="AAPLUSDT", accession=f"aapl-{index}", event_time=now - timedelta(days=40 + index), now=now,
            stock_before=100, stock_after=101, ref_before=400, ref_after=400,
        )
        assert store_warmup(store, event) is True
    assert store.count_reactions() == 3
    assert store.count_reactions("AAPLUSDT") == 3
    assert store.count_reactions("NVDAUSDT") == 0

    def market(_symbol, _now):
        return {
            "contract": {"status": "normal", "is_rwa": "YES", "taker_fee_rate": 0.0006},
            "n_precedents": store.count_reactions("NVDAUSDT"),
            "hedge_r2": 0.42,
            "hedge_beta": 0.9,
        }

    def transport(*_a, **_k):
        raise AssertionError("NVDA has no precedents of its own")

    result = run_paper_cycle(
        _settings(), store, fetch=lambda: ([_book()], []), event_fetch=lambda: [_filing()],
        model_transport=transport, market_fetch=market,
    )
    assert result["reason"] == "governor_precheck:precedents_ok"
    assert store.latest_run()["detail"]["model_calls"] == 0
