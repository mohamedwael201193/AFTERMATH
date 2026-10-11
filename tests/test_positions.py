from datetime import datetime, timedelta, timezone

from aftermath_api.config import Settings
from aftermath_api.cycle import annotate_due_funding, run_paper_cycle
from aftermath_api.metrics import evaluate
from aftermath_api.positions import close_later, enter_later, mark_later, paired_from_fills, portfolio_state, summarize
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
        "funding_interval_hours": 8,
        "post_acceptance_bp": 50.0,
        "accession": "0001045810-26-000073",
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
    assert opened["cost_json"]["entry_spread_bp"] == 2.0
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
    assert closed["cost_json"]["exit_spread_bp"] == round((101.01 - 100.99) / 101 * 1e4, 4)
    quoted = paired_from_fills([{"cost_json": closed["cost_json"]}])[0]
    assert quoted["spread_bp"] == round((2.0 + closed["cost_json"]["exit_spread_bp"]) / 2, 4)
    assert closed["cost_json"]["exit_book_hash"] == "exit-book"
    baselines = closed["cost_json"]["baselines"]
    assert baselines["fixed_sign_bp"] == 84.94
    assert baselines["fixed_sign_side"] == 1
    assert baselines["llm_off_bp"] == 0
    assert baselines["llm_off_policy"] == "same_column_as_no_trade"
    assert baselines["no_trade_bp"] == 0
    assert baselines["random_bp"] is not None
    report = evaluate(paired_from_fills([{"cost_json": closed["cost_json"]}]))
    assert report["status"] == "INSUFFICIENT_DATA"
    assert report["sample_size"] == 1


def test_a_book_before_the_horizon_is_a_mark_and_the_exit_waits():
    proposed = "2026-10-10T12:00:00+00:00"
    opened_at = "2026-10-10T13:00:00+00:00"
    mark_at = "2026-10-10T14:00:00+00:00"
    exit_at = (datetime.fromisoformat(opened_at) + timedelta(hours=24, seconds=1)).isoformat()
    opened = enter_later(_pending(proposed, "proposal-book"), [_book(opened_at, "entry-book", 99.99, 100.01, [[99.99, 10]], [[100.0, 10]])])
    mark_book = _book(mark_at, "mark-book", 100.49, 100.51, [[100.49, 10]], [[100.51, 10]])
    exit_book = _book(exit_at, "exit-book", 100.99, 101.01, [[101.0, 10]], [[101.02, 10]])
    marked = mark_later(opened["cost_json"], [mark_book, exit_book], datetime.fromisoformat(mark_at))
    assert marked["changed"] is True
    assert marked["status"] == "PAPER_FILLED"
    assert marked["cost_json"]["mark"]["book_hash"] == "mark-book"
    assert marked["cost_json"]["mark"]["mid"] == 100.5
    assert marked["cost_json"]["mark"]["counted_outcome"] is False
    entry = opened["cost_json"]["entry"]
    gross = float(entry["qty"]) * (100.5 - float(entry["vwap"]))
    assert marked["cost_json"]["mark"]["unrealized_usdt"] == round(gross - float(entry["fee_usdt"]), 4)
    unpaid = dict(opened["cost_json"])
    unpaid["entry"] = {key: value for key, value in entry.items() if key != "fee_usdt"}
    missing_fee = mark_later(unpaid, [mark_book], datetime.fromisoformat(mark_at))
    assert missing_fee["cost_json"]["mark"]["unrealized_usdt"] is None
    assert missing_fee["cost_json"]["mark"]["gross_usdt"] == round(gross, 4)
    assert "outcome_bp" not in marked["cost_json"]
    assert mark_later(marked["cost_json"], [mark_book], datetime.fromisoformat(mark_at))["changed"] is False
    opened["cost_json"]["funding_rates"] = [0.0001, 0.0001, 0.0001]
    marked["cost_json"]["funding_rates"] = [0.0001, 0.0001, 0.0001]
    closed = close_later(marked["cost_json"], [mark_book, exit_book], datetime.fromisoformat(exit_at))
    assert closed["cost_json"]["exit_book_hash"] == "exit-book"
    assert closed["cost_json"]["outcome_bp"] == 84.94
    pair = paired_from_fills([{"cost_json": closed["cost_json"]}])[0]
    assert abs(pair["hold_hours"] - (24 + 1 / 3600)) < 1e-6
    assert pair["notional_usdt"] == closed["cost_json"]["entry"]["filled_usdt"]
    too_early = close_later(marked["cost_json"], [mark_book, exit_book], datetime.fromisoformat(mark_at))
    assert too_early == {"error": "horizon_open"}


