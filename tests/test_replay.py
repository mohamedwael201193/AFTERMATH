import json as jsonlib
from datetime import datetime, timedelta, timezone

import pytest

import aftermath_api.cycle as cycle
import aftermath_api.gate as gate
import aftermath_api.receipts as receipts
from aftermath_api.receipts import chain_intact, generate_production_key, verify_line
from aftermath_api.replay import LookaheadError, run_historical_replay
from aftermath_api.store import MemoryStore, PostgresStore


def _book(when: str, digest: str, bid: float, ask: float, bids, asks):
    mid = (bid + ask) / 2
    return {
        "source": "bitget-history-candles",
        "instrument_id": "NVDAUSDT",
        "event_type": "book",
        "event_time_utc": when,
        "fetched_at_utc": when,
        "payload": {
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "spread_bp": (ask - bid) / mid * 1e4,
            "depth_usdt": 50000.0,
            "bids": bids,
            "asks": asks,
            "raw_sha256": digest,
        },
        "mapping_confidence": 1.0,
    }


def _filing(now: datetime):
    accepted = (now - timedelta(minutes=5)).isoformat()
    return {
        "source": "sec-edgar",
        "instrument_id": "NVDAUSDT",
        "event_type": "filing",
        "event_time_utc": accepted,
        "fetched_at_utc": now.isoformat(),
        "payload": {
            "form": "8-K",
            "items": "2.02",
            "qualifies": True,
            "counted": True,
            "accession": "0001045810-26-000073",
            "document_sha256": "d" * 64,
            "excerpt": "Item 2.02 results of operations.",
            "excerpt_untrusted": True,
        },
        "mapping_confidence": 1.0,
    }


def _market(**overrides):
    body = {
        "contract": {"status": "normal", "is_rwa": "YES", "taker_fee_rate": 0.0006, "funding_interval_hours": 8},
        "n_precedents": 4,
        "hedge_r2": 0.4,
        "hedge_beta": 0.9,
    }
    body.update(overrides)
    return body


def _transport(action: str):
    calls = {"n": 0}

    def transport(_url, json=None, headers=None, timeout=None):
        calls["n"] += 1
        evidence = jsonlib.loads(json["messages"][1]["content"])["evidence"]
        body = {
            "action": action,
            "symbol": "NVDAUSDT",
            "size_frac": 0.0 if action == "NO_ACTION" else 0.05,
            "confidence": 0.8,
            "horizon_hours": 24,
            "thesis": "The filing is the evidence for a paper long.",
            "invalidation": "A later book that removes the residual ends the idea.",
            "cited_evidence_ids": [row["id"] for row in evidence],
            "text": "The filing is the evidence for a paper long.",
        }

        class Ok:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": jsonlib.dumps(body)}}]}

        return Ok()

    transport.llm_model = "stub-historical-replay"
    transport.calls = calls
    return transport


def _books(now: datetime):
    proposed = now.isoformat()
    opened = (now + timedelta(hours=1)).isoformat()
    closed = (now + timedelta(hours=25, seconds=1)).isoformat()
    proposal = _book(proposed, "proposal-book", 99.99, 100.01, [[99.99, 10]], [[100.0, 10]])
    entry = _book(opened, "entry-book", 99.99, 100.01, [[99.99, 10]], [[100.0, 10]])
    exit_book = _book(closed, "exit-book", 100.99, 101.01, [[101.0, 10]], [[101.02, 10]])
    return proposal, entry, exit_book


def _run(tmp_path, action="LONG", market=None, books=None, funding_rates=None, store=None, transport=None):
    now = datetime(2026, 10, 2, 13, 9, 26, tzinfo=timezone.utc)
    proposal, entry, exit_book = _books(now)
    private = tmp_path / "replay_ed25519.key"
    public = tmp_path / "replay_ed25519.pub"
    generate_production_key(private, public)
    chosen = transport or _transport(action)
    if store is None:
        store = MemoryStore()
    report = run_historical_replay(
        _filing(now),
        now=now,
        books=list(books) if books is not None else [proposal, entry, exit_book],
        market_context=_market() if market is None else market,
        funding_rates=[0.0001, 0.0001, 0.0001] if funding_rates is None else funding_rates,
        model_transport=chosen,
        signing_path=str(private),
        store=store,
    )
    return report, store, public, chosen


def test_historical_replay_labels_receipts_fees_and_funding(tmp_path):
    original_issue = receipts.issue_receipt
    original_govern = cycle.govern
    original_clock = gate.datetime
    report, store, public, _transport_used = _run(tmp_path)
    assert gate.datetime is original_clock
    assert receipts.issue_receipt is original_issue
    assert cycle.govern is original_govern

    assert report["mode"] == "historical_replay"
    assert report["counted_outcome"] is False
    assert report["prospective"] is False
    assert report["store"] == "MemoryStore"
    assert report["outcome_bp"] == 84.94
    assert report["fees_usdt"] == 0.603
    assert report["funding_usdt"] == 0.15
    assert report["funding_source"] == "venue_funding"
    assert report["metrics"]["status"] == "INSUFFICIENT_DATA"
    assert report["chain_intact"] is True
    assert report["receipts_verify"]
    assert all(report["receipts_verify"])

    decision = store.get_decision(report["decision"]["id"])
    assert decision["mode"] == "historical_replay"
    assert decision["payload"]["mode"] == "historical_replay"
    assert decision["payload"]["counted_outcome"] is False
    assert decision["payload"]["prospective"] is False
    fill = store.list_fills()[0]
    assert fill["status"] == "CLOSED"
    assert fill["cost_json"]["mode"] == "historical_replay"
    assert fill["cost_json"]["counted_outcome"] is False
    for line in store.list_ledger():
        assert line["body"]["mode"] == "historical_replay"
        assert line["body"]["counted_outcome"] is False
        assert line["body"]["prospective"] is False
        assert verify_line(public, line) is True
    assert chain_intact(public, store.list_ledger())
    receipt = store.receipt_for_decision(decision["id"])
    tampered = {**receipt["line"], "body": {**receipt["line"]["body"], "status": "CLOSED"}}
    assert verify_line(public, tampered) is False
    assert type(store) is MemoryStore


