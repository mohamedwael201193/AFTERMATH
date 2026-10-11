"""Offline instrument-category regressions. Fixtures use the field names observed on public Bitget responses."""

from datetime import datetime, timezone

import pytest

from aftermath_api.connectors import contract_from_record, funding_history_from_record, market_from_public
from aftermath_api.errors import ApiError
from aftermath_api.execution_context import derive_execution
from aftermath_api.paper import govern

V2 = "https://api.bitget.com/api/v2/mix/market/contracts"
V3 = "https://api.bitget.com/api/v3/market/instruments"


def _v2(symbol="NVDAUSDT", **overrides):
    row = {
        "symbol": symbol,
        "baseCoin": symbol.replace("USDT", ""),
        "quoteCoin": "USDT",
        "symbolStatus": "normal",
        "symbolType": "perpetual",
        "isRwa": "YES",
        "takerFeeRate": "0.0006",
        "makerFeeRate": "0.0002",
        "fundInterval": "8",
        "minTradeNum": "0.01",
        "minTradeUSDT": "5",
        "pricePlace": "2",
        "volumePlace": "2",
        "sizeMultiplier": "0.01",
    }
    row.update(overrides)
    return {
        "endpoint": "/api/v2/mix/market/contracts",
        "params": {"productType": "USDT-FUTURES", "symbol": symbol},
        "sha256": "abc",
        "data": [row],
    }


def _v3_futures(symbol="NVDAUSDT"):
    return {
        "endpoint": "/api/v3/market/instruments",
        "params": {"category": "USDT-FUTURES", "symbol": symbol},
        "sha256": "def",
        "data": [{
            "symbol": symbol,
            "category": "USDT-FUTURES",
            "status": "online",
            "symbolType": "stock",
            "type": "perpetual",
            "quoteCoin": "USDT",
            "isRwa": "YES",
            "takerFeeRate": "0.0006",
            "makerFeeRate": "0.0002",
            "fundInterval": "8",
            "minOrderQty": "0.01",
            "minOrderAmount": "5",
            "pricePrecision": "2",
            "quantityPrecision": "2",
        }],
    }


def _spot(symbol="RNVDAUSDT", **overrides):
    """SPOT shape. Live spot rows have isReality and no isRwa; isRwa here is the hostile case."""
    row = {
        "symbol": symbol,
        "category": "SPOT",
        "status": "online",
        "symbolType": "stock",
        "isReality": "yes",
        "isRwa": "YES",
        "quoteCoin": "USDT",
        "takerFeeRate": "0.001",
        "minOrderQty": "0.0001",
        "pricePrecision": "2",
        "quantityPrecision": "4",
    }
    row.update(overrides)
    return {
        "endpoint": "/api/v3/market/instruments",
        "params": {"category": "SPOT", "symbol": symbol},
        "data": [row],
    }


def _book():
    now = datetime.now(timezone.utc).isoformat()
    return {
        "instrument_id": "NVDAUSDT",
        "event_type": "book",
        "event_time_utc": now,
        "fetched_at_utc": now,
        "payload": {
            "bid": 100.0, "ask": 100.02, "mid": 100.01, "spread_bp": 2.0, "depth_usdt": 50000.0,
            "bids": [[100.0, 10.0]], "asks": [[100.02, 10.0]],
        },
    }


def _proposal():
    return {"action": "LONG", "symbol": "NVDAUSDT", "size_frac": 0.05, "confidence": 0.8, "horizon_hours": 24}


class _Candles:
    def __init__(self, contract):
        self._contract = contract

    def contract(self, symbol):
        assert symbol == self._contract["symbol"]
        return self._contract

    def candles(self, symbol, *, end_ms, limit=1000):
        return [[index * 3_600_000, 100 * (1.001 ** index)] for index in range(40)]


