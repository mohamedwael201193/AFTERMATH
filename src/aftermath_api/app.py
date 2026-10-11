"""HTTP application. Health is real. Writes fail closed when a required store or key is absent."""

from __future__ import annotations

import json
import logging
import math
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .auth import require_decision, require_job, require_reader
from .config import ROOT, Settings, load_settings
from .cycle import run_paper_cycle
from .decide import abstain
from .errors import ApiError, error_body, install_errors
from .gate import core_blockers, has_order_book
from .identity import accept_mapping, resolve_symbol
from .ids import SCHEMA_VERSION, event_id, evidence_id, payload_hash, utc_now
from .paper import govern, paper_fill
from .metrics import evaluate
from .positions import paired_from_fills, summarize
from .receipts import chain_intact, issue_receipt, verify_line
from .store import MemoryStore, PostgresStore

SECRET_RE = re.compile(r"(?i)(bearer\s+\S+|postgresql://\S+|rnd_\S+|vcp_\S+|ghp_\S+|k1\S+)")
log = logging.getLogger("aftermath")


def _redact(text: str) -> str:
    return SECRET_RE.sub("[redacted]", text)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact(str(record.msg))
        return True


def _signing_ready(settings: Settings) -> bool:
    return bool(settings.signing_key_path) and Path(settings.signing_key_path).is_file()


def _run_is_stale(run: dict | None) -> bool:
    if not run or not run.get("finished_at_utc"):
        return True
    try:
        finished = datetime.fromisoformat(str(run["finished_at_utc"]))
    except ValueError:
        return True
    if finished.tzinfo is None:
        finished = finished.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - finished > timedelta(hours=2)


def _public_key(settings: Settings) -> Path | None:
    if settings.signing_key_path:
        sibling = Path(settings.signing_key_path).with_suffix(".pub")
        if sibling.is_file():
            return sibling
    fallback = ROOT / "keys" / "production_ed25519.pub"
    return fallback if fallback.is_file() else None


class RateLimiter:
    def __init__(self, limit: int = 120):
        self.limit = limit
        self.hits: dict[str, list[float]] = {}

    def allow(self, key: str, now: float) -> bool:
        window = [stamp for stamp in self.hits.get(key, []) if now - stamp < 60]
        if len(window) >= self.limit:
            self.hits[key] = window
            return False
        window.append(now)
        self.hits[key] = window
        return True


