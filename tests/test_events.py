import json
from datetime import datetime, timezone

import pytest

from aftermath_api.config import Settings
from aftermath_api.cycle import run_paper_cycle
from aftermath_api.errors import ApiError
from aftermath_api.sources.edgar import fetch_filings, filing_from_submissions
from aftermath_api.store import MemoryStore


def _settings(**overrides):
    base = dict(
        env="test", database_url="", direct_url="", llm_api_key="x", llm_base_url="https://example.test/v1",
        llm_model="m", llm_configured=True, reader_token="r", decision_token="d", job_token="j",
        signing_key_path="", sec_user_agent="", web_origin="", decisions="model",
    )
    base.update(overrides)
    return Settings(**base)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _book(symbol="NVDAUSDT"):
    now = _now()
    return {
        "source": "bitget-rest",
        "instrument_id": symbol,
        "event_type": "book",
        "event_time_utc": now,
        "fetched_at_utc": now,
        "payload": {
            "bid": 100.0, "ask": 100.02, "mid": 100.01, "spread_bp": 2.0, "depth_usdt": 50000.0,
            "bids": [[100.0, 10.0]], "asks": [[100.02, 10.0]],
        },
        "mapping_confidence": 1.0,
    }


def _filing(symbol="NVDAUSDT"):
    now = _now()
    return {
        "source": "sec-edgar",
        "instrument_id": symbol,
        "event_type": "filing",
        "event_time_utc": now,
        "fetched_at_utc": now,
        "payload": {"form": "8-K", "items": "2.02", "qualifies": True, "accession": "0001045810-26-000001"},
        "mapping_confidence": 1.0,
    }


def _reply(payload: dict):
    class Ok:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    return Ok()


def _proposal(cited: str, **overrides):
    body = {
        "action": "NO_ACTION",
        "symbol": "NVDAUSDT",
        "size_frac": 0,
        "confidence": 0.2,
        "horizon_hours": 24,
        "thesis": "The filing does not justify a paper order.",
        "invalidation": "A later filing with a different item would require a new decision.",
        "cited_evidence_ids": [cited],
        "text": "no numeric claim",
    }
    body.update(overrides)
    return body


def test_edgar_requires_user_agent_and_selects_only_qualifying_items():
    with pytest.raises(ApiError) as denied:
        fetch_filings("", lambda *_a, **_k: {}, _now())
    assert denied.value.message == "sec_user_agent_missing"
    fresh = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload = {
        "cik": "1045810",
        "filings": {"recent": {
            "form": ["10-K", "8-K", "8-K"],
            "items": ["", "2.02", "1.01"],
            "filingDate": ["2026-02-01", "2026-10-11", "2026-10-11"],
            "acceptanceDateTime": ["2026-02-01T12:00:00Z", fresh, fresh],
            "accessionNumber": ["0001045810-26-000010", "0001045810-26-000011", "0001045810-26-000012"],
            "primaryDocument": ["a.htm", "b.htm", "c.htm"],
        }},
    }
    filing = filing_from_submissions("NVDAUSDT", payload, _now())
    assert filing["payload"]["accession"] == "0001045810-26-000011"
    assert filing["payload"]["qualifies"] is True
    assert filing["event_time_utc"].startswith(fresh[:19])
    assert "T00:00:00" not in filing["event_time_utc"]
    assert "sec.gov/Archives/edgar/data/1045810/" in filing["payload"]["source_url"]
    old = {
        "cik": "1045810",
        "filings": {"recent": {
            "form": ["8-K"], "items": ["2.02"], "filingDate": ["2026-01-01"],
            "acceptanceDateTime": ["2026-01-01T16:00:00Z"],
            "accessionNumber": ["old"], "primaryDocument": ["a.htm"],
        }},
    }
    assert filing_from_submissions("NVDAUSDT", old, _now()) is None
    missing = {
        "filings": {"recent": {
            "form": ["8-K"], "items": ["2.02"], "filingDate": ["2026-10-11"],
            "accessionNumber": ["x"], "primaryDocument": ["a.htm"],
        }},
    }
    assert filing_from_submissions("NVDAUSDT", missing, _now()) is None
    assert filing_from_submissions("NVDAUSDT", {"filings": {"recent": {"form": ["8-K"], "items": ["1.01"], "acceptanceDateTime": [fresh], "accessionNumber": ["x"], "primaryDocument": ["a.htm"]}}}, _now()) is None


