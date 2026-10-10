from aftermath_api.execution.bitget_demo import client_oid, submit_demo_order


def _env(**overrides):
    base = {
        "AFTERMATH_DEMO_EXEC_ENABLED": "0",
        "AFTERMATH_BITGET_ENV": "demo",
        "BITGET_DEMO_API_KEY": "test-key",
        "BITGET_DEMO_API_SECRET": "test-secret",
        "BITGET_DEMO_API_PASSPHRASE": "test-pass",
    }
    base.update(overrides)
    return base


def _order():
    return {"decision_id": "dec_123", "symbol": "NVDAUSDT", "side": "buy", "qty": "0.01"}


def test_demo_orders_stay_disabled_by_default():
    called = []

    def transport(*args):
        called.append(args)
        return {"ok": True}

    result = submit_demo_order(_order(), transport, _env(), now_ms=1)
    assert result["status"] == "DISABLED"
    assert result["submitted"] is False
    assert called == []


def test_live_environment_cannot_sign_a_demo_order():
    called = []
    result = submit_demo_order(
        _order(),
        lambda *args: called.append(args),
        _env(AFTERMATH_DEMO_EXEC_ENABLED="1", AFTERMATH_BITGET_ENV="live"),
        now_ms=1,
    )
    assert result["reason"] == "bitget_env_not_demo"
    assert called == []


def test_enabled_demo_order_sends_the_paper_header_and_stable_client_oid():
    seen = {}

    def transport(method, path, headers, body):
        seen.update({"method": method, "path": path, "headers": headers, "body": body})
        return {"ok": True, "order_id": "demo-1"}

    result = submit_demo_order(_order(), transport, _env(AFTERMATH_DEMO_EXEC_ENABLED="1"), now_ms=1787033528294)
    assert result["status"] == "SUBMITTED"
    assert seen["headers"]["paptrading"] == "1"
    assert seen["headers"]["ACCESS-KEY"] == "test-key"
    assert result["client_oid"] == client_oid("dec_123")
    assert result["client_oid"] == "afm-" + __import__("hashlib").sha256(b"dec_123").hexdigest()[:24]
    again = submit_demo_order(_order(), transport, _env(AFTERMATH_DEMO_EXEC_ENABLED="1"), now_ms=1787033528294)
    assert again["client_oid"] == result["client_oid"]


def test_timeout_is_unknown_and_msft_is_outside_the_demo_universe():
    def transport(*_args):
        raise TimeoutError("timed out")

    unknown = submit_demo_order(_order(), transport, _env(AFTERMATH_DEMO_EXEC_ENABLED="1"), now_ms=1)
    assert unknown["status"] == "UNKNOWN"
    assert unknown["submitted"] is False
    refused = submit_demo_order(
        {**_order(), "symbol": "MSFTUSDT"},
        transport,
        _env(AFTERMATH_DEMO_EXEC_ENABLED="1"),
        now_ms=1,
    )
    assert refused["reason"] == "symbol_not_in_demo_universe"
