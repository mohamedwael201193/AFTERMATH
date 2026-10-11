"""Public forward paper log. Replay, fixtures, and Studio rows never enter it."""

from __future__ import annotations

import csv
import io
from html import escape

from .execution_context import PAPER_EQUITY

TRADE_COLUMNS = (
    "timestamp_utc",
    "instrument",
    "direction",
    "entry_price",
    "exit_price",
    "quantity",
    "notional",
    "fees",
    "spread_bp",
    "slippage_bp",
    "funding",
    "net_pnl",
    "balance_change",
    "trade_status",
    "strategy_version",
    "decision_id",
    "demo_order_id",
    "venue",
)
CYCLE_COLUMNS = (
    "timestamp_utc",
    "decision_id",
    "status",
    "reason",
    "model_calls",
    "record_class",
)
EXCLUDED = {"historical_replay", "fixture", "getagent_studio"}
STRATEGY = "S-A"


def trade_rows(fills: list[dict]) -> list[dict]:
    chosen = []
    seen_decisions = set()
    seen_orders = set()
    for fill in sorted(fills, key=_fill_time):
        row = _trade_row(fill)
        if row is None:
            continue
        decision = row["decision_id"]
        order = row["demo_order_id"]
        if decision and decision in seen_decisions:
            continue
        if order and order in seen_orders:
            continue
        if decision:
            seen_decisions.add(decision)
        if order:
            seen_orders.add(order)
        chosen.append(row)
    balance = PAPER_EQUITY
    for row in chosen:
        if row["trade_status"] != "CLOSED" or row["net_pnl"] == "":
            row["balance_change"] = ""
            continue
        change = float(row["net_pnl"])
        balance = round(balance + change, 6)
        row["balance_change"] = _num(change)
    return chosen


def cycle_rows(runs: list[dict]) -> list[dict]:
    rows = []
    for run in sorted(runs, key=lambda item: str(item.get("started_at_utc") or "")):
        row = _cycle_row(run)
        if row is not None:
            rows.append(row)
    return rows


def to_csv(columns: tuple[str, ...], rows: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in columns})
    return buffer.getvalue()


def closed_outcome_count(rows: list[dict]) -> int:
    return sum(1 for row in rows if row.get("trade_status") == "CLOSED" and row.get("net_pnl") != "")


