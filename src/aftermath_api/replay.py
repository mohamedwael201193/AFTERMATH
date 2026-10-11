"""Historical replay of one paper cycle. It is not a live outcome.

`run_paper_cycle` binds its clock with `datetime.now`, and `decide_bounded`
calls `core_blockers` without forwarding a clock. A past filing would therefore
be `stale_evidence` and fail `event_fresh`. This module calls the same
production functions in that cycle's order, with the clock pinned to the
historical decision time, and withholds every later book from the model.
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import Settings
from .cycle import (
    _decide_or_abstain,
    _document_ready,
    advance_positions,
    persist_observation,
)
from .execution_context import PAPER_EQUITY
from .ids import SCHEMA_VERSION
from .metrics import evaluate
from .positions import advance_positions as advance_positions_later
from .positions import paired_from_fills, summarize
from .receipts import chain_intact, verify_line
from .sources.edgar import MAX_EVENT_AGE
from .store import MemoryStore, PostgresStore

MODE = "historical_replay"
ASSUMED_SPREAD_BP = 2.0
SPREAD_NOTE = (
    "Bitget does not publish historical order books. The mid is the candle open "
    "for the decision and entry books, and the candle close for the exit book at "
    "entry+24h. Bid and ask are that mid widened by a fixed 2.0 bp. Depth is the "
    "closed candle's quote volume. spread_source is assumed; book_source is candle_proxy."
)
BAR_MS = {"1m": 60_000, "5m": 300_000, "1H": 3_600_000}


class LookaheadError(AssertionError):
    """Raised when a replay input uses data from after the decision time."""


def book_from_candle(
    *,
    symbol: str,
    row: list,
    granularity: str,
    price_field: str,
    kind: str,
) -> dict:
    """Build one book observation from a closed history-candles row.

    The book is timestamped at the bar close, which is when quote volume is
    known. Entry and decision mids are the bar open. The exit mid is the bar
    close. The spread is the recorded assumption above, not a venue book.
    """
    if granularity not in BAR_MS:
        raise ValueError("unsupported candle granularity")
    if price_field not in ("open", "close"):
        raise ValueError("price_field must be open or close")
    try:
        open_ms = int(row[0])
        open_px, _high, _low, close_px, base_vol, quote_vol = (float(item) for item in row[1:7])
    except (TypeError, ValueError, IndexError) as exc:
        raise ValueError("candle row is not a history-candles tuple") from exc
    mid = open_px if price_field == "open" else close_px
    if mid <= 0 or open_px <= 0 or close_px <= 0:
        raise ValueError("candle price invalid")
    bar_ms = BAR_MS[granularity]
    open_at = datetime.fromtimestamp(open_ms / 1000, timezone.utc)
    close_at = datetime.fromtimestamp((open_ms + bar_ms) / 1000, timezone.utc)
    price_at = open_at if price_field == "open" else close_at
    half = mid * ASSUMED_SPREAD_BP / 2.0 / 1e4
    bid = mid - half
    ask = mid + half
    quote = float(quote_vol)
    digest = hashlib.sha256(
        f"{symbol}|{granularity}|{open_ms}|{price_field}|{kind}|{mid:.8f}|{quote:.8f}".encode()
    ).hexdigest()
    bid_qty = quote / bid if quote > 0 else 0.0
    ask_qty = quote / ask if quote > 0 else 0.0
    return {
        "source": "bitget-history-candles",
        "instrument_id": symbol,
        "event_type": "book",
        "event_time_utc": price_at.isoformat(),
        "fetched_at_utc": close_at.isoformat(),
        "mapping_confidence": 1.0,
        "payload": {
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "spread_bp": ASSUMED_SPREAD_BP,
            "depth_usdt": quote,
            "bids": [[bid, bid_qty]],
            "asks": [[ask, ask_qty]],
            "raw_sha256": digest,
            "taker_fee_rate": 0.0006,
            "book_source": "candle_proxy",
            "spread_source": "assumed",
            "spread_assumption_bp": ASSUMED_SPREAD_BP,
            "spread_note": SPREAD_NOTE,
            "price_field": price_field,
            "candle_open_ms": open_ms,
            "candle_close_ms": open_ms + bar_ms,
            "granularity": granularity,
            "quote_vol": quote,
            "base_vol": float(base_vol),
            "mode": MODE,
            "counted_outcome": False,
            "prospective": False,
            "kind": kind,
        },
    }


def run_historical_replay(
    filing: dict,
    *,
    now: datetime,
    books: list[dict],
    market_context: dict,
    funding_rates: list[float] | None,
    model_transport,
    signing_path: str,
    store=None,
) -> dict:
    """Run one isolated historical paper lifecycle. Never opens Postgres."""
    store = _memory_store(store)
    moment = _aware(now)
    _assert_filing_window(filing, moment)
    decision_books, entry_book, exit_book = _split_books(books, moment)
    observations = [_stamp(book) for book in decision_books] + [_stamp(filing)]
    _assert_model_inputs(moment, observations, market_context)
    _assert_funding_window(entry_book, exit_book, funding_rates)

    recorded: dict = {}
    settings = _replay_settings(getattr(model_transport, "llm_model", None))
    accession = str((filing.get("payload") or {}).get("accession") or "unknown")
    key = "historical_replay:" + accession + ":" + moment.strftime("%Y-%m-%dT%H:%M")
    with _pinned_runtime(moment, recorded):
        advance_positions(store, observations, moment, signing_path=signing_path)
        links: list[str] = []
        loaded: list[dict] = []
        rows: list[tuple[str, str]] = []
        for obs in observations:
            saved = persist_observation(store, obs)
            evid = saved["evidence"]["id"]
            phash = saved["evidence"]["payload_hash"]
            links.append(evid)
            rows.append((evid, phash))
            loaded.append({
                "id": evid,
                "payload_hash": phash,
                "facts": obs.get("payload") or {},
                "event": {**obs, "payload_hash": phash},
            })
        result, model_calls = _decide_or_abstain(
            settings,
            store,
            observations,
            loaded,
            rows,
            moment,
            model_transport,
            lambda _symbol, at: _market_at(market_context, moment, at),
        )
        did = "dec_" + _short()
        store.insert_decision({
            "id": did,
            "status": result["status"],
            "decision_source": result["decision_source"],
            "prompt_hash": result["prompt_hash"],
            "input_snapshot_hash": result["input_snapshot_hash"],
            "schema_version": SCHEMA_VERSION,
            "reason": result["reason"],
            "idempotency_key": key,
            "created_at_utc": moment.isoformat(),
            "mode": MODE,
            "payload": {"mode": MODE, "counted_outcome": False, "prospective": False},
        }, [{"decision_id": did, "evidence_id": evid, "position": index} for index, evid in enumerate(links)])
        fill_key = key + ":entry"
        if result.get("pending_entry"):
            store.insert_fill({
                "id": "fill_" + _short(),
                "decision_id": did,
                "idempotency_key": fill_key,
                "status": "PENDING_ENTRY",
                "cost_json": {
                    **result["pending_entry"],
                    "mode": MODE,
                    "counted_outcome": False,
                    "prospective": False,
                },
                "created_at_utc": moment.isoformat(),
            })
        from .receipts import issue_receipt

        decision = store.get_decision(did)
        if Path(signing_path).is_file():
            issue_receipt(store, Path(signing_path), {
                "decision_id": decision["id"],
                "status": decision["status"],
                "reason": decision["reason"],
                "input_snapshot_hash": decision["input_snapshot_hash"],
                "evidence_ids": decision["evidence_ids"],
                "prompt_hash": decision["prompt_hash"],
                "model": settings.llm_model if result["decision_source"] == "model" else "absent",
            })
        store.insert_run({
            "id": "run_" + _short(),
            "idempotency_key": key,
            "status": "refused" if result["status"] == "ABSTAIN" else result["status"],
            "reason": result["reason"],
            "decision_id": did,
            "started_at_utc": moment.isoformat(),
            "finished_at_utc": moment.isoformat(),
            "detail": {
                "mode": MODE,
                "counted_outcome": False,
                "prospective": False,
                "observations": len(observations),
                "model_calls": model_calls,
                "hf1": None,
            },
        })
        fill = _advance_later(store, fill_key, entry_book, exit_book, funding_rates, signing_path)

    return _report(
        store,
        filing,
        moment,
        decision_books[-1] if decision_books else None,
        entry_book,
        exit_book,
        result,
        recorded.get("proposal"),
        recorded.get("verdict"),
        fill,
        model_calls,
        signing_path,
        _document_ready(filing),
    )


def _advance_later(store, fill_key: str, entry_book: dict, exit_book: dict | None, funding_rates, signing_path: str):
    pending = store.fill_for_key(fill_key)
    if pending is None:
        return None
    entry_time = _parse(entry_book.get("fetched_at_utc"))
    advance_positions_later(store, [entry_book], entry_time, signing_path=signing_path)
    opened = store.fill_for_key(fill_key)
    if opened is None or opened.get("status") != "PAPER_FILLED" or exit_book is None:
        return opened
    cost = dict(opened.get("cost_json") or {})
    cost["mode"] = MODE
    cost["counted_outcome"] = False
    cost["prospective"] = False
    if funding_rates is not None:
        cost["funding_rates"] = [float(rate) for rate in funding_rates]
    store.update_fill(opened["id"], cost_json=cost)
    exit_time = _parse(exit_book.get("fetched_at_utc"))
    advance_positions_later(store, [exit_book], exit_time, signing_path=signing_path)
    closed = store.fill_for_key(fill_key)
    if closed is not None and closed.get("status") != "CLOSED":
        from .positions import close_later

        probed = close_later(dict(closed.get("cost_json") or {}), [exit_book], exit_time)
        if probed.get("error"):
            failed = dict(closed.get("cost_json") or {})
            failed["exit_error"] = probed["error"]
            failed["mode"] = MODE
            store.update_fill(closed["id"], cost_json=failed)
            closed = store.fill_for_key(fill_key)
    return closed


def _report(
    store,
    filing,
    moment,
    decision_book,
    entry_book,
    exit_book,
    result,
    governed_proposal,
    verdict,
    fill,
    model_calls,
    signing_path,
    document_ready,
) -> dict:
    payload = filing.get("payload") or {}
    proposal = result.get("proposal") if isinstance(result.get("proposal"), dict) else governed_proposal
    if not isinstance(proposal, dict):
        proposal = {}
    action = proposal.get("action")
    cost = {} if fill is None else (fill.get("cost_json") or {})
    public = _public_path(signing_path)
    receipt_rows = []
    verified = []
    if hasattr(store, "receipts"):
        for row in store.receipts.values():
            receipt = store.get_receipt(row["id"])
            ok = bool(public is not None and receipt is not None and verify_line(public, receipt["line"]))
            receipt_rows.append(row["id"])
            verified.append({"id": row["id"], "verified": ok})
    lines = store.list_ledger()
    intact = bool(public is not None and lines and chain_intact(public, lines))
    pairs = paired_from_fills(store.list_fills())
    decision_id = next(
        (row["id"] for row in store.decisions.values() if str(row.get("idempotency_key") or "").startswith("historical_replay:")),
        None,
    )
    return {
        "mode": MODE,
        "counted_outcome": False,
        "prospective": False,
        "store": "MemoryStore",
        "accession": payload.get("accession"),
        "acceptance_time": filing.get("event_time_utc"),
        "document_sha256": payload.get("document_sha256"),
        "document_ready": document_ready,
        "decision_time": moment.isoformat(),
        "decision": {
            "id": decision_id,
            "status": result.get("status"),
            "reason": result.get("reason"),
            "action": action,
            "side": {"LONG": 1, "SHORT": -1}.get(action),
            "confidence": proposal.get("confidence"),
            "reasons": [result.get("reason")] if result.get("reason") else [],
            "unbound_numbers": result.get("unbound_numbers") or [],
        },
        "governor": None if verdict is None else {
            "verdict": verdict.get("verdict"),
            "reasons": verdict.get("reasons"),
            "checks": verdict.get("checks"),
            "size_frac": verdict.get("size_frac"),
        },
        "entry": _leg(entry_book, (cost.get("entry") or None), cost.get("opened_at"), cost.get("entry_ref")),
        "exit": _leg(exit_book, (cost.get("exit") or None), cost.get("closed_at"), (cost.get("exit") or {}).get("ref_mid")),
        "fees_usdt": cost.get("fees_usdt"),
        "funding_usdt": cost.get("funding_usdt"),
        "funding_source": cost.get("funding_source"),
        "funding_settlements": cost.get("funding_settlements"),
        "outcome_bp": cost.get("outcome_bp"),
        "fill_status": None if fill is None else fill.get("status"),
        "receipt_ids": receipt_rows,
        "receipt_verification": verified,
        "receipts_verify": [row["verified"] for row in verified],
        "chain_intact": intact,
        "model_calls": model_calls,
        "metrics": evaluate(pairs),
        "summary": summarize(store.list_fills()),
        "decision_book": _leg(decision_book, None, None, (decision_book or {}).get("payload", {}).get("mid") if decision_book else None),
        "steps": _steps(),
        "equity_usdt": PAPER_EQUITY,
    }


def _leg(book, walk, time_key, ref) -> dict | None:
    if book is None and walk is None:
        return None
    payload = {} if book is None else (book.get("payload") or {})
    price = None if not isinstance(walk, dict) else walk.get("vwap")
    if price is None:
        price = ref if ref is not None else payload.get("mid")
    return {
        "time": time_key or (None if book is None else book.get("fetched_at_utc")),
        "price_time": None if book is None else book.get("event_time_utc"),
        "price": price,
        "candle_mid": payload.get("mid"),
        "source": None if book is None else book.get("source"),
        "book_source": payload.get("book_source"),
        "spread_source": payload.get("spread_source"),
        "spread_assumption_bp": payload.get("spread_assumption_bp"),
        "price_field": payload.get("price_field"),
        "granularity": payload.get("granularity"),
    }


def _steps() -> dict:
    return {
        "native": [
            "cycle.persist_observation",
            "cycle._decide_or_abstain",
            "decide.decide_bounded with prompts/decision_v3.txt, schema checks, the daily cap, and numnorm",
            "cycle._hold_if_approved",
            "execution_context.derive_execution",
            "paper.govern (vendored governor_check)",
            "positions.advance_positions, enter_later, close_later, and _funding",
            "paper.paper_fill (vendored walk_book)",
            "receipts.issue_receipt, verify_line, and chain_intact",
            "positions.paired_from_fills, positions.summarize, and metrics.evaluate",
        ],
        "replay_wrapped": [
            "run_paper_cycle is not called. It sets now = datetime.now(timezone.utc), so a past filing fails core_blockers stale_evidence (90 minutes) and the governor event_fresh limit (360 minutes).",
            "The wrapper runs that function's persist, decide, govern, receipt, and run steps in the same order and passes the historical decision time into every function that accepts it.",
            "gate.datetime.now, execution_context.datetime.now, positions.datetime.now, and cycle.utc_now are pinned to the decision time for the call. decide_bounded calls core_blockers() with no clock, and enter_later calls derive_execution() with no clock.",
            "receipts.issue_receipt is wrapped only to stamp mode, counted_outcome, and prospective on the production ledger body. The signature is the production signature.",
            "Entry uses the first book strictly after the decision time. Exit uses the first book at or after entry+24h. Those later books are passed only to positions.advance_positions, never to the model or the governor.",
            "H-HF-1 scan_live is not called. In run_paper_cycle it is a separate scan and it cannot change the S-A decision; the live scanner also reads the current book.",
            "The store is a fresh MemoryStore. PostgresStore is refused before any method call. DATABASE_URL is not read.",
        ],
    }


def _market_at(market_context: dict, decision_time: datetime, at: datetime) -> dict:
    if _aware(at) > decision_time:
        raise LookaheadError("market fetch is after the decision time")
    _assert_model_inputs(decision_time, [], market_context)
    return market_context


def _assert_filing_window(filing: dict, now: datetime) -> None:
    event_time = _parse(filing.get("event_time_utc"))
    if event_time is None:
        raise LookaheadError("filing has no acceptance time")
    if event_time > now or now - event_time > MAX_EVENT_AGE:
        raise LookaheadError("decision time is outside the 360 minute acceptance window")


def _split_books(books: list[dict], now: datetime):
    parsed = []
    for book in books:
        if book.get("event_type") not in (None, "book"):
            raise LookaheadError("books must be book observations")
        fetched = _parse(book.get("fetched_at_utc"))
        if fetched is None:
            raise LookaheadError("book missing fetched_at_utc")
        parsed.append((fetched, book))
    parsed.sort(key=lambda item: item[0])
    decision = [book for ts, book in parsed if ts <= now]
    later = [(ts, book) for ts, book in parsed if ts > now]
    if not later:
        raise LookaheadError("entry book is not strictly after decision time")
    entry_ts, entry = later[0]
    if any(ts < entry_ts for ts, _book in later):
        raise LookaheadError("entry book is not the first book after decision time")
    entry_event = _parse(entry.get("event_time_utc"))
    if entry_ts <= now or (entry_event is not None and entry_event <= now):
        raise LookaheadError("entry book is not strictly after decision time")
    if decision:
        latest = max(decision, key=lambda book: _parse(book.get("fetched_at_utc")))
        decision = [latest]
    horizon = entry_ts + timedelta(hours=24)
    exits = [(ts, book) for ts, book in parsed if ts >= horizon]
    exit_book = None if not exits else exits[0][1]
    if exit_book is not None and exits[0][0] < horizon:
        raise LookaheadError("exit book is before entry+24h")
    return decision, entry, exit_book


def _assert_funding_window(entry_book: dict, exit_book: dict | None, funding_rates) -> None:
    if exit_book is None:
        return
    prints = (exit_book.get("payload") or {}).get("funding_prints")
    if not prints:
        return
    opened = _parse(entry_book.get("fetched_at_utc"))
    closed = _parse(exit_book.get("fetched_at_utc"))
    if opened is None or closed is None or closed < opened + timedelta(hours=24):
        raise LookaheadError("exit book is before entry+24h")
    parsed = []
    previous = None
    for item in prints:
        if not isinstance(item, dict) or item.get("rate") is None:
            raise LookaheadError("funding print missing a rate")
        ts = _parse(item.get("funding_time_utc"))
        if ts is None or not (opened < ts <= closed):
            raise LookaheadError("funding settlement outside the entry-exit window")
        if previous is not None and ts < previous:
            raise LookaheadError("funding settlements are not chronological")
        previous = ts
        parsed.append(float(item["rate"]))
    if funding_rates is None or len(list(funding_rates)) != len(parsed):
        raise LookaheadError("funding_rates do not match the in-window settlements")
    for given, printed in zip(funding_rates, parsed):
        if abs(float(given) - printed) > 1e-12:
            raise LookaheadError("funding_rates do not match the in-window settlements")


def _assert_model_inputs(now: datetime, observations: list[dict], market_context: dict) -> None:
    if not isinstance(market_context, dict):
        raise LookaheadError("market context is missing")
    for obs in observations:
        for key in ("event_time_utc", "fetched_at_utc"):
            ts = _parse(obs.get(key))
            if ts is not None and ts > now:
                raise LookaheadError("candle after decision time in model context")
        _walk_times(obs.get("payload") or {}, now)
    _walk_times(market_context, now)


def _walk_times(value, now: datetime, key: str = "") -> None:
    if isinstance(value, dict):
        for child_key, child in value.items():
            if child_key in ("candles", "bars"):
                _walk_candles(child, now)
            elif child_key.endswith("_utc") or child_key.endswith("_ms"):
                _assert_clock_value(child, now, child_key)
            elif child_key not in ("excerpt", "text", "thesis", "invalidation", "spread_note"):
                _walk_times(child, now, child_key)
        return
    if isinstance(value, list) and key in ("candles", "bars"):
        _walk_candles(value, now)


def _walk_candles(rows, now: datetime) -> None:
    if not isinstance(rows, list):
        return
    for row in rows:
        stamp = row[0] if isinstance(row, (list, tuple)) and row else None
        if isinstance(row, dict):
            stamp = row.get("ts_ms", row.get("open_ms", row.get("t")))
        ts = _epoch(stamp)
        if ts is not None and ts > now:
            raise LookaheadError("candle after decision time in model context")


def _assert_clock_value(value, now: datetime, key: str) -> None:
    if isinstance(value, str):
        ts = _parse(value)
        if ts is not None and ts > now:
            raise LookaheadError("candle after decision time in model context")
        return
    ts = _epoch(value)
    if ts is not None and ts > now:
        raise LookaheadError("candle after decision time in model context")
    if key:
        return


def _epoch(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 10**12:
        return None
    return datetime.fromtimestamp(float(value) / 1000, timezone.utc)


def _stamp(obs: dict) -> dict:
    payload = dict(obs.get("payload") or {})
    payload["mode"] = MODE
    payload["counted_outcome"] = False
    payload["prospective"] = False
    return {**obs, "payload": payload}


def _memory_store(store):
    if store is None:
        return MemoryStore()
    if isinstance(store, PostgresStore) or type(store) is not MemoryStore:
        raise RuntimeError("historical_replay only accepts MemoryStore and does not open Postgres")
    return store


def _replay_settings(model_name: str | None) -> Settings:
    return Settings(
        env="test",
        database_url="",
        direct_url="",
        llm_api_key="historical-replay",
        llm_base_url="https://replay.invalid/v1",
        llm_model=model_name or "historical-replay-transport",
        llm_configured=True,
        reader_token="",
        decision_token="",
        job_token="",
        signing_key_path="",
        sec_user_agent="",
        web_origin="",
        decisions="model",
        llm_daily_cap=3,
    )


@contextmanager
def _pinned_runtime(moment: datetime, recorded: dict):
    import aftermath_api.cycle as cycle
    import aftermath_api.execution_context as execution_context
    import aftermath_api.gate as gate
    import aftermath_api.ids as ids
    import aftermath_api.positions as positions
    import aftermath_api.receipts as receipts

    clock = _PinnedClock(moment)

    def utc_now() -> str:
        return moment.astimezone(timezone.utc).isoformat(timespec="milliseconds")

    def issuing(store, path, body):
        stamped = dict(body)
        stamped["mode"] = MODE
        stamped["counted_outcome"] = False
        stamped["prospective"] = False
        return saved["issue"](store, path, stamped)

    def governing(proposal, ctx):
        _walk_times(ctx, moment)
        verdict = saved["govern"](proposal, ctx)
        recorded["proposal"] = proposal
        recorded["verdict"] = verdict
        return verdict

    saved = {
        "gate": gate.datetime,
        "execution": execution_context.datetime,
        "positions": positions.datetime,
        "ids_utc": ids.utc_now,
        "cycle_utc": cycle.utc_now,
        "issue": receipts.issue_receipt,
        "govern": cycle.govern,
    }
    gate.datetime = clock
    execution_context.datetime = clock
    positions.datetime = clock
    ids.utc_now = utc_now
    cycle.utc_now = utc_now
    receipts.issue_receipt = issuing
    cycle.govern = governing
    try:
        yield
    finally:
        gate.datetime = saved["gate"]
        execution_context.datetime = saved["execution"]
        positions.datetime = saved["positions"]
        ids.utc_now = saved["ids_utc"]
        cycle.utc_now = saved["cycle_utc"]
        receipts.issue_receipt = saved["issue"]
        cycle.govern = saved["govern"]


class _PinnedClock:
    def __init__(self, moment: datetime):
        self._moment = moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)

    def now(self, tz=None):
        if tz is None:
            return self._moment.replace(tzinfo=None)
        return self._moment.astimezone(tz)

    def fromisoformat(self, value):
        return datetime.fromisoformat(value)


def _public_path(signing_path: str) -> Path | None:
    path = Path(signing_path)
    if not path.is_file():
        return None
    public = path.with_suffix(".pub")
    if public.is_file():
        return public
    return None


def _short() -> str:
    import uuid

    return uuid.uuid4().hex[:16]


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse(value) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