def test_futures_record_with_valid_fields_passes():
    parsed = contract_from_record(_v2(), "NVDAUSDT")
    assert parsed["status"] == "normal"
    assert parsed["is_rwa"] == "YES"
    assert parsed["taker_fee_rate"] == pytest.approx(0.0006)
    assert parsed["funding_interval_hours"] == 8
    assert parsed["price_precision"] == 2
    assert parsed["quantity_precision"] == 2
    assert parsed["min_order_qty"] == pytest.approx(0.01)
    assert parsed["instrument_category"] == "USDT-FUTURES"
    assert parsed["metadata_source"] == V2
    assert parsed["field_sources"]["is_rwa"] == {"category": "USDT-FUTURES", "endpoint": V2, "field": "isRwa"}
    assert parsed["field_sources"]["taker_fee_rate"]["field"] == "takerFeeRate"
    assert parsed["field_sources"]["min_order_qty"]["field"] == "minTradeNum"
    assert "?" not in parsed["metadata_source"]

    v3 = contract_from_record(_v3_futures(), "NVDAUSDT")
    assert v3["status"] == "normal"
    assert v3["venue_status"] == "online"
    assert v3["symbol_type"] == "stock"
    assert v3["contract_type"] == "perpetual"
    assert v3["is_rwa"] == "YES"
    assert v3["metadata_source"] == V3
    assert v3["field_sources"]["price_precision"]["field"] == "pricePrecision"
    assert v3["field_sources"]["min_order_qty"]["field"] == "minOrderQty"
    assert v3["funding_interval_hours"] == 8

    btc = _v2("BTCUSDT", isRwa="NO", baseCoin="BTC", pricePlace="1", volumePlace="4", minTradeNum="0.0001")
    assert contract_from_record(btc, "BTCUSDT")["is_rwa"] == "NO"

    naked = _v2()
    naked["data"][0].pop("isRwa")
    naked["data"][0]["isReality"] = "yes"
    with pytest.raises(ApiError) as naked_error:
        contract_from_record(naked, "NVDAUSDT")
    assert "isRwa" in naked_error.value.message

    built = market_from_public(_Candles(parsed), "NVDAUSDT", 40 * 3_600_000, 4)
    derived = derive_execution(_proposal(), [_book()], "model", market=built)
    assert derived["error"] is None
    assert derived["fee_rate"] == pytest.approx(0.0006)
    context = derived["context"]
    assert context["instrument_category"] == "USDT-FUTURES"
    assert context["metadata_source"] == V2
    assert context["funding_interval_hours"] == 8
    assert context["price_precision"] == 2
    assert context["quantity_precision"] == 2
    assert context["min_order_qty"] == pytest.approx(0.01)
    assert context["quote_coin"] == "USDT"
    assert context["contract"] == {"status": "normal", "is_rwa": "YES"}
    assert context["field_sources"]["funding_interval_hours"]["field"] == "fundInterval"
    verdict = govern(_proposal(), context)
    assert verdict["verdict"] == "APPROVED"
    tradeable = next(item for item in verdict["checks"] if item["check"] == "contract_tradeable")
    assert tradeable["pass"] is True
    assert tradeable["value"]["is_rwa"] == "YES"


def test_spot_record_is_refused_for_a_futures_decision():
    with pytest.raises(ApiError) as spot_error:
        contract_from_record(_spot(), "RNVDAUSDT")
    assert "USDT-FUTURES" in spot_error.value.message
    live_shape = _spot()
    del live_shape["data"][0]["isRwa"]
    del live_shape["data"][0]["takerFeeRate"]
    with pytest.raises(ApiError) as live_spot_error:
        contract_from_record(live_shape, "RNVDAUSDT")
    assert "USDT-FUTURES" in live_spot_error.value.message

    derived = derive_execution(
        _proposal(),
        [_book()],
        "model",
        market={
            "instrument_category": "SPOT",
            "metadata_source": V3,
            "contract": {"status": "normal", "is_rwa": "YES", "taker_fee_rate": 0.0006},
            "n_precedents": 4,
            "hedge_r2": 0.4,
            "hedge_beta": 0.9,
        },
    )
    assert derived["error"] == "incomplete_market:category"
    assert "context" not in derived
    assert derived.get("fee_rate") is None