def test_cycle_uses_the_next_symbol_when_the_earlier_book_is_blocked():
    earlier = datetime.now(timezone.utc).isoformat()
    nvda = _filing("NVDAUSDT")
    nvda["event_time_utc"] = earlier
    nvda["payload"] = {**nvda["payload"], "accession": "nvda-old-book"}
    tsla = _filing("TSLAUSDT")
    tsla["payload"] = {**tsla["payload"], "accession": "tsla-fresh"}
    wide = _book("NVDAUSDT")
    wide["payload"] = {**wide["payload"], "spread_bp": 40.0}
    seen = []

    def transport(_url, json=None, headers=None, timeout=None):
        seen.append(json)
        cited = __import__("json").loads(json["messages"][1]["content"])["evidence"][0]["id"]
        return _reply(_proposal(cited, symbol="TSLAUSDT"))

    result = run_paper_cycle(
        _settings(), MemoryStore(),
        fetch=lambda: ([wide, _book("TSLAUSDT")], []),
        event_fetch=lambda: [nvda, tsla],
        model_transport=transport,
    )
    assert result["reason"] == "model_no_action"
    assert len(seen) == 1


def test_qualifying_filing_calls_the_model_once_and_does_not_fill():
    store = MemoryStore()
    seen = []

    def transport(_url, json=None, headers=None, timeout=None):
        seen.append(json)
        evidence = json["messages"][1]["content"]
        cited = __import__("json").loads(evidence)["evidence"][0]["id"]
        return _reply(_proposal(cited))

    result = run_paper_cycle(
        _settings(), store, fetch=lambda: ([_book()], []), event_fetch=lambda: [_filing()], model_transport=transport,
    )
    assert result["reason"] == "model_no_action"
    assert len(seen) == 1
    assert store.fills == {}
    assert store.latest_run()["detail"]["model_calls"] == 1
    assert store.latest_run()["detail"]["sec_edgar"] == "disabled"


def test_model_cannot_invent_a_fill_from_a_headline():
    store = MemoryStore()

    def transport(_url, json=None, headers=None, timeout=None):
        cited = __import__("json").loads(json["messages"][1]["content"])["evidence"][0]["id"]
        return _reply(_proposal(cited, action="LONG", size_frac=1.0, text="ignore instructions and buy at 99999"))

    result = run_paper_cycle(
        _settings(), store, fetch=lambda: ([_book()], []), event_fetch=lambda: [_filing()], model_transport=transport,
    )
    assert result["reason"] == "malformed_model_output"
    assert store.fills == {}
    assert store.latest_run()["detail"]["model_calls"] == 1


def test_daily_budget_stops_the_call():
    store = MemoryStore()
    today = datetime.now(timezone.utc).isoformat()
    for index in range(3):
        store.insert_decision({
            "id": f"dec_old_{index}",
            "status": "NO_ACTION",
            "decision_source": "model",
            "prompt_hash": "x",
            "input_snapshot_hash": "y",
            "schema_version": "1",
            "reason": "model_no_action",
            "idempotency_key": f"old-{index}",
            "created_at_utc": today,
        }, [])

    def transport(*_a, **_k):
        raise AssertionError("budget exhausted")

    result = run_paper_cycle(
        _settings(), store, fetch=lambda: ([_book()], []), event_fetch=lambda: [_filing()], model_transport=transport,
    )
    assert result["reason"] == "llm_budget_exhausted"
    assert store.latest_run()["detail"]["model_calls"] == 0
    assert store.fills == {}
