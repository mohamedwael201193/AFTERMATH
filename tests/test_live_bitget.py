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