def test_short_receives_positive_funding():
    proposed = "2026-10-10T12:00:00+00:00"
    opened_at = "2026-10-10T13:00:00+00:00"
    exit_at = (datetime.fromisoformat(opened_at) + timedelta(hours=24, seconds=1)).isoformat()
    pending = _pending(proposed, "proposal-book")
    pending["side"] = -1
    pending["action"] = "SHORT"
    pending["post_acceptance_bp"] = -25.0
    opened = enter_later(pending, [_book(opened_at, "entry-book", 99.99, 100.01, [[99.99, 10]], [[100.0, 10]])])
    opened["cost_json"]["funding_rates"] = [0.0001, 0.0001, 0.0001]
    closed = close_later(
        opened["cost_json"],
        [_book(exit_at, "exit-book", 100.99, 101.01, [[101.0, 10]], [[101.02, 10]])],
        datetime.fromisoformat(exit_at),
    )
    filled = closed["cost_json"]["entry"]["filled_usdt"]
    assert closed["cost_json"]["funding_usdt"] == round(-filled * 0.0003, 6)
    long = enter_later(_pending(proposed, "proposal-book"), [_book(opened_at, "entry-book", 99.99, 100.01, [[99.99, 10]], [[100.0, 10]])])
    long["cost_json"]["funding_rates"] = [0.0001, 0.0001, 0.0001]
    long["cost_json"]["post_acceptance_bp"] = -25.0
    compared = close_later(
        long["cost_json"],
        [_book(exit_at, "exit-book", 100.99, 101.01, [[101.0, 10]], [[101.02, 10]])],
        datetime.fromisoformat(exit_at),
    )
    assert compared["cost_json"]["baselines"]["fixed_sign_side"] == -1
    assert compared["cost_json"]["baselines"]["fixed_sign_bp"] != compared["cost_json"]["outcome_bp"]


def test_funding_uses_the_contract_interval_and_does_not_assume_eight_hours():
    proposed = "2026-10-10T12:00:00+00:00"
    opened_at = "2026-10-10T13:00:00+00:00"
    exit_at = (datetime.fromisoformat(opened_at) + timedelta(hours=24, seconds=1)).isoformat()
    book = _book(opened_at, "entry-book", 99.99, 100.01, [[99.99, 10]], [[100.0, 10]])
    exit_book = _book(exit_at, "exit-book", 100.99, 101.01, [[101.0, 10]], [[101.02, 10]])
    opened = enter_later(_pending(proposed, "proposal-book"), [book])
    four = dict(opened["cost_json"])
    four["funding_interval_hours"] = 4
    four["funding_rates"] = [0.0001] * 6
    closed = close_later(four, [exit_book], datetime.fromisoformat(exit_at))
    assert closed["cost_json"]["funding_settlements"] == 6
    assert closed["cost_json"]["funding_source"] == "venue_funding"
    filled = float(opened["cost_json"]["entry"]["filled_usdt"])
    assert closed["cost_json"]["funding_usdt"] == round(filled * 0.0006, 6)
    missing = dict(four)
    missing.pop("funding_interval_hours")
    refused = close_later(missing, [exit_book], datetime.fromisoformat(exit_at))
    assert refused["cost_json"]["funding_source"] == "missing_interval"
    assert refused["cost_json"]["funding_usdt"] is None
    assert refused["cost_json"]["outcome_bp"] is None


def test_exit_book_prints_price_funding_only_when_the_window_is_complete():
    proposed = "2026-10-10T12:00:00+00:00"
    opened_at = datetime.fromisoformat("2026-10-10T13:00:00+00:00")
    exit_at = opened_at + timedelta(hours=24, seconds=1)
    opened = enter_later(_pending(proposed, "proposal-book"), [_book(opened_at.isoformat(), "entry-book", 99.99, 100.01, [[99.99, 10]], [[100.0, 10]])])
    cost = opened["cost_json"]
    assert "funding_rates" not in cost
    stamps = [opened_at + timedelta(hours=hours) for hours in (8, 16, 24)]
    prints = [{"funding_time_utc": stamp.isoformat(), "rate": 0.0001} for stamp in stamps]
    prints.append({"funding_time_utc": (opened_at - timedelta(hours=8)).isoformat(), "rate": 0.01})
    exit_book = _book(exit_at.isoformat(), "exit-book", 100.99, 101.01, [[101.0, 10]], [[101.02, 10]])
    exit_book["payload"]["funding_prints"] = prints
    closed = close_later(cost, [exit_book], exit_at)
    assert closed["cost_json"]["funding_source"] == "venue_funding"
    assert closed["cost_json"]["funding_settlements"] == 3
    assert closed["cost_json"]["funding_rates"] == [0.0001, 0.0001, 0.0001]
    filled = float(cost["entry"]["filled_usdt"])
    assert closed["cost_json"]["funding_usdt"] == round(filled * 0.0003, 6)
    short = _book(exit_at.isoformat(), "exit-short", 100.99, 101.01, [[101.0, 10]], [[101.02, 10]])
    short["payload"]["funding_prints"] = prints[:2]
    refused = close_later(cost, [short], exit_at)
    assert refused["cost_json"]["funding_source"] == "missing"
    assert refused["cost_json"]["funding_usdt"] is None
    assert refused["cost_json"]["outcome_bp"] is None
    explicit = dict(cost)
    explicit["funding_rates"] = [0.0, 0.0, 0.0]
    priced = close_later(explicit, [short], exit_at)
    assert priced["cost_json"]["funding_source"] == "venue_funding"
    assert priced["cost_json"]["funding_usdt"] == 0.0


