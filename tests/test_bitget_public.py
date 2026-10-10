from datetime import datetime, timezone

import pytest

from aftermath_api.connectors import BitgetConnector

pytestmark = pytest.mark.live


def test_public_nvda_contract_and_closed_candles(tmp_path):
    connector = BitgetConnector(tmp_path)
    contract = connector.contract("NVDAUSDT")
    assert contract["symbol"] == "NVDAUSDT"
    assert contract["status"] == "normal"
    assert contract["is_rwa"] in ("YES", "NO")
    assert 0 <= contract["taker_fee_rate"] <= 0.01
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    rows = connector.candles("NVDAUSDT", end_ms=end_ms, limit=30)
    assert len(rows) >= 1
    assert rows[0][1] > 0
    assert rows[-1][0] + 3_600_000 <= end_ms
