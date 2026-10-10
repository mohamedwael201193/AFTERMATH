"""Paper position lifecycle. Entry uses a later book than the proposal snapshot."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .execution_context import derive_execution
from .paper import paper_fill

MIN_CLOSED = 30
FALLBACK_FUNDING_8H = 0.0001


def advance_positions(store, observations: list[dict], now: datetime) -> None:
    books = [row for row in observations if row.get("event_type") == "book"]
    for fill in list(store.list_fills()):
        cost = dict(fill.get("cost_json") or {})
        if fill.get("status") == "PENDING_ENTRY":
            opened = enter_later(cost, books)
            if opened.get("error"):
                continue
            store.update_fill(fill["id"], status=opened["status"], cost_json=opened["cost_json"])
        elif fill.get("status") == "PAPER_FILLED" and cost.get("outcome_bp") is None:
            closed = close_later(cost, books, now)
            if closed.get("error"):
                continue
            store.update_fill(fill["id"], status="CLOSED", cost_json=closed["cost_json"])


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
    funding, settlements = _funding(float(entry["filled_usdt"]), opened, closed_at)
    fees = float(entry["fee_usdt"]) + float(exit_walk["walk"]["fee_usdt"])
    net = gross - fees - funding
    filled = float(entry["filled_usdt"])
    return {
        "status": "CLOSED",
        "cost_json": {
            **cost,
            "exit": exit_walk["walk"],
            "exit_book_hash": derived["book_hash"],
            "closed_at": book.get("fetched_at_utc"),
            "gross_usdt": round(gross, 6),
            "fees_usdt": round(fees, 6),
            "funding_usdt": round(funding, 6),
            "funding_settlements": settlements,
            "funding_source": "fallback_1bp_per_8h",
            "net_usdt": round(net, 6),
            "outcome_bp": round(net / filled * 1e4, 4) if filled else None,
        },
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


def _funding(notional: float, start: datetime, end: datetime) -> tuple[float, int]:
    settlements = int((end - start).total_seconds() // (8 * 3600))
    return notional * FALLBACK_FUNDING_8H * max(settlements, 0), max(settlements, 0)


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