class _Fills:
    def __init__(self, fill):
        self.fill = fill

    def list_fills(self):
        return [self.fill]


def test_a_due_position_receives_funding_history_on_its_exit_book():
    opened = datetime.fromisoformat("2026-10-10T13:00:00+00:00")
    now = opened + timedelta(hours=24, seconds=1)
    fill = {
        "status": "PAPER_FILLED",
        "cost_json": {
            "symbol": "NVDAUSDT",
            "opened_at": opened.isoformat(),
            "horizon_hours": 24,
            "funding_interval_hours": 8,
        },
    }
    prints = [{"funding_time_utc": (opened + timedelta(hours=8)).isoformat(), "rate": 0.0001}]
    book = _book(now.isoformat(), "exit-book", 100.99, 101.01, [[101.0, 10]], [[101.02, 10]])
    seen = []

    def fetch(symbol):
        seen.append(symbol)
        return prints

    annotate_due_funding(_Fills(fill), [book], now, fetch)
    assert seen == ["NVDAUSDT"]
    assert book["payload"]["funding_prints"] == prints

    early_book = _book(opened.isoformat(), "early-book", 99.99, 100.01, [[99.99, 10]], [[100.0, 10]])
    annotate_due_funding(_Fills(fill), [early_book], opened + timedelta(hours=1), fetch)
    assert "funding_prints" not in early_book["payload"]
    assert seen == ["NVDAUSDT"]

    failed = _book(now.isoformat(), "failed-book", 100.99, 101.01, [[101.0, 10]], [[101.02, 10]])

    def boom(_symbol):
        raise RuntimeError("funding history unavailable")

    annotate_due_funding(_Fills(fill), [failed], now, boom)
    assert "funding_prints" not in failed["payload"]

    rated = {
        "status": "PAPER_FILLED",
        "cost_json": {**fill["cost_json"], "funding_rates": [0.0, 0.0, 0.0]},
    }
    untouched = _book(now.isoformat(), "rated-book", 100.99, 101.01, [[101.0, 10]], [[101.02, 10]])

    def unexpected(_symbol):
        raise AssertionError("funding history was fetched for a position that already has rates")

    annotate_due_funding(_Fills(rated), [untouched], now, unexpected)
    assert "funding_prints" not in untouched["payload"]


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
        "contract": {"status": "normal", "is_rwa": "YES", "taker_fee_rate": 0.0006, "funding_interval_hours": 8},
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

    mark_at = (datetime.fromisoformat(opened_at) + timedelta(hours=1)).isoformat()
    mark_book = _book(mark_at, "mark-book", 100.49, 100.51, [[100.49, 10]], [[100.51, 10]])
    advance_positions(store, [mark_book], datetime.fromisoformat(mark_at), signing_path=str(private))
    marked = store.fill_for_key(fill_key)
    assert marked["status"] == "PAPER_FILLED"
    assert marked["cost_json"]["mark"]["book_hash"] == "mark-book"
    assert marked["cost_json"]["mark"]["counted_outcome"] is False
    assert "outcome_bp" not in marked["cost_json"]
    assert lifecycle_intact(store, marked["id"])
    signed_before_repeat = len(store.list_ledger())
    advance_positions(store, [mark_book], datetime.fromisoformat(mark_at), signing_path=str(private))
    assert len(store.list_ledger()) == signed_before_repeat

    store.update_fill(
        marked["id"],
        cost_json={**marked["cost_json"], "funding_rates": [0.0001, 0.0001, 0.0001]},
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
    assert [line["body"]["status"] for line in transitions] == ["PAPER_FILLED", "PAPER_FILLED", "CLOSED"]
    assert all(verify_line(public, line) for line in transitions)
    assert chain_intact(public, store.list_ledger())
    tampered = {**receipt["line"], "body": {**receipt["line"]["body"], "status": "CLOSED"}}
    assert verify_line(public, tampered) is False
    close_line = transitions[-1]
    tampered_close = {**close_line, "body": {**close_line["body"], "status": "PAPER_FILLED"}}
    assert verify_line(public, tampered_close) is False
    assert production_ledger.ledger == []
