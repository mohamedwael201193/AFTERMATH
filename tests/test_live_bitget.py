"""Live public market data. These tests call Bitget and write nothing."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from aftermath_api.connectors import BitgetConnector
from aftermath_api.positions import close_later, mark_later


@pytest.mark.live
def test_live_public_ticker(tmp_path: Path):
    obs = BitgetConnector(tmp_path, mode="live").ticker("BTCUSDT")
    assert obs["source"] == "bitget-rest"
    assert obs["instrument_id"] == "BTCUSDT"
    assert obs["payload"]["last"] > 0
    assert obs["fetched_at_utc"]


@pytest.mark.live
def test_live_public_depth(tmp_path: Path):
    obs = BitgetConnector(tmp_path, mode="live").depth("NVDAUSDT")
    assert obs["event_type"] == "book"
    assert obs["instrument_id"] == "NVDAUSDT"
    assert obs["payload"]["ask"] > obs["payload"]["bid"] > 0
    assert obs["payload"]["depth_usdt"] > 0
    assert obs["endpoint"] == "/api/v2/mix/market/merge-depth"


@pytest.mark.live
def test_a_real_nvda_book_marks_a_paper_position_and_is_not_an_outcome(tmp_path: Path):
    connector = BitgetConnector(tmp_path, mode="live")
    book = connector.depth("NVDAUSDT")
    contract = connector.contract("NVDAUSDT")
    assert contract["instrument_category"] == "USDT-FUTURES"
    fee = float(contract["taker_fee_rate"])
    assert 0 < fee <= 0.01
    payload = book["payload"]
    fetched = datetime.fromisoformat(book["fetched_at_utc"])
    mid = (payload["bid"] + payload["ask"]) / 2
    qty = 1.0
    entry_vwap = mid - 1
    entry_fee = round(entry_vwap * qty * fee, 6)
    cost = {
        "symbol": "NVDAUSDT",
        "side": 1,
        "opened_at": (fetched - timedelta(hours=1)).isoformat(),
        "horizon_hours": 24,
        "entry_book_hash": "earlier-book",
        "fee_rate": fee,
        "entry": {"vwap": entry_vwap, "qty": qty, "fee_usdt": entry_fee, "filled_usdt": entry_vwap * qty},
    }
    marked = mark_later(cost, [book], fetched)
    assert marked["changed"] is True
    mark = marked["cost_json"]["mark"]
    assert mark["bid"] == payload["bid"]
    assert mark["ask"] == payload["ask"]
    assert mark["book_hash"] == payload["raw_sha256"]
    assert mark["counted_outcome"] is False
    assert mark["unrealized_usdt"] == round(qty * (mid - entry_vwap) - entry_fee, 4)
    assert "outcome_bp" not in marked["cost_json"]


@pytest.mark.live
def test_real_nvda_funding_history_prices_a_matching_window(tmp_path: Path):
    connector = BitgetConnector(tmp_path, mode="live")
    contract = connector.contract("NVDAUSDT")
    assert contract["instrument_category"] == "USDT-FUTURES"
    interval = float(contract["funding_interval_hours"])
    assert interval == 8
    prints = connector.funding_history("NVDAUSDT")
    assert len(prints) >= 4
    latest = datetime.fromisoformat(prints[-1]["funding_time_utc"])
    opened = latest - timedelta(hours=24)
    closed_at = latest + timedelta(seconds=1)
    in_window = [
        row for row in prints
        if opened < datetime.fromisoformat(row["funding_time_utc"]) <= closed_at
    ]
    exit_book = {
        "source": "bitget-rest",
        "instrument_id": "NVDAUSDT",
        "event_type": "book",
        "event_time_utc": closed_at.isoformat(),
        "fetched_at_utc": closed_at.isoformat(),
        "payload": {
            "bid": 100.0,
            "ask": 100.02,
            "spread_bp": 2.0,
            "depth_usdt": 5000.0,
            "bids": [[100.0, 10]],
            "asks": [[100.02, 10]],
            "raw_sha256": "live-funding-exit",
            "funding_prints": prints,
        },
    }
    cost = {
        "symbol": "NVDAUSDT",
        "side": 1,
        "opened_at": opened.isoformat(),
        "horizon_hours": 24,
        "entry_book_hash": "earlier-book",
        "fee_rate": float(contract["taker_fee_rate"]),
        "funding_interval_hours": interval,
        "entry": {"vwap": 100.0, "qty": 1.0, "fee_usdt": 0.06, "filled_usdt": 100.0},
    }
    closed = close_later(cost, [exit_book], closed_at)
    assert len(in_window) == 3
    assert closed["cost_json"]["funding_source"] == "venue_funding"
    assert closed["cost_json"]["funding_settlements"] == 3
    assert closed["cost_json"]["funding_rates"] == [row["rate"] for row in in_window]
    assert closed["cost_json"]["funding_usdt"] == round(100.0 * sum(row["rate"] for row in in_window), 6)
    assert closed["cost_json"]["outcome_bp"] is not None
