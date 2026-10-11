"""The public paper log is the forward ledger. Replay and invented rows stay out."""

import csv
import io

from fastapi.testclient import TestClient

from aftermath_api.app import create_app
from aftermath_api.config import Settings
from aftermath_api.paper_log import closed_outcome_count, cycle_rows, to_csv, trade_rows, TRADE_COLUMNS
from aftermath_api.store import MemoryStore


def _settings():
    return Settings(
        env="test", database_url="", direct_url="", llm_api_key="", llm_base_url="", llm_model="",
        llm_configured=False, reader_token="reader-token", decision_token="d", job_token="j",
        signing_key_path="", sec_user_agent="", web_origin="", decisions="abstain_only",
    )


def _fill(fill_id, status, cost, decision="dec_1", key="paper-cycle:v2:2026-10-11T12:entry"):
    return {
        "id": fill_id,
        "decision_id": decision,
        "idempotency_key": key,
        "status": status,
        "created_at_utc": "2026-10-11T12:00:00+00:00",
        "cost_json": cost,
    }


def _closed(**overrides):
    cost = {
        "symbol": "NVDAUSDT",
        "action": "LONG",
        "side": 1,
        "opened_at": "2026-10-11T13:00:00+00:00",
        "closed_at": "2026-10-12T13:00:00+00:00",
        "entry": {"vwap": 100.0, "qty": 1.0, "filled_usdt": 100.0, "fee_usdt": 0.06, "slippage_bp": 1.0},
        "exit": {"vwap": 101.0, "filled_usdt": 101.0, "slippage_bp": 1.2},
        "gross_usdt": 1.0,
        "fees_usdt": 0.1206,
        "funding_usdt": 0.03,
        "net_usdt": 0.8494,
        "entry_spread_bp": 2.0,
        "exit_spread_bp": 1.98,
    }
    cost.update(overrides)
    return cost


def _reader(text):
    return list(csv.DictReader(io.StringIO(text)))


def test_closed_row_matches_recomputed_pnl_and_labels_the_venue():
    rows = trade_rows([_fill("fill_1", "CLOSED", _closed())])
    assert len(rows) == 1
    row = rows[0]
    assert row["venue"] == "internal_paper"
    assert row["trade_status"] == "CLOSED"
    assert row["strategy_version"] == "S-A"
    assert row["net_pnl"] == "0.8494"
    assert row["balance_change"] == "0.8494"
    assert row["fees"] == "0.1206"
    assert row["funding"] == "0.03"
    assert float(row["net_pnl"]) == round(1.0 - 0.1206 - 0.03, 6)
    assert row["demo_order_id"] == ""
    text = to_csv(TRADE_COLUMNS, rows)
    assert "postgresql" not in text
    assert "Bearer" not in text


def test_open_position_is_not_a_closed_outcome():
    rows = trade_rows([
        _fill("fill_open", "PAPER_FILLED", {
            "symbol": "NVDAUSDT", "action": "LONG", "opened_at": "2026-10-11T13:00:00+00:00",
            "entry": {"vwap": 100.0, "qty": 1.0, "filled_usdt": 100.0, "fee_usdt": 0.06},
            "entry_spread_bp": 2.0,
        }),
    ])
    assert rows[0]["trade_status"] == "OPEN"
    assert rows[0]["exit_price"] == ""
    assert rows[0]["net_pnl"] == ""
    assert rows[0]["balance_change"] == ""
    assert rows[0]["funding"] == ""
    assert closed_outcome_count(rows) == 0


def test_missing_fees_or_funding_are_not_invented():
    missing_fee = _closed()
    del missing_fee["fees_usdt"]
    missing_funding = _closed()
    missing_funding["funding_usdt"] = None
    rows = trade_rows([
        _fill("fill_fee", "CLOSED", missing_fee, decision="dec_fee"),
        _fill("fill_fund", "CLOSED", missing_funding, decision="dec_fund"),
    ])
    assert rows[0]["trade_status"] == "INCOMPLETE"
    assert rows[0]["fees"] == ""
    assert rows[0]["net_pnl"] == ""
    assert rows[1]["funding"] == ""
    assert rows[1]["trade_status"] == "INCOMPLETE"
    assert closed_outcome_count(rows) == 0