def test_lookahead_rejects_an_entry_book_that_is_not_after_the_decision(tmp_path):
    now = datetime(2026, 10, 2, 13, 9, 26, tzinfo=timezone.utc)
    same = _book(now.isoformat(), "same-book", 99.99, 100.01, [[99.99, 10]], [[100.0, 10]])
    transport = _transport("LONG")
    private = tmp_path / "replay_ed25519.key"
    public = tmp_path / "replay_ed25519.pub"
    generate_production_key(private, public)
    with pytest.raises(LookaheadError, match="entry book"):
        run_historical_replay(
            _filing(now),
            now=now,
            books=[same],
            market_context=_market(),
            funding_rates=[0.0001, 0.0001, 0.0001],
            model_transport=transport,
            signing_path=str(private),
        )
    assert transport.calls["n"] == 0


def test_lookahead_rejects_a_candle_after_the_decision_in_model_context(tmp_path):
    now = datetime(2026, 10, 2, 13, 9, 26, tzinfo=timezone.utc)
    _proposal, entry, exit_book = _books(now)
    proposal = _book(now.isoformat(), "proposal-book", 99.99, 100.01, [[99.99, 10]], [[100.0, 10]])
    future_ms = int((now + timedelta(hours=2)).timestamp() * 1000)
    transport = _transport("LONG")
    private = tmp_path / "replay_ed25519.key"
    generate_production_key(private, tmp_path / "replay_ed25519.pub")
    market = _market(candles=[[future_ms, 100.0, 101.0, 99.0, 100.5, 1.0, 100.0]])
    with pytest.raises(LookaheadError, match="candle after decision time"):
        run_historical_replay(
            _filing(now),
            now=now,
            books=[proposal, entry, exit_book],
            market_context=market,
            funding_rates=[0.0001, 0.0001, 0.0001],
            model_transport=transport,
            signing_path=str(private),
        )
    assert transport.calls["n"] == 0


def test_model_no_action_produces_no_fill(tmp_path):
    report, store, _public, transport = _run(tmp_path, action="NO_ACTION")
    assert transport.calls["n"] == 1
    assert report["decision"]["status"] == "NO_ACTION"
    assert report["counted_outcome"] is False
    assert report["prospective"] is False
    assert store.list_fills() == []
    assert report["fill_status"] is None
    assert report["outcome_bp"] is None


def test_governor_refusal_produces_no_fill(tmp_path):
    report, store, _public, transport = _run(tmp_path, market=_market(n_precedents=1))
    assert transport.calls["n"] == 0
    assert report["model_calls"] == 0
    assert report["decision"]["reason"] == "governor_precheck:precedents_ok"
    assert report["governor"]["verdict"] == "REFUSED"
    assert report["governor"]["checks"]
    assert store.list_fills() == []
    assert report["fill_status"] is None
    assert report["counted_outcome"] is False
    assert report["prospective"] is False
    decision = store.get_decision(report["decision"]["id"])
    assert decision["mode"] == "historical_replay"
    receipt = store.receipt_for_decision(decision["id"])
    assert receipt["line"]["body"]["mode"] == "historical_replay"


def test_postgres_store_is_refused_before_connect():
    store = PostgresStore("postgresql://127.0.0.1/doesnotexist", schema="aftermath")
    calls = {"n": 0}

    def _connect():
        calls["n"] += 1
        raise AssertionError("postgres connect")

    store._connect = _connect
    transport = _transport("LONG")
    with pytest.raises(RuntimeError, match="MemoryStore"):
        run_historical_replay(
            {"event_time_utc": "2026-10-02T13:04:26+00:00", "payload": {}},
            now=datetime(2026, 10, 2, 13, 9, 26, tzinfo=timezone.utc),
            books=[],
            market_context={},
            funding_rates=None,
            model_transport=transport,
            signing_path="",
            store=store,
        )
    assert calls["n"] == 0
    assert transport.calls["n"] == 0


def test_default_store_is_memory_and_not_postgres(tmp_path):
    now = datetime(2026, 10, 2, 13, 9, 26, tzinfo=timezone.utc)
    proposal, entry, exit_book = _books(now)
    private = tmp_path / "replay_ed25519.key"
    generate_production_key(private, tmp_path / "replay_ed25519.pub")
    report = run_historical_replay(
        _filing(now),
        now=now,
        books=[proposal, entry, exit_book],
        market_context=_market(),
        funding_rates=[0.0001, 0.0001, 0.0001],
        model_transport=_transport("LONG"),
        signing_path=str(private),
    )
    assert report["store"] == "MemoryStore"
    assert report["counted_outcome"] is False
    assert report["prospective"] is False
    assert report["outcome_bp"] == 84.94
    assert "run_paper_cycle is not called" in " ".join(report["steps"]["replay_wrapped"])
