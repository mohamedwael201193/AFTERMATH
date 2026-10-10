"""Event, evidence, and decision snapshot identifiers. UTC, schema version 1."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone


SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def payload_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def event_id(source: str, instrument_id: str, event_type: str, event_time_utc: str, phash: str) -> str:
    raw = f"{source}|{instrument_id}|{event_type}|{event_time_utc}|{phash}".encode()
    return "evn_" + hashlib.sha256(raw).hexdigest()[:24]


def evidence_id(event: str, phash: str, schema_version: int = SCHEMA_VERSION) -> str:
    raw = f"{event}|{phash}|{schema_version}".encode()
    return "ev_" + hashlib.sha256(raw).hexdigest()[:24]


def snapshot_hash(schema_version: int, prompt_hash: str, rows: list[tuple[str, str]]) -> str:
    lines = [f"{schema_version}|{prompt_hash}"]
    for eid, phash in rows:
        lines.append(f"{eid}:{phash}")
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()