def test_futures_record_with_mismatched_symbol_is_refused():
    rec = _v2()
    rec["data"][0]["symbol"] = "TSLAUSDT"
    with pytest.raises(ApiError) as row_error:
        contract_from_record(rec, "NVDAUSDT")
    assert "symbol mismatch" in row_error.value.message
    rec = _v2()
    rec["params"]["symbol"] = "QQQUSDT"
    with pytest.raises(ApiError) as param_error:
        contract_from_record(rec, "NVDAUSDT")
    assert "symbol mismatch" in param_error.value.message

    derived = derive_execution(
        _proposal(),
        [_book()],
        "model",
        market={
            "symbol": "TSLAUSDT",
            "instrument_category": "USDT-FUTURES",
            "contract": {"status": "normal", "is_rwa": "YES", "taker_fee_rate": 0.0006},
            "n_precedents": 4,
            "hedge_r2": 0.4,
            "hedge_beta": 0.9,
        },
    )
    assert derived["error"] == "incomplete_market:symbol"


def test_missing_taker_fee_is_refused_without_a_default():
    rec = _v2()
    del rec["data"][0]["takerFeeRate"]
    with pytest.raises(ApiError) as caught:
        contract_from_record(rec, "NVDAUSDT")
    assert "fee" in caught.value.message
    assert caught.value.message != "0.0006"
    assert "0.0006" not in caught.value.message

    derived = derive_execution(
        _proposal(),
        [_book()],
        "model",
        market={
            "instrument_category": "USDT-FUTURES",
            "metadata_source": V2,
            "funding_interval_hours": 8,
            "contract": {"status": "normal", "is_rwa": "YES"},
            "n_precedents": 4,
            "hedge_r2": 0.4,
            "hedge_beta": 0.9,
        },
    )
    assert derived["error"] == "incomplete_market:fee"
    assert derived.get("fee_rate") is None


def test_non_normal_status_is_refused():
    rec = _v2(symbolStatus="maintain")
    with pytest.raises(ApiError) as halted:
        contract_from_record(rec, "NVDAUSDT")
    assert "status" in halted.value.message
    offline = _v3_futures()
    offline["data"][0]["status"] = "offline"
    with pytest.raises(ApiError) as offline_error:
        contract_from_record(offline, "NVDAUSDT")
    assert "status" in offline_error.value.message

    derived = derive_execution(
        _proposal(),
        [_book()],
        "model",
        market={
            "instrument_category": "USDT-FUTURES",
            "contract": {"status": "maintain", "is_rwa": "YES", "taker_fee_rate": 0.0006},
            "n_precedents": 4,
            "hedge_r2": 0.4,
            "hedge_beta": 0.9,
        },
    )
    assert derived["error"].startswith("incomplete_market:")
    assert "contract" in derived["error"]


def test_funding_history_keeps_venue_rates_in_time_order():
    rec = {
        "params": {"productType": "USDT-FUTURES", "symbol": "NVDAUSDT"},
        "data": [
            {"symbol": "NVDAUSDT", "fundingRate": "0.0002", "fundingTime": "1760000000000"},
            {"symbol": "NVDAUSDT", "fundingRate": "-0.0001", "fundingTime": "1759971200000"},
        ],
    }
    prints = funding_history_from_record(rec, "NVDAUSDT")
    assert [row["rate"] for row in prints] == [-0.0001, 0.0002]
    assert funding_history_from_record({"params": {"productType": "USDT-FUTURES"}, "data": []}, "NVDAUSDT") == []
    with pytest.raises(ApiError) as spot:
        funding_history_from_record({"params": {"category": "SPOT"}, "data": []}, "NVDAUSDT")
    assert "USDT-FUTURES" in spot.value.message
    with pytest.raises(ApiError):
        funding_history_from_record(
            {"params": {"productType": "USDT-FUTURES"}, "data": [{"symbol": "BTCUSDT", "fundingRate": "0.0001", "fundingTime": "1760000000000"}]},
            "NVDAUSDT",
        )