def create_app(settings: Settings | None = None, store=None) -> FastAPI:
    settings = settings or load_settings()
    if store is None:
        store = PostgresStore(settings.database_url) if settings.database_url and settings.env != "test" else MemoryStore()
    app = FastAPI(title="AFTERMATH", version="0.1.0")
    if settings.web_origin:
        app.add_middleware(CORSMiddleware, allow_origins=[settings.web_origin], allow_methods=["GET", "POST"], allow_headers=["Authorization", "Idempotency-Key", "Content-Type"])
    install_errors(app)
    logging.getLogger().addFilter(RedactingFilter())
    app.state.settings = settings
    app.state.store = store
    app.state.limiter = RateLimiter()

    def reader(request: Request) -> None:
        require_reader(settings, request.headers.get("authorization"))
        if not app.state.limiter.allow("reader", time.monotonic()):
            raise ApiError("SOURCE_UNAVAILABLE", "rate limit", 429, retryable=True)

    @app.middleware("http")
    async def _log(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        log.info(json.dumps({"path": request.url.path, "status": response.status_code}))
        return response

    @app.get("/health")
    def health():
        return {"status": "ok", "env": settings.env}

    @app.get("/ready")
    def ready():
        problems = []
        if settings.env == "prod" and not settings.database_url:
            problems.append("database")
        elif settings.database_url:
            try:
                if not store.ping():
                    problems.append("database")
            except Exception:
                problems.append("database")
        if settings.env == "prod" and not _signing_ready(settings):
            problems.append("signing_key")
        body = {
            "ready": not problems,
            "problems": problems,
            "llm": "configured" if settings.llm_configured else "absent",
            "decisions": settings.decisions,
        }
        if problems:
            return JSONResponse(body, status_code=503)
        return body

    @app.get("/v1/events")
    def events(request: Request, limit: int = 50, cursor: str | None = None):
        reader(request)
        if limit < 1 or limit > 200:
            raise ApiError("SCHEMA", "limit out of range", 422)
        return store.list_events(limit=limit, cursor=cursor)

    @app.get("/v1/events/{event_id_}")
    def one_event(event_id_: str, request: Request):
        reader(request)
        row = store.get_event(event_id_)
        if not row:
            raise ApiError("SCHEMA", "event not found", 404)
        return row

    @app.get("/v1/instruments/{symbol}")
    def instrument(symbol: str, request: Request):
        reader(request)
        rows = [row for row in store.list_events(limit=200)["items"] if row["instrument_id"] == symbol]
        if not rows:
            raise ApiError("UNMAPPED_SYMBOL", "no observation", 404)
        latest = rows[0]
        fetched = datetime.fromisoformat(latest["fetched_at_utc"])
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - fetched).total_seconds() > 60:
            raise ApiError("STALE", "latest observation is older than 60 seconds", 409)
        return latest

    @app.get("/v1/evidence/{evidence_id_}")
    def one_evidence(evidence_id_: str, request: Request):
        reader(request)
        row = store.get_evidence(evidence_id_)
        if not row:
            raise ApiError("SCHEMA", "evidence not found", 404)
        return row

    @app.get("/v1/decisions/{decision_id}")
    def one_decision(decision_id: str, request: Request):
        reader(request)
        row = store.get_decision(decision_id)
        if not row:
            raise ApiError("SCHEMA", "decision not found", 404)
        receipt = store.receipt_for_decision(row["id"])
        return {
            **row,
            "model_called": row.get("decision_source") == "model",
            "receipt_id": None if receipt is None else receipt["id"],
        }

    @app.get("/v1/decisions")
    def decision_list(request: Request, limit: int = 50):
        reader(request)
        if limit < 1 or limit > 200:
            raise ApiError("SCHEMA", "limit out of range", 422)
        return {"items": store.list_decision_headers(limit=limit)}

    @app.get("/v1/paper/fills")
    def fills(request: Request):
        reader(request)
        return {"items": store.list_fills()}

    @app.get("/v1/receipts/{receipt_id}")
    def one_receipt(receipt_id: str, request: Request):
        reader(request)
        row = store.get_receipt(receipt_id)
        if not row:
            raise ApiError("SCHEMA", "receipt not found", 404)
        return row

    @app.post("/v1/receipts/{receipt_id}/verify")
    async def verify(receipt_id: str, request: Request):
        reader(request)
        row = store.get_receipt(receipt_id)
        if not row:
            raise ApiError("SCHEMA", "receipt not found", 404)
        pub = _public_key(settings)
        supplied = None
        if request.headers.get("content-type", "").startswith("application/json"):
            raw = await request.body()
            if raw:
                try:
                    supplied = json.loads(raw).get("line")
                except json.JSONDecodeError as exc:
                    raise ApiError("SCHEMA", "verify body is not json", 422) from exc
        if supplied is not None:
            ok = bool(pub and verify_line(pub, supplied) and supplied.get("line_hash") == row["line"]["line_hash"])
            return {"id": receipt_id, "verified": ok, "ots_status": row["ots_status"], "checked": "supplied_copy"}
        lines = store.list_ledger()
        ok = bool(pub and chain_intact(pub, lines) and any(line["line_hash"] == row["line"]["line_hash"] for line in lines))
        return {"id": receipt_id, "verified": ok, "ots_status": row["ots_status"], "checked": "stored"}

    @app.post("/v1/receipts/{receipt_id}/replay")
    def replay(receipt_id: str, request: Request):
        reader(request)
        row = store.get_receipt(receipt_id)
        if not row:
            raise ApiError("SCHEMA", "receipt not found", 404)
        pub = _public_key(settings)
        lines = store.list_ledger()
        signature_ok = bool(pub and verify_line(pub, row["line"]))
        chain_ok = bool(pub and chain_intact(pub, lines))
        return {
            "id": receipt_id,
            "signature_ok": signature_ok,
            "chain_ok": chain_ok,
            "ots_status": row["ots_status"],
            "anchor": "unconfirmed" if row["ots_status"] in ("pending", "not_anchored") else row["ots_status"],
            "llm_reproduction": "not_available",
            "deterministic_checks": ["signature", "hash_chain"],
        }

    @app.get("/v1/ops/status")
    def ops_status(request: Request):
        reader(request)
        counts = store.dashboard_counts()
        run = counts["latest_run"]
        sec = "configured" if settings.sec_user_agent else "disabled"
        return {
            "latest_run": run,
            "scheduler": "external_hourly_post",
            "schedule": "github_actions_hourly",
            "continuous_operation": False,
            "stale": _run_is_stale(run),
            "fill_count": counts["fill_count"],
            "decision_count": counts["decision_count"],
            "event_count": counts["event_count"],
            "book_count": counts["book_count"],
            "precedent_count": counts["precedent_count"],
            "paper_only": True,
            "kill_switch": os.environ.get("AFTERMATH_KILL") == "1",
            "sources": {"sec_edgar": {"status": sec, "reason": None if settings.sec_user_agent else "sec_user_agent_missing"}},
        }

    @app.get("/v1/metrics")
    def metrics(request: Request):
        reader(request)
        body = summarize(store.list_fills())
        body["evaluation"] = evaluate(paired_from_fills(store.list_fills()))
        return body

    @app.post("/v1/decisions")
    async def decisions(request: Request):
        require_decision(settings, request.headers.get("authorization"))
        if settings.env == "prod" and not _signing_ready(settings):
            raise ApiError("SOURCE_UNAVAILABLE", "signing_key missing", 503)
        key = request.headers.get("idempotency-key")
        if not key:
            raise ApiError("SCHEMA", "Idempotency-Key required", 422)
        prior_id = store.decision_for_key(key)
        if prior_id:
            return {
                "decision": store.get_decision(prior_id),
                "fill": store.fill_for_key(key),
                "receipt": store.receipt_for_decision(prior_id),
            }
        body = await request.json()
        from .execution_context import caller_controlled, derive_execution

        if settings.env == "prod" and caller_controlled(body):
            raise ApiError("SCHEMA", "caller cannot set execution inputs", 422)
        ids = body.get("evidence_ids")
        if not isinstance(ids, list) or not ids:
            raise ApiError("INSUFFICIENT_EVIDENCE", "evidence_ids required", 422)
        loaded = []
        for eid in ids:
            ev = store.get_evidence(eid)
            if not ev:
                raise ApiError("INSUFFICIENT_EVIDENCE", "unknown evidence", 422)
            event = ev["event"]
            if event.get("conflict"):
                loaded.append({**ev, "facts": {}})
                continue
            loaded.append({"id": ev["id"], "payload_hash": ev["payload_hash"], "facts": event["payload"], "event": event})
        from .decide import decide

        events = [ev["event"] for ev in loaded]
        blocker = core_blockers(events)
        calls = getattr(app.state, "decider_calls", None)
        if blocker:
            rows = [(ev["id"], ev["payload_hash"]) for ev in loaded]
            result = abstain(blocker, rows)
        elif not settings.llm_configured:
            decider = getattr(app.state, "decider", decide)
            if calls is not None:
                calls.append("decider")
            result = decider(settings, loaded)
        elif not has_order_book(events):
            rows = [(ev["id"], ev["payload_hash"]) for ev in loaded]
            result = abstain("missing_order_book", rows)
        else:
            decider = getattr(app.state, "decider", decide)
            if calls is not None:
                calls.append("decider")
            result = decider(settings, loaded)
        now = utc_now()
        did = "dec_" + uuid.uuid4().hex[:24]
        row = {
            "id": did,
            "status": result["status"],
            "decision_source": result["decision_source"],
            "prompt_hash": result["prompt_hash"],
            "input_snapshot_hash": result["input_snapshot_hash"],
            "schema_version": result["schema_version"],
            "reason": result["reason"],
            "idempotency_key": key,
            "created_at_utc": now,
        }
        links = [{"decision_id": did, "evidence_id": eid, "position": i} for i, eid in enumerate(ids)]
        if body.get("input_snapshot_hash") and body["input_snapshot_hash"] != result["input_snapshot_hash"]:
            raise ApiError("SCHEMA", "input_snapshot_hash mismatch", 422)
        saved = store.insert_decision(row, links)
        fill = None
        receipt = None
        if result["status"] == "PAPER_PROPOSED" and result.get("proposal"):
            supplied = caller_controlled(body)
            if settings.env == "prod" or not supplied:
                derived = derive_execution(result["proposal"], events, result["decision_source"])
                if derived["error"]:
                    saved = store.update_decision(saved["id"], status="RISK_REJECTED", reason=derived["error"])
                else:
                    try:
                        verdict = govern(result["proposal"], derived["context"])
                    except (KeyError, TypeError, ValueError):
                        saved = store.update_decision(saved["id"], status="RISK_REJECTED", reason="invalid_risk_context")
                        verdict = None
                    if verdict is None:
                        pass
                    elif verdict["verdict"] != "APPROVED":
                        saved = store.update_decision(saved["id"], status="RISK_REJECTED", reason=",".join(verdict.get("reasons") or []))
                    else:
                        notional = float(verdict["size_frac"]) * float(derived["context"]["equity"])
                        fill = store.insert_fill({
                            "id": "fill_" + uuid.uuid4().hex[:16],
                            "decision_id": saved["id"],
                            "idempotency_key": key,
                            "status": "PENDING_ENTRY",
                            "cost_json": {
                                "symbol": result["proposal"]["symbol"],
                                "action": result["proposal"]["action"],
                                "side": derived["side"],
                                "notional": notional,
                                "horizon_hours": float(result["proposal"].get("horizon_hours") or 24),
                                "proposal_book_hash": derived["book_hash"],
                                "proposal_fetched_at": derived["proposal_fetched_at"],
                                "fee_rate": derived["fee_rate"],
                            },
                            "created_at_utc": now,
                        })
                        saved = store.update_decision(saved["id"], status="AWAITING_NEXT_BOOK", reason="awaiting_next_book")
            else:
                ctx = body.get("risk_context") or {}
                try:
                    verdict = govern(result["proposal"], ctx)
                except (KeyError, TypeError, ValueError):
                    saved = store.update_decision(saved["id"], status="RISK_REJECTED", reason="invalid_risk_context")
                    verdict = None
                if verdict is None:
                    pass
                elif verdict["verdict"] != "APPROVED":
                    saved = store.update_decision(saved["id"], status="RISK_REJECTED", reason=",".join(verdict.get("reasons") or []))
                else:
                    requested = float(body.get("notional", 0))
                    cap = float(verdict["size_frac"]) * float(ctx.get("equity") or 0)
                    notional = requested if not math.isfinite(requested) else min(requested, cap)
                    walk = paper_fill(
                        int(body.get("side", 1)),
                        notional,
                        float(body.get("ref_price", 0)),
                        body.get("book") or {"bids": [], "asks": []},
                        float(body.get("fee_rate", 0)),
                    )
                    fill = store.insert_fill({
                        "id": "fill_" + uuid.uuid4().hex[:16],
                        "decision_id": saved["id"],
                        "idempotency_key": key,
                        "status": walk["status"],
                        "cost_json": walk,
                        "created_at_utc": now,
                    })
                    saved = store.update_decision(saved["id"], status=walk["status"])
        if _signing_ready(settings):
            try:
                final = store.get_decision(saved["id"])
                receipt = issue_receipt(store, Path(settings.signing_key_path), {
                    "decision_id": final["id"],
                    "status": final["status"],
                    "reason": final["reason"],
                    "input_snapshot_hash": final["input_snapshot_hash"],
                    "evidence_ids": final["evidence_ids"],
                    "prompt_hash": final["prompt_hash"],
                    "model": settings.llm_model if result["decision_source"] == "model" else "absent",
                })
            except Exception:
                if store.receipt_for_decision(saved["id"]) is None:
                    store.abandon_unsigned(saved["id"])
                raise ApiError("SOURCE_UNAVAILABLE", "signing failed", 503)
        return {"decision": store.get_decision(saved["id"]), "fill": fill, "receipt": receipt}

    @app.post("/internal/jobs/paper-cycle")
    def paper_cycle(request: Request):
        require_job(settings, request.headers.get("authorization"))
        fetcher = getattr(app.state, "cycle_fetch", None)
        return run_paper_cycle(
            settings,
            store,
            fetch=fetcher,
            signing_path=settings.signing_key_path,
            event_fetch=getattr(app.state, "event_fetch", None),
            model_transport=getattr(app.state, "model_transport", None),
        )

    @app.post("/v1/events")
    async def ingest(request: Request):
        require_decision(settings, request.headers.get("authorization"))
        body = await request.json()
        if settings.env == "prod" and (
            str(body.get("instrument_id", "")).startswith("fixture:")
            or str(body.get("source", "")).lower() == "fixture"
        ):
            raise ApiError("SCHEMA", "fixture instruments are refused", 422)
        symbol, _mapped, reason = resolve_symbol(str(body.get("instrument_id", "")))
        if symbol is None:
            raise ApiError("UNMAPPED_SYMBOL", reason or "unmapped", 422)
        body["instrument_id"] = symbol
        confidence = float(body.get("mapping_confidence", 1.0))
        if not accept_mapping(confidence):
            raise ApiError("UNMAPPED_SYMBOL", "mapping confidence below 0.9", 422)
        event_time = datetime.fromisoformat(body["event_time_utc"])
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        if event_time > datetime.now(timezone.utc) + timedelta(seconds=5):
            raise ApiError("SCHEMA", "future event", 422)
        phash = payload_hash(body["payload"])
        eid = event_id(body["source"], body["instrument_id"], body["event_type"], body["event_time_utc"], phash)
        event = store.insert_event({
            "id": eid,
            "instrument_id": body["instrument_id"],
            "event_type": body["event_type"],
            "event_time_utc": body["event_time_utc"],
            "fetched_at_utc": body["fetched_at_utc"],
            "source": body["source"],
            "schema_version": SCHEMA_VERSION,
            "payload": body["payload"],
            "payload_hash": phash,
            "mapping_confidence": body.get("mapping_confidence", 1.0),
            "conflict": bool(body.get("conflict", False)),
            "created_at_utc": utc_now(),
        })
        evid = evidence_id(event["id"], phash)
        ev = store.insert_evidence({
            "id": evid,
            "event_id": event["id"],
            "schema_version": SCHEMA_VERSION,
            "payload_hash": phash,
            "included_at_utc": utc_now(),
        })
        return {"event": event, "evidence": ev}

    return app


def error_for_tests(code: str, message: str) -> dict:
    return error_body(code, message)
