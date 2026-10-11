from datetime import datetime, timedelta, timezone

from aftermath_api.config import Settings
from aftermath_api.cycle import run_paper_cycle
from aftermath_api.metrics import evaluate
from aftermath_api.positions import close_later, enter_later, paired_from_fills, portfolio_state, summarize
from aftermath_api.store import MemoryStore
from tests.test_events import _settings


def _book(when: str, digest: str, bid: float, ask: float, bids, asks):
    mid = (bid + ask) / 2
    return {
        "source": "bitget-rest",
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


def _pending(when: str, digest: str):
    return {
        "symbol": "NVDAUSDT",
        "action": "LONG",
        "side": 1,
        "notional": 100.0,
        "horizon_hours": 24,
        "proposal_book_hash": digest,
        "proposal_fetched_at": when,
        "fee_rate": 0.0006,
    }


def test_same_snapshot_does_not_open_a_position():
    when = "2026-10-10T12:00:00+00:00"
    book = _book(when, "proposal-book", 99.99, 100.01, [[99.99, 10]], [[100.0, 10]])
    opened = enter_later(_pending(when, "proposal-book"), [book])
    assert opened["error"] == "no_later_book"


def test_entry_and_exit_use_the_approved_contract_fee_not_a_default():
    proposed = "2026-10-10T12:00:00+00:00"
    opened_at = "2026-10-10T13:00:00+00:00"
    entry_book = _book(opened_at, "entry-book", 99.99, 100.01, [[99.99, 10]], [[100.0, 10]])
    pending = {**_pending(proposed, "proposal-book"), "fee_rate": 0.0004}
    opened = enter_later(pending, [entry_book])
    assert opened["status"] == "PAPER_FILLED"
    assert opened["cost_json"]["fee_rate"] == 0.0004
    entry = opened["cost_json"]["entry"]
    assert abs(entry["fee_usdt"] - entry["filled_usdt"] * 0.0004) < 1e-9
    missing = {key: value for key, value in _pending(proposed, "proposal-book").items() if key != "fee_rate"}
    assert enter_later(missing, [entry_book]) == {"error": "missing_fee"}
    exit_at = (datetime.fromisoformat(opened_at) + timedelta(hours=24, seconds=1)).isoformat()
    exit_book = _book(exit_at, "exit-book", 100.99, 101.01, [[100.99, 10]], [[101.0, 10]])
    unpriced = {key: value for key, value in opened["cost_json"].items() if key != "fee_rate"}
    assert close_later(unpriced, [exit_book], datetime.fromisoformat(exit_at)) == {"error": "missing_fee"}


def test_later_book_entry_and_exit_match_the_cost_model():
    proposed = "2026-10-10T12:00:00+00:00"
    opened_at = "2026-10-10T13:00:00+00:00"
    exit_at = (datetime.fromisoformat(opened_at) + timedelta(hours=24, seconds=1)).isoformat()
    entry_book = _book(opened_at, "entry-book", 99.99, 100.01, [[99.99, 10]], [[100.0, 10]])
    opened = enter_later(_pending(proposed, "proposal-book"), [entry_book])
    assert opened["status"] == "PAPER_FILLED"
    assert opened["cost_json"]["entry_book_hash"] == "entry-book"
    assert opened["cost_json"]["entry"]["vwap"] == 100.0
    assert opened["cost_json"]["entry"]["fee_usdt"] == 0.06
    exit_book = _book(exit_at, "exit-book", 100.99, 101.01, [[101.0, 10]], [[101.02, 10]])
    opened["cost_json"]["funding_rates"] = [0.0001, 0.0001, 0.0001]
    closed = close_later(opened["cost_json"], [exit_book], datetime.fromisoformat(exit_at))
    # Buy 1 unit at 100, sell at 101. Fees 0.06 and 0.0606. Three venue prints of 1 bp.
    assert closed["cost_json"]["gross_usdt"] == 1.0
    assert closed["cost_json"]["fees_usdt"] == 0.1206
    assert closed["cost_json"]["funding_usdt"] == 0.03
    assert closed["cost_json"]["funding_source"] == "venue_funding"
    assert closed["cost_json"]["net_usdt"] == 0.8494
    assert closed["cost_json"]["outcome_bp"] == 84.94
    assert closed["cost_json"]["exit_book_hash"] == "exit-book"
    baselines = closed["cost_json"]["baselines"]
    assert baselines["fixed_sign_bp"] == 84.94
    assert baselines["llm_off_bp"] == 0
    assert baselines["llm_off_policy"] == "identical_to_no_trade"
    assert baselines["no_trade_bp"] == 0
    assert baselines["random_bp"] is not None
    report = evaluate(paired_from_fills([{"cost_json": closed["cost_json"]}]))
    assert report["status"] == "INSUFFICIENT_DATA"
    assert report["sample_size"] == 1


def test_missing_funding_is_not_replaced_with_one_basis_point():
    proposed = "2026-10-10T12:00:00+00:00"
    opened_at = "2026-10-10T13:00:00+00:00"
    exit_at = (datetime.fromisoformat(opened_at) + timedelta(hours=24, seconds=1)).isoformat()
    opened = enter_later(_pending(proposed, "proposal-book"), [_book(opened_at, "entry-book", 99.99, 100.01, [[99.99, 10]], [[100.0, 10]])])
    closed = close_later(opened["cost_json"], [_book(exit_at, "exit-book", 100.99, 101.01, [[101.0, 10]], [[101.02, 10]])], datetime.fromisoformat(exit_at))
    assert closed["cost_json"]["funding_source"] == "missing"
    assert closed["cost_json"]["funding_usdt"] is None
    assert closed["cost_json"]["outcome_bp"] is None
    zero = dict(opened["cost_json"])
    zero["funding_rates"] = [0.0, 0.0, 0.0]
    priced = close_later(zero, [_book(exit_at, "exit-zero", 100.99, 101.01, [[101.0, 10]], [[101.02, 10]])], datetime.fromisoformat(exit_at))
    assert priced["cost_json"]["funding_source"] == "venue_funding"
    assert priced["cost_json"]["funding_usdt"] == 0.0
    assert priced["cost_json"]["net_usdt"] == 0.8794


def test_metrics_stay_insufficient_below_the_preregistered_minimum():
    one = [{"cost_json": {"outcome_bp": 84.94}}]
    assert summarize(one)["status"] == "INSUFFICIENT_DATA"
    assert summarize(one)["sample_size"] == 1
    many = [{"cost_json": {"outcome_bp": 1.0}} for _ in range(30)]
    observed = summarize(many)
    assert observed["status"] == "OBSERVED"
    assert observed["sample_size"] == 30
    assert observed["mean_net_bp"] == 1.0
    assert observed["label"] == "observed"


def test_cycle_opens_a_pending_entry_only_on_a_later_book():
    store = MemoryStore()
    proposed = "2026-10-10T12:00:00+00:00"
    store.insert_fill({
        "id": "fill_pending",
        "decision_id": "dec_pending",
        "idempotency_key": "pending-entry",
        "status": "PENDING_ENTRY",
        "cost_json": _pending(proposed, "proposal-book"),
        "created_at_utc": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
    })
    same = _book(proposed, "proposal-book", 99.99, 100.01, [[99.99, 10]], [[100.0, 10]])
    run_paper_cycle(_settings(llm_configured=False, decisions="abstain_only"), store, fetch=lambda: ([same], []))
    assert store.list_fills()[0]["status"] == "PENDING_ENTRY"
    later = "2026-10-10T14:00:00+00:00"
    nxt = _book(later, "entry-book", 99.99, 100.01, [[99.99, 10]], [[100.0, 10]])
    fresh = MemoryStore()
    fresh.insert_fill({
        "id": "fill_pending",
        "decision_id": "dec_pending",
        "idempotency_key": "pending-entry",
        "status": "PENDING_ENTRY",
        "cost_json": _pending(proposed, "proposal-book"),
        "created_at_utc": proposed,
    })
    run_paper_cycle(_settings(llm_configured=False, decisions="abstain_only"), fresh, fetch=lambda: ([nxt], []))
    opened = [row for row in fresh.list_fills() if row["id"] == "fill_pending"][0]
    assert opened["status"] == "PAPER_FILLED"
    assert opened["cost_json"]["entry_book_hash"] == "entry-book"
    assert opened["cost_json"].get("outcome_bp") is None


def test_a_pending_entry_expires_without_a_fill():
    store = MemoryStore()
    proposed = "2026-10-10T12:00:00+00:00"
    store.insert_fill({
        "id": "fill_old",
        "decision_id": "dec_old",
        "idempotency_key": "old-entry",
        "status": "PENDING_ENTRY",
        "cost_json": _pending(proposed, "proposal-book"),
        "created_at_utc": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
    })
    same = _book(proposed, "proposal-book", 99.99, 100.01, [[99.99, 10]], [[100.0, 10]])
    run_paper_cycle(_settings(llm_configured=False, decisions="abstain_only"), store, fetch=lambda: ([same], []))
    expired = store.list_fills()[0]
    assert expired["status"] == "EXPIRED"
    assert expired["cost_json"]["expiry_reason"] == "no_later_book"
    assert expired["cost_json"].get("entry") is None
    assert store.fill_events[-1]["status"] == "EXPIRED"


def test_closed_pnl_is_a_fraction_of_equity():
    store = MemoryStore()
    today = datetime.now(timezone.utc).isoformat()
    store.insert_fill({
        "id": "fill_closed",
        "decision_id": "dec_closed",
        "idempotency_key": "closed",
        "status": "CLOSED",
        "cost_json": {"symbol": "NVDAUSDT", "net_usdt": -100.0, "closed_at": today},
        "created_at_utc": today,
    })
    state = portfolio_state(store)
    assert state["day_pnl"] == -0.01
    assert state["drawdown"] == -0.01
    assert state["symbol_pnl_by_symbol"]["NVDAUSDT"] == -0.01


def _market_for_govern(_symbol, _now):
    return {
        "contract": {"status": "normal", "is_rwa": "YES", "taker_fee_rate": 0.0006},
        "n_precedents": 4,
        "hedge_r2": 0.4,
        "hedge_beta": 0.9,
    }


def _cycle_settings(signing_key_path: str):
    return Settings(
        env="test",
        database_url="",
        direct_url="",
        llm_api_key="x",
        llm_base_url="https://example.test/v1",
        llm_model="m",
        llm_configured=True,
        reader_token="r",
        decision_token="d",
        job_token="j",
        signing_key_path=signing_key_path,
        sec_user_agent="",
        web_origin="",
        decisions="model",
    )


def test_isolated_lifecycle_approve_pending_fill_close_receipt_and_tamper(tmp_path):
    """In-memory isolated store (no production Postgres): governor approve, pending entry,
    later-book fill, horizon close with explicit venue funding, signed receipt, tamper fail."""
    import json as jsonlib

    from aftermath_api.paper import govern
    from aftermath_api.positions import advance_positions, lifecycle_intact
    from aftermath_api.receipts import chain_intact, generate_production_key, verify_line

    production_ledger = MemoryStore()
    store = MemoryStore()
    private = tmp_path / "production_ed25519.key"
    public = tmp_path / "production_ed25519.pub"
    generate_production_key(private, public)

    clock = datetime.now(timezone.utc)
    proposed = (clock - timedelta(seconds=30)).isoformat()
    opened_at = clock.isoformat()
    exit_at = (clock + timedelta(hours=24, seconds=1)).isoformat()
    proposal_book = _book(proposed, "proposal-book", 99.99, 100.01, [[99.99, 10]], [[100.0, 10]])
    entry_book = _book(opened_at, "entry-book", 99.99, 100.01, [[99.99, 10]], [[100.0, 10]])
    exit_book = _book(exit_at, "exit-book", 100.99, 101.01, [[101.0, 10]], [[101.02, 10]])
    filing = {
        "source": "sec-edgar",
        "instrument_id": "NVDAUSDT",
        "event_type": "filing",
        "event_time_utc": proposed,
        "fetched_at_utc": proposed,
        "payload": {
            "form": "8-K",
            "items": "2.02",
            "qualifies": True,
            "accession": "proof-isolated-lifecycle-2.02",
            "document_sha256": "d" * 64,
            "excerpt": "Item 2.02 results of operations.",
            "excerpt_untrusted": True,
        },
        "mapping_confidence": 1.0,
    }

    def transport(_url, json=None, headers=None, timeout=None):
        cited = jsonlib.loads(json["messages"][1]["content"])["evidence"][0]["id"]
        body = {
            "action": "LONG",
            "symbol": "NVDAUSDT",
            "size_frac": 0.05,
            "confidence": 0.8,
            "horizon_hours": 24,
            "thesis": "The filing supports a paper long.",
            "invalidation": "A later book that removes the residual ends the idea.",
            "cited_evidence_ids": [cited],
            "text": "no numeric claim",
        }

        class Ok:
            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": jsonlib.dumps(body)}}]}

        return Ok()

    settings = _cycle_settings(str(private))
    approved = run_paper_cycle(
        settings,
        store,
        fetch=lambda: ([proposal_book], []),
        event_fetch=lambda: [filing],
        signing_path=str(private),
        model_transport=transport,
        market_fetch=_market_for_govern,
    )
    assert approved["reason"] == "awaiting_next_book"
    assert approved["receipt_id"]
    assert production_ledger.ledger == []

    fill_key = approved["idempotency_key"] + ":entry"
    pending = store.fill_for_key(fill_key)
    assert pending["status"] == "PENDING_ENTRY"
    assert lifecycle_intact(store, pending["id"])
    assert all(row.get("source") != "fixture" for row in store.events.values())

    decision = store.get_decision(approved["decision_id"])
    events = [store.get_evidence(eid)["event"] for eid in decision["evidence_ids"]]
    from aftermath_api.execution_context import derive_execution

    derived = derive_execution(
        {"action": "LONG", "symbol": "NVDAUSDT", "size_frac": 0.05, "horizon_hours": 24},
        events,
        "model",
        market=_market_for_govern("NVDAUSDT", None),
    )
    assert derived["error"] is None
    assert govern({"action": "LONG", "symbol": "NVDAUSDT", "size_frac": 0.05, "horizon_hours": 24, "confidence": 0.8}, derived["context"])["verdict"] == "APPROVED"

    advance_positions(store, [entry_book], datetime.fromisoformat(opened_at), signing_path=str(private))
    opened = store.fill_for_key(fill_key)
    assert opened["status"] == "PAPER_FILLED"
    assert opened["cost_json"]["entry_book_hash"] == "entry-book"
    assert lifecycle_intact(store, opened["id"])

    store.update_fill(
        opened["id"],
        cost_json={**opened["cost_json"], "funding_rates": [0.0001, 0.0001, 0.0001]},
    )
    advance_positions(store, [exit_book], datetime.fromisoformat(exit_at), signing_path=str(private))
    closed = store.fill_for_key(fill_key)
    assert closed["status"] == "CLOSED"
    assert closed["cost_json"]["funding_source"] == "venue_funding"
    assert closed["cost_json"]["funding_usdt"] == 0.15
    assert closed["cost_json"]["outcome_bp"] == 84.94
    assert lifecycle_intact(store, closed["id"])

    receipt = store.receipt_for_decision(approved["decision_id"])
    assert receipt is not None
    assert verify_line(public, receipt["line"]) is True
    transitions = [line for line in store.list_ledger() if (line.get("body") or {}).get("kind") == "fill_transition"]
    assert [line["body"]["status"] for line in transitions] == ["PAPER_FILLED", "CLOSED"]
    assert all(verify_line(public, line) for line in transitions)
    assert chain_intact(public, store.list_ledger())
    tampered = {**receipt["line"], "body": {**receipt["line"]["body"], "status": "CLOSED"}}
    assert verify_line(public, tampered) is False
    close_line = transitions[-1]
    tampered_close = {**close_line, "body": {**close_line["body"], "status": "PAPER_FILLED"}}
    assert verify_line(public, tampered_close) is False
    assert production_ledger.ledger == []
