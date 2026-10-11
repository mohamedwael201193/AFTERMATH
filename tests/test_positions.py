from datetime import datetime, timedelta, timezone

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
