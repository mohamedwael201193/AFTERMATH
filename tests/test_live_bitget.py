"""Live public market data. This file is the only test that calls Bitget."""

from pathlib import Path

import pytest

from aftermath_api.connectors import BitgetConnector


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