def test_a_fabricated_net_is_not_a_closed_outcome():
    forged = _closed(net_usdt=50.0)
    rows = trade_rows([_fill("fill_fake", "CLOSED", forged)])
    assert rows[0]["trade_status"] == "INCOMPLETE"
    assert rows[0]["net_pnl"] == ""
    assert closed_outcome_count(rows) == 0


def test_replay_fixture_and_studio_do_not_leak():
    rows = trade_rows([
        _fill("fill_r", "CLOSED", _closed(mode="historical_replay"), decision="dec_r", key="historical_replay:acc"),
        _fill("fill_f", "CLOSED", _closed(mode="fixture"), decision="dec_f"),
        _fill("fill_s", "CLOSED", _closed(mode="getagent_studio"), decision="dec_s"),
        _fill("fill_h", "CLOSED", _closed(strategy_id="H-HF-1"), decision="dec_h"),
    ])
    assert rows == []


def test_duplicate_decision_or_order_is_exported_once():
    demo = _closed(mode="bitget_demo", demo_order_id="ord_1")
    rows = trade_rows([
        _fill("fill_a", "CLOSED", demo, decision="dec_same", key="a"),
        _fill("fill_b", "CLOSED", demo, decision="dec_same", key="b"),
        _fill("fill_c", "CLOSED", _closed(mode="bitget_demo", demo_order_id="ord_1"), decision="dec_other", key="c"),
    ])
    assert len(rows) == 1
    assert rows[0]["demo_order_id"] == "ord_1"
    assert rows[0]["venue"] == "bitget_demo"


def test_cycle_log_keeps_refusals_and_drops_replay():
    rows = cycle_rows([
        {
            "started_at_utc": "2026-10-11T12:17:00+00:00",
            "decision_id": "dec_live",
            "idempotency_key": "paper-cycle:v2:2026-10-11T12",
            "status": "refused",
            "reason": "no_qualifying_event",
            "detail": {"model_calls": 0},
        },
        {
            "started_at_utc": "2026-08-26T20:30:00+00:00",
            "decision_id": "dec_replay",
            "idempotency_key": "historical_replay:0001045810-26-000073:2026-08-26T20:30",
            "status": "NO_ACTION",
            "reason": "model_no_action",
            "detail": {"mode": "historical_replay", "model_calls": 1},
        },
    ])
    assert len(rows) == 1
    assert rows[0]["reason"] == "no_qualifying_event"
    assert rows[0]["record_class"] == "forward_cycle"
    assert rows[0]["model_calls"] == 0


def test_public_csv_needs_no_login_and_rejects_writes():
    store = MemoryStore()
    store.insert_fill(_fill("fill_1", "CLOSED", _closed()))
    store.insert_run({
        "id": "run_1",
        "idempotency_key": "paper-cycle:v2:2026-10-11T12",
        "status": "refused",
        "reason": "no_qualifying_event",
        "decision_id": "dec_1",
        "started_at_utc": "2026-10-11T12:17:00+00:00",
        "finished_at_utc": "2026-10-11T12:18:00+00:00",
        "detail": {"model_calls": 0},
    })
    http = TestClient(create_app(_settings(), store))
    trades = http.get("/paper-trading-log.csv")
    cycles = http.get("/paper-cycle-log.csv")
    page = http.get("/paper-trading-log")
    assert trades.status_code == 200
    assert "text/csv" in trades.headers["content-type"]
    assert _reader(trades.text)[0]["decision_id"] == "dec_1"
    assert cycles.status_code == 200
    assert _reader(cycles.text)[0]["reason"] == "no_qualifying_event"
    assert page.status_code == 200
    assert "No forward paper trade has closed" not in page.text
    assert "1 closed" in page.text
    denied = http.post("/paper-trading-log.csv")
    assert denied.status_code == 405
    assert len(store.list_fills()) == 1


def test_empty_ledger_reports_the_blocker_and_no_trade_row():
    http = TestClient(create_app(_settings(), MemoryStore()))
    trades = http.get("/paper-trading-log.csv")
    page = http.get("/paper-trading-log")
    assert _reader(trades.text) == []
    assert trades.text.splitlines()[0].startswith("timestamp_utc,")
    assert "No forward paper trade has closed" in page.text
    assert "not a profitability claim" not in page.text
