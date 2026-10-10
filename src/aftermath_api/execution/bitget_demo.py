"""Bitget Demo orders. Disabled unless the environment and the feature flag both allow it."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

DEMO_PATH = "/api/v3/trade/place-order"
# Live strategy symbols are separate. Demo support is not assumed for a symbol that has not been verified.
DEMO_SYMBOLS = frozenset({
    "NVDAUSDT",
    "TSLAUSDT",
    "AAPLUSDT",
    "AMZNUSDT",
    "METAUSDT",
    "GOOGLUSDT",
    "COINUSDT",
    "MSTRUSDT",
})


class DemoDisabled(Exception):
    pass


def client_oid(decision_id: str) -> str:
    return "afm-" + hashlib.sha256(decision_id.encode()).hexdigest()[:24]


def sign_request(secret: str, timestamp: str, method: str, path: str, body: str) -> str:
    payload = f"{timestamp}{method.upper()}{path}{body}"
    digest = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def submit_demo_order(order: dict, transport, env: dict[str, str], *, now_ms: int) -> dict:
    """Return a status. A disabled flag or the wrong environment never calls transport."""
    if env.get("AFTERMATH_DEMO_EXEC_ENABLED") != "1":
        return {"status": "DISABLED", "submitted": False}
    if env.get("AFTERMATH_BITGET_ENV") != "demo":
        return {"status": "REFUSED", "reason": "bitget_env_not_demo", "submitted": False}
    symbol = str(order.get("symbol") or "")
    if symbol not in DEMO_SYMBOLS:
        return {"status": "REFUSED", "reason": "symbol_not_in_demo_universe", "submitted": False}
    key = env.get("BITGET_DEMO_API_KEY") or ""
    secret = env.get("BITGET_DEMO_API_SECRET") or ""
    passphrase = env.get("BITGET_DEMO_API_PASSPHRASE") or ""
    if not key or not secret or not passphrase:
        return {"status": "REFUSED", "reason": "demo_credentials_missing", "submitted": False}
    decision_id = str(order.get("decision_id") or "")
    if not decision_id:
        return {"status": "REFUSED", "reason": "decision_id_missing", "submitted": False}
    body = json.dumps({
        "category": "USDT-FUTURES",
        "symbol": symbol,
        "side": order.get("side"),
        "orderType": "market",
        "qty": order.get("qty"),
        "clientOid": client_oid(decision_id),
    }, separators=(",", ":"))
    timestamp = str(now_ms)
    headers = {
        "ACCESS-KEY": key,
        "ACCESS-SIGN": sign_request(secret, timestamp, "POST", DEMO_PATH, body),
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": passphrase,
        "Content-Type": "application/json",
        "paptrading": "1",
    }
    try:
        response = transport("POST", DEMO_PATH, headers, body)
    except TimeoutError:
        return {"status": "UNKNOWN", "submitted": False, "client_oid": client_oid(decision_id)}
    return {
        "status": "SUBMITTED" if response.get("ok") else "REJECTED",
        "submitted": bool(response.get("ok")),
        "client_oid": client_oid(decision_id),
        "order_id": response.get("order_id"),
    }
