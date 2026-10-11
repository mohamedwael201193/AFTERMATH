"""Paper position lifecycle. Entry uses a later book than the proposal snapshot."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from .execution_context import PAPER_EQUITY, derive_execution
from .paper import paper_fill

MIN_CLOSED = 30
PENDING_TTL = timedelta(hours=2)


def portfolio_state(store, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    fills = store.list_fills()
    open_rows = [row for row in fills if row.get("status") in ("PENDING_ENTRY", "PAPER_FILLED")]
    symbols = []
    gross = 0.0
    for row in open_rows:
        cost = row.get("cost_json") or {}
        symbol = cost.get("symbol")
        if symbol:
            symbols.append(str(symbol))
        entry = cost.get("entry") or {}
        try:
            gross += float(entry.get("filled_usdt") or cost.get("notional") or 0)
        except (TypeError, ValueError):
            continue
    closed = []
    for row in fills:
        if row.get("status") != "CLOSED":
            continue
        cost = row.get("cost_json") or {}
        try:
            net = float(cost["net_usdt"])
        except (KeyError, TypeError, ValueError):
            return _exposure(gross, open_rows, symbols, None, None, {})
        closed.append((str(cost.get("closed_at") or ""), str(cost.get("symbol") or ""), net))
    closed.sort()
    path = 0.0
    peak = 0.0
    worst = 0.0
    day_net = 0.0
    by_symbol: dict[str, float] = {}
    day = now.date().isoformat()
    for closed_at, symbol, net in closed:
        path += net
        peak = max(peak, path)
        worst = min(worst, path - peak)
        if closed_at.startswith(day):
            day_net += net
            by_symbol[symbol] = by_symbol.get(symbol, 0.0) + net
    return _exposure(gross, open_rows, symbols, day_net / PAPER_EQUITY, worst / PAPER_EQUITY, by_symbol)


def _exposure(gross: float, open_rows: list, symbols: list, day_pnl, drawdown, by_symbol: dict) -> dict:
    return {
        "gross_open_usdt": gross,
        "n_open": len(open_rows),
        "open_symbols": symbols,
        "symbol_pnl_today": 0.0,
        "symbol_pnl_by_symbol": {key: value / PAPER_EQUITY for key, value in by_symbol.items()},
        "day_pnl": day_pnl,
        "drawdown": drawdown,
    }


def lifecycle_intact(store, fill_id: str) -> bool:
    events = [row for row in getattr(store, "fill_events", []) if row.get("fill_id") == fill_id]
    current = next((row for row in store.list_fills() if row.get("id") == fill_id), None)
    if current is None or not events:
        return False
    last = events[-1]
    return last.get("status") == current.get("status") and last.get("cost_json") == current.get("cost_json")


def advance_positions(store, observations: list[dict], now: datetime) -> None:
    books = [row for row in observations if row.get("event_type") == "book"]
    for fill in list(store.list_fills()):
        cost = dict(fill.get("cost_json") or {})
        if fill.get("status") == "PENDING_ENTRY":
            opened = enter_later(cost, books)
            if opened.get("error"):
                if _pending_expired(fill, now):
                    store.update_fill(fill["id"], status="EXPIRED", cost_json={
                        **cost,
                        "expiry_reason": opened["error"],
                        "expired_at": now.isoformat(),
                    })
                continue
            store.update_fill(fill["id"], status=opened["status"], cost_json=opened["cost_json"])
        elif fill.get("status") == "PAPER_FILLED" and cost.get("outcome_bp") is None:
            closed = close_later(cost, books, now)
            if closed.get("error"):
                continue
            store.update_fill(fill["id"], status="CLOSED", cost_json=closed["cost_json"])


def _pending_expired(fill: dict, now: datetime) -> bool:
    created = _parse(fill.get("created_at_utc"))
    if created is None:
        return False
    return now - created > PENDING_TTL


def enter_later(pending: dict, books: list[dict]) -> dict:
    book = _later_book(books, pending.get("symbol"), pending.get("proposal_book_hash"), pending.get("proposal_fetched_at"))
    if book is None:
        return {"error": "no_later_book"}
    proposal = {"action": pending.get("action"), "symbol": pending.get("symbol")}
    derived = derive_execution(proposal, [book], "model")
    if derived["error"]:
        return {"error": derived["error"]}
    walk = paper_fill(int(pending["side"]), float(pending["notional"]), derived["ref_price"], derived["profile"], derived["fee_rate"])
    if walk["status"] != "PAPER_FILLED":
        return {"error": walk.get("reason") or "unfilled"}
    return {
        "status": "PAPER_FILLED",
        "cost_json": {
            **pending,
            "entry": walk["walk"],
            "entry_book_hash": derived["book_hash"],
            "entry_ref": derived["ref_price"],
            "entry_profile": _json_profile(derived["profile"]),
            "opened_at": book.get("fetched_at_utc"),
            "fee_rate": derived["fee_rate"],
        },
    }


def close_later(cost: dict, books: list[dict], now: datetime) -> dict:
    opened = _parse(cost.get("opened_at"))
    if opened is None:
        return {"error": "missing_entry_time"}
    horizon = float(cost.get("horizon_hours") or 0)
    if now < opened + timedelta(hours=horizon):
        return {"error": "horizon_open"}
    book = _later_book(books, cost.get("symbol"), cost.get("entry_book_hash"), cost.get("opened_at"))
    if book is None:
        return {"error": "no_exit_book"}
    entry = cost.get("entry") or {}
    qty = float(entry.get("qty") or 0)
    if qty <= 0:
        return {"error": "missing_entry_qty"}
    derived = derive_execution({"action": "LONG" if int(cost["side"]) > 0 else "SHORT", "symbol": cost["symbol"]}, [book], "model")
    if derived["error"]:
        return {"error": derived["error"]}
    exit_walk = paper_fill(-int(cost["side"]), qty * derived["ref_price"], derived["ref_price"], derived["profile"], derived["fee_rate"])
    if exit_walk["status"] != "PAPER_FILLED":
        return {"error": "exit_unfilled"}
    closed_at = _parse(book.get("fetched_at_utc")) or now
    gross = int(cost["side"]) * qty * (float(exit_walk["walk"]["vwap"]) - float(entry["vwap"]))
    funding, settlements, funding_source = _funding(
        float(entry["filled_usdt"]), opened, closed_at, cost.get("funding_rates"),
    )
    fees = float(entry["fee_usdt"]) + float(exit_walk["walk"]["fee_usdt"])
    filled = float(entry["filled_usdt"])
    net = None if funding is None else gross - fees - funding
    return {
        "status": "CLOSED",
        "cost_json": {
            **cost,
            "exit": exit_walk["walk"],
            "exit_book_hash": derived["book_hash"],
            "closed_at": book.get("fetched_at_utc"),
            "gross_usdt": round(gross, 6),
            "fees_usdt": round(fees, 6),
            "funding_usdt": None if funding is None else round(funding, 6),
            "funding_settlements": settlements,
            "funding_source": funding_source,
            "net_usdt": None if net is None else round(net, 6),
            "outcome_bp": None if net is None or not filled else round(net / filled * 1e4, 4),
            "baselines": _baselines(cost, derived, opened, closed_at, cost.get("funding_rates")),
        },
    }


def paired_from_fills(fills: list[dict]) -> list[dict]:
    pairs = []
    for row in fills:
        cost = row.get("cost_json") or {}
        baselines = cost.get("baselines")
        if not isinstance(baselines, dict) or cost.get("outcome_bp") is None or not cost.get("closed_at"):
            continue
        if any(baselines.get(f"{name}_bp") is None for name in ("fixed_sign", "llm_off", "random", "no_trade")):
            continue
        pair = {
            "closed_at": cost["closed_at"],
            "agent_bp": float(cost["outcome_bp"]),
            "fixed_sign_bp": float(baselines["fixed_sign_bp"]),
            "llm_off_bp": float(baselines["llm_off_bp"]),
            "random_bp": float(baselines["random_bp"]),
            "no_trade_bp": float(baselines["no_trade_bp"]),
        }
        pair.update(_pair_cost_fields(cost))
        pairs.append(pair)
    return pairs


def _pair_cost_fields(cost: dict) -> dict:
    entry = cost.get("entry") or {}
    try:
        filled = float(entry.get("filled_usdt") or cost.get("notional") or 0)
    except (TypeError, ValueError):
        return {}
    if filled <= 0:
        return {}
    out: dict = {}
    for usdt_key, bp_key in (("fees_usdt", "fees_bp"), ("funding_usdt", "funding_bp")):
        try:
            out[bp_key] = round(float(cost[usdt_key]) / filled * 1e4, 4)
        except (KeyError, TypeError, ValueError):
            continue
    slip_usdt = 0.0
    exit_leg = cost.get("exit") or {}
    saw_slippage = False
    for leg in (entry, exit_leg):
        sbp = leg.get("slippage_bp")
        if sbp is None:
            continue
        saw_slippage = True
        try:
            leg_fill = float(leg.get("filled_usdt") or filled)
            slip_usdt += abs(float(sbp)) / 1e4 * leg_fill
        except (TypeError, ValueError):
            continue
    if saw_slippage:
        out["slippage_bp"] = round(slip_usdt / filled * 1e4, 4)
    if cost.get("risk_control_violation") is True:
        out["risk_control_violation"] = True
    return out


def _baselines(cost: dict, exit_derived: dict, opened: datetime, closed_at: datetime, rates=None) -> dict:
    no_trade = {"fixed_sign_bp": None, "llm_off_bp": 0.0, "random_bp": None, "no_trade_bp": 0.0}
    profile = _profile(cost.get("entry_profile"))
    exit_profile = exit_derived["profile"]
    entry_ref = cost.get("entry_ref")
    try:
        notional = float(cost.get("notional"))
        fee = float(cost.get("fee_rate"))
        entry_ref = float(entry_ref)
    except (TypeError, ValueError):
        return no_trade
    if profile is None:
        return no_trade
    fixed = _arm_bp(1, notional, entry_ref, profile, exit_derived["ref_price"], exit_profile, fee, opened, closed_at, rates)
    seed = hashlib.sha256(f"{cost.get('symbol')}|{cost.get('opened_at')}".encode()).digest()
    random_side = 1 if seed[0] % 2 == 0 else -1
    random_bp = _arm_bp(random_side, notional, entry_ref, profile, exit_derived["ref_price"], exit_profile, fee, opened, closed_at, rates)
    return {
        "fixed_sign_bp": fixed,
        "llm_off_bp": 0.0,
        "llm_off_policy": "identical_to_no_trade",
        "random_bp": random_bp,
        "no_trade_bp": 0.0,
    }


def _arm_bp(side: int, notional: float, entry_ref: float, entry_profile: dict, exit_ref: float, exit_profile: dict, fee: float, opened: datetime, closed_at: datetime, rates=None):
    entry = paper_fill(side, notional, entry_ref, entry_profile, fee)
    if entry["status"] != "PAPER_FILLED":
        return None
    qty = float(entry["walk"]["qty"])
    exit_walk = paper_fill(-side, qty * exit_ref, exit_ref, exit_profile, fee)
    if exit_walk["status"] != "PAPER_FILLED":
        return None
    gross = side * qty * (float(exit_walk["walk"]["vwap"]) - float(entry["walk"]["vwap"]))
    funding, _settlements, _source = _funding(float(entry["walk"]["filled_usdt"]), opened, closed_at, rates)
    if funding is None:
        return None
    net = gross - float(entry["walk"]["fee_usdt"]) - float(exit_walk["walk"]["fee_usdt"]) - funding
    filled = float(entry["walk"]["filled_usdt"])
    if filled <= 0:
        return None
    return round(net / filled * 1e4, 4)


def _json_profile(profile: dict) -> dict:
    return {
        "bids": [[float(offset), float(size)] for offset, size in profile["bids"]],
        "asks": [[float(offset), float(size)] for offset, size in profile["asks"]],
    }


def _profile(value) -> dict | None:
    if not isinstance(value, dict) or not value.get("bids") or not value.get("asks"):
        return None
    return {
        "bids": [(float(level[0]), float(level[1])) for level in value["bids"]],
        "asks": [(float(level[0]), float(level[1])) for level in value["asks"]],
    }


def summarize(fills: list[dict]) -> dict:
    closed = [row for row in fills if (row.get("cost_json") or {}).get("outcome_bp") is not None]
    sample = len(closed)
    if sample < MIN_CLOSED:
        return {
            "status": "INSUFFICIENT_DATA",
            "sample_size": sample,
            "minimum_sample": MIN_CLOSED,
            "window": None,
            "calculation_version": 1,
            "label": "observed",
            "note": "Closed paper outcomes are below the preregistered minimum of 30.",
        }
    nets = [float(row["cost_json"]["outcome_bp"]) for row in closed]
    ordered = sorted(nets)
    midpoint = ordered[sample // 2] if sample % 2 else (ordered[sample // 2 - 1] + ordered[sample // 2]) / 2
    equity = 0.0
    peak = 0.0
    drawdown = 0.0
    for value in nets:
        equity += value
        peak = max(peak, equity)
        drawdown = max(drawdown, peak - equity)
    return {
        "status": "OBSERVED",
        "sample_size": sample,
        "minimum_sample": MIN_CLOSED,
        "mean_net_bp": round(sum(nets) / sample, 4),
        "median_net_bp": round(midpoint, 4),
        "max_drawdown_bp": round(drawdown, 4),
        "label": "observed",
        "window": None,
        "calculation_version": 1,
        "note": "Observed paper outcomes. This is not a significance or profitability claim.",
    }


def _later_book(books: list[dict], symbol: str, prior_hash: str | None, prior_time: str | None) -> dict | None:
    prior = _parse(prior_time)
    chosen = None
    for book in books:
        if book.get("instrument_id") != symbol:
            continue
        payload = book.get("payload") or {}
        if prior_hash and payload.get("raw_sha256") == prior_hash:
            continue
        fetched = _parse(book.get("fetched_at_utc"))
        if prior is not None and (fetched is None or fetched <= prior):
            continue
        if chosen is None or _parse(book.get("fetched_at_utc")) < _parse(chosen.get("fetched_at_utc")):
            chosen = book
    return chosen


def _funding(notional: float, start: datetime, end: datetime, rates=None) -> tuple[float | None, int, str]:
    """Use venue prints, including a real zero. A missing series is not a 1 bp guess."""
    settlements = max(int((end - start).total_seconds() // (8 * 3600)), 0)
    if settlements == 0:
        return 0.0, 0, "no_settlement"
    if not isinstance(rates, list) or len(rates) < settlements:
        return None, settlements, "missing"
    used = rates[:settlements]
    if any(isinstance(rate, bool) or not isinstance(rate, (int, float)) for rate in used):
        return None, settlements, "missing"
    return notional * sum(float(rate) for rate in used), settlements, "venue_funding"


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