def methodology_html(trades: list[dict], cycles: list[dict]) -> str:
    closed = closed_outcome_count(trades)
    opened = sum(1 for row in trades if row.get("trade_status") == "OPEN")
    if closed == 0:
        blocker = (
            "No forward paper trade has closed. AFTERMATH records a trade only after a real Item 2.02 filing "
            "is accepted, the model decides, the risk governor approves, and the paper position is entered and "
            "closed on later books with measured fees and funding. That filing has not occurred. "
            "Open rows, when any exist, are not outcomes. Empty cells are missing measurements, not zeros."
        )
    else:
        blocker = f"{closed} closed forward paper trades are in the ledger. They are paper results, not a profitability claim."
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AFTERMATH paper trading log</title>
</head>
<body>
<main>
<h1>Paper trading log</h1>
<p>This page is a public read-only view of the prospective ledger. It does not accept orders.</p>
<p>{escape(blocker)}</p>
<ul>
<li><a href="/paper-trading-log.csv">Trade log</a>: {len(trades)} forward rows, {closed} closed, {opened} open.</li>
<li><a href="/paper-cycle-log.csv">Cycle log</a>: {len(cycles)} no-trade or refusal cycles. These are not fills.</li>
</ul>
<p>The venue is <code>internal_paper</code> or <code>bitget_demo</code>. Historical replay, fixtures, backtests, and GetAgent Studio records are excluded. The registered strategy is S-A and is unchanged. A positive funding rate is a cost for a long and a credit for a short. The paper account starts at {int(PAPER_EQUITY)} USDT. A balance change is the closed net P&amp;L only.</p>
</main>
</body>
</html>
"""


def _trade_row(fill: dict) -> dict | None:
    cost = fill.get("cost_json") or {}
    if not isinstance(cost, dict):
        return None
    venue = _venue(fill, cost)
    if venue is None:
        return None
    strategy = cost.get("strategy_id") or STRATEGY
    if strategy != STRATEGY:
        return None
    status = str(fill.get("status") or "")
    entry = cost.get("entry") if isinstance(cost.get("entry"), dict) else {}
    exit_leg = cost.get("exit") if isinstance(cost.get("exit"), dict) else {}
    direction = _direction(cost)
    fees = _measured(cost.get("fees_usdt"))
    if fees is None and status != "CLOSED":
        fees = _measured(entry.get("fee_usdt"))
    funding = _measured(cost.get("funding_usdt")) if status == "CLOSED" else None
    net = _reconciled_net(cost) if status == "CLOSED" else None
    trade_status = _trade_status(status, net)
    if trade_status == "CLOSED" and (fees is None or funding is None or net is None):
        trade_status = "INCOMPLETE"
        net = None
    return {
        "timestamp_utc": cost.get("opened_at") or cost.get("closed_at") or fill.get("created_at_utc") or "",
        "instrument": cost.get("symbol") or "",
        "direction": direction,
        "entry_price": _measured(entry.get("vwap")) or "",
        "exit_price": _measured(exit_leg.get("vwap")) if trade_status == "CLOSED" else "",
        "quantity": _measured(entry.get("qty")) or "",
        "notional": _measured(entry.get("filled_usdt") if entry else cost.get("notional")) or "",
        "fees": "" if fees is None else _num(fees),
        "spread_bp": _spread(cost, trade_status),
        "slippage_bp": _slippage(entry, exit_leg if trade_status == "CLOSED" else {}),
        "funding": "" if funding is None else _num(funding),
        "net_pnl": "" if net is None else _num(net),
        "balance_change": "",
        "trade_status": trade_status,
        "strategy_version": STRATEGY,
        "decision_id": fill.get("decision_id") or "",
        "demo_order_id": "" if venue != "bitget_demo" else str(cost.get("demo_order_id") or ""),
        "venue": venue,
    }


def _cycle_row(run: dict) -> dict | None:
    key = str(run.get("idempotency_key") or "")
    detail = run.get("detail") if isinstance(run.get("detail"), dict) else {}
    mode = str(detail.get("mode") or "").lower()
    if key.startswith("historical_replay:") or mode in EXCLUDED:
        return None
    calls = detail.get("model_calls")
    return {
        "timestamp_utc": run.get("started_at_utc") or "",
        "decision_id": run.get("decision_id") or "",
        "status": run.get("status") or "",
        "reason": run.get("reason") or "",
        "model_calls": "" if calls is None else calls,
        "record_class": "forward_cycle",
    }


def _venue(fill: dict, cost: dict) -> str | None:
    key = str(fill.get("idempotency_key") or "")
    mode = str(cost.get("mode") or "").strip().lower()
    if key.startswith("historical_replay:") or mode in EXCLUDED:
        return None
    if mode == "bitget_demo" or cost.get("demo_order_id"):
        return "bitget_demo"
    if mode in ("", "internal_paper"):
        return "internal_paper"
    return None


def _direction(cost: dict) -> str:
    action = cost.get("action")
    if action in ("LONG", "SHORT"):
        return action
    side = cost.get("side")
    if side == 1:
        return "LONG"
    if side == -1:
        return "SHORT"
    return ""


def _trade_status(status: str, net) -> str:
    if status == "PAPER_FILLED":
        return "OPEN"
    if status == "PENDING_ENTRY":
        return "PENDING"
    if status == "CLOSED" and net is not None:
        return "CLOSED"
    if status == "CLOSED":
        return "INCOMPLETE"
    return "PENDING"


def _reconciled_net(cost: dict):
    try:
        gross = float(cost["gross_usdt"])
        fees = float(cost["fees_usdt"])
        funding = float(cost["funding_usdt"])
        stored = float(cost["net_usdt"])
    except (KeyError, TypeError, ValueError):
        return None
    recomputed = round(gross - fees - funding, 6)
    if abs(recomputed - round(stored, 6)) > 1e-4:
        return None
    return recomputed


def _spread(cost: dict, trade_status: str) -> str:
    values = []
    for key in ("entry_spread_bp", "exit_spread_bp"):
        if key == "exit_spread_bp" and trade_status != "CLOSED":
            continue
        measured = _measured(cost.get(key))
        if measured is not None:
            values.append(measured)
    if not values:
        return ""
    return _num(sum(values) / len(values))


def _slippage(entry: dict, exit_leg: dict) -> str:
    values = []
    notionals = []
    for leg in (entry, exit_leg):
        measured = _measured(leg.get("slippage_bp"))
        filled = _measured(leg.get("filled_usdt"))
        if measured is None or filled is None:
            continue
        values.append(abs(measured) * filled)
        notionals.append(filled)
    if not values or sum(notionals) <= 0:
        return ""
    return _num(sum(values) / sum(notionals))


def _measured(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _num(value: float) -> str:
    text = f"{round(float(value), 6):.6f}".rstrip("0").rstrip(".")
    if text in ("", "-"):
        return "0"
    return text


def _fill_time(fill: dict) -> str:
    cost = fill.get("cost_json") or {}
    return str(cost.get("opened_at") or fill.get("created_at_utc") or "")
