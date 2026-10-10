"""One paper cycle. It records a refusal when core evidence is incomplete. It does not invent fills."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from .decide import abstain
from .errors import ApiError
from .ids import SCHEMA_VERSION, event_id, evidence_id, payload_hash, utc_now
from .receipts import issue_receipt

WHITELIST = (
    "AAPLUSDT",
    "AMZNUSDT",
    "COINUSDT",
    "GOOGLUSDT",
    "METAUSDT",
    "MSFTUSDT",
    "MSTRUSDT",
    "NVDAUSDT",
    "TSLAUSDT",
)


def fetch_live(cache_dir: Path) -> tuple[list[dict], list[str]]:
    from .connectors import BitgetConnector

    connector = BitgetConnector(cache_dir, mode="live")
    observations: list[dict] = []
    errors: list[str] = []
    for symbol in WHITELIST:
        try:
            observations.append(connector.ticker(symbol))
        except ApiError as exc:
            errors.append(exc.code)
    return observations, errors


def persist_observation(store, body: dict) -> dict:
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
        "conflict": False,
        "created_at_utc": utc_now(),
    })
    evid = evidence_id(event["id"], phash)
    evidence = store.insert_evidence({
        "id": evid,
        "event_id": event["id"],
        "schema_version": SCHEMA_VERSION,
        "payload_hash": phash,
        "included_at_utc": utc_now(),
    })
    return {"event": event, "evidence": evidence}


def run_paper_cycle(settings, store, *, fetch=None, signing_path: str = "") -> dict:
    now = datetime.now(timezone.utc)
    key = "paper-cycle:" + now.strftime("%Y-%m-%dT%H")
    existing = store.decision_for_key(key)
    if existing:
        decision = store.get_decision(existing)
        receipt = store.receipt_for_decision(existing)
        if store.run_for_key(key) is None:
            store.insert_run({
                "id": "run_" + uuid.uuid4().hex[:16],
                "idempotency_key": key,
                "status": "refused" if decision["status"] == "ABSTAIN" else decision["status"],
                "reason": decision["reason"],
                "decision_id": existing,
                "started_at_utc": decision["created_at_utc"],
                "finished_at_utc": utc_now(),
                "detail": {"observations": len(decision.get("evidence_ids") or []), "model_calls": 0, "recovered": True},
            })
        return {
            "idempotency_key": key,
            "decision_id": existing,
            "repeated": True,
            "reason": decision.get("reason"),
            "receipt_id": None if receipt is None else receipt["id"],
        }
    observations: list[dict] = []
    errors: list[str] = []
    if fetch is not None:
        observations, errors = fetch()
    elif settings.env != "test":
        cache = Path("/tmp/aftermath-cache") if Path("/tmp").is_dir() else Path(".") / "cache"
        cache.mkdir(parents=True, exist_ok=True)
        observations, errors = fetch_live(cache)
    links = []
    if not observations:
        result = abstain("source_unavailable" if errors else "scheduled_no_new_evidence", [])
    else:
        rows = []
        for obs in observations:
            saved = persist_observation(store, obs)
            evid = saved["evidence"]["id"]
            rows.append((evid, saved["evidence"]["payload_hash"]))
            links.append(evid)
        result = abstain("missing_order_book", rows)
    did = "dec_" + uuid.uuid4().hex[:24]
    store.insert_decision({
        "id": did,
        "status": result["status"],
        "decision_source": result["decision_source"],
        "prompt_hash": result["prompt_hash"],
        "input_snapshot_hash": result["input_snapshot_hash"],
        "schema_version": SCHEMA_VERSION,
        "reason": result["reason"],
        "idempotency_key": key,
        "created_at_utc": utc_now(),
    }, [{"decision_id": did, "evidence_id": evid, "position": i} for i, evid in enumerate(links)])
    receipt = None
    path = Path(signing_path) if signing_path else None
    if path is not None and path.is_file():
        final = store.get_decision(did)
        receipt = issue_receipt(store, path, {
            "decision_id": final["id"],
            "status": final["status"],
            "reason": final["reason"],
            "input_snapshot_hash": final["input_snapshot_hash"],
            "evidence_ids": final["evidence_ids"],
            "prompt_hash": final["prompt_hash"],
            "model": "absent",
        })
    store.insert_run({
        "id": "run_" + uuid.uuid4().hex[:16],
        "idempotency_key": key,
        "status": "refused" if result["status"] == "ABSTAIN" else result["status"],
        "reason": result["reason"],
        "decision_id": did,
        "started_at_utc": now.isoformat(),
        "finished_at_utc": utc_now(),
        "detail": {"observations": len(observations), "fetch_errors": len(errors), "model_calls": 0},
    })
    return {
        "idempotency_key": key,
        "decision_id": did,
        "repeated": False,
        "reason": result["reason"],
        "receipt_id": None if receipt is None else receipt["id"],
    }
