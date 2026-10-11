"""Persistence. Prod uses Postgres. Tests may use MemoryStore, which is not a live source."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


class Immutable(Exception):
    pass


def _insert_fill_event(conn, schema: str, fill_id: str, status: str, cost_json) -> None:
    """Append the lifecycle row. A missing table does not roll back the fill."""
    conn.execute("SAVEPOINT fill_event")
    try:
        conn.execute(
            f"INSERT INTO {schema}.fill_events (fill_id, status, cost_json) VALUES (%s, %s, %s)",
            (fill_id, status, cost_json),
        )
    except Exception as exc:
        conn.execute("ROLLBACK TO SAVEPOINT fill_event")
        if "fill_events" not in str(exc):
            raise
        return
    conn.execute("RELEASE SAVEPOINT fill_event")


@dataclass
class MemoryStore:
    events: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)
    decisions: dict = field(default_factory=dict)
    decision_evidence: list = field(default_factory=list)
    fills: dict = field(default_factory=dict)
    fill_events: list = field(default_factory=list)
    idempotency: dict = field(default_factory=dict)
    ledger: list = field(default_factory=list)
    receipts: dict = field(default_factory=dict)
    runs: dict = field(default_factory=dict)

    def insert_event(self, row: dict) -> dict:
        if row["id"] in self.events:
            return self.events[row["id"]]
        self.events[row["id"]] = dict(row)
        return self.events[row["id"]]

    def update_event(self, _eid: str, _payload: dict) -> None:
        raise Immutable("events are append-only")

    def get_event(self, eid: str) -> dict | None:
        return self.events.get(eid)

    def list_events(self, limit: int = 50, cursor: str | None = None) -> dict:
        rows = sorted(self.events.values(), key=lambda r: (r["event_time_utc"], r["id"]), reverse=True)
        if cursor:
            rows = [r for r in rows if (r["event_time_utc"], r["id"]) < tuple(cursor.split("|", 1))]
        page = rows[:limit]
        nxt = None
        if len(rows) > limit and page:
            last = page[-1]
            nxt = f"{last['event_time_utc']}|{last['id']}"
        return {"items": page, "next_cursor": nxt}

    def has_accession(self, accession: str) -> bool:
        for row in self.events.values():
            payload = row.get("payload") or {}
            if (
                row.get("source") == "sec-edgar"
                and payload.get("accession") == accession
                and payload.get("status") != "document_pending"
            ):
                return True
        return False

    def count_reactions(self, symbol: str | None = None) -> int:
        count = 0
        for row in self.events.values():
            if symbol is not None and (row.get("instrument_id") != symbol or row.get("source") != "sec-edgar"):
                continue
            payload = row.get("payload") or {}
            reaction = payload.get("reaction_bp")
            if payload.get("counted") is True and isinstance(reaction, (int, float)) and not isinstance(reaction, bool):
                count += 1
        return count

    def insert_evidence(self, row: dict) -> dict:
        if row["id"] in self.evidence:
            return self.evidence[row["id"]]
        self.evidence[row["id"]] = dict(row)
        return self.evidence[row["id"]]

    def get_evidence(self, eid: str) -> dict | None:
        ev = self.evidence.get(eid)
        if not ev:
            return None
        event = self.events[ev["event_id"]]
        return {**ev, "event": event}

    def ping(self) -> bool:
        return True

    def decision_for_key(self, key: str) -> str | None:
        return self.idempotency.get(key)

    def update_decision(self, did: str, **fields) -> dict:
        self.decisions[did].update(fields)
        return self.get_decision(did)

    def insert_decision(self, row: dict, links: list[dict]) -> dict:
        key = row.get("idempotency_key")
        if key and key in self.idempotency:
            return self.decisions[self.idempotency[key]]
        self.decisions[row["id"]] = dict(row)
        if key:
            self.idempotency[key] = row["id"]
        for link in links:
            self.decision_evidence.append(dict(link))
        return self.decisions[row["id"]]

    def count_decisions(self) -> int:
        return len(self.decisions)

    def list_decisions(self, limit: int = 50) -> list[dict]:
        rows = sorted(self.decisions.values(), key=lambda row: str(row.get("created_at_utc") or ""), reverse=True)
        return [self.get_decision(row["id"]) for row in rows[:limit]]

    def list_decision_headers(self, limit: int = 50) -> list[dict]:
        headers = []
        for row in self.list_decisions(limit):
            receipt = self.receipt_for_decision(row["id"])
            headers.append({
                "id": row["id"],
                "created_at_utc": row.get("created_at_utc"),
                "status": row.get("status"),
                "reason": row.get("reason"),
                "decision_source": row.get("decision_source"),
                "model_called": row.get("decision_source") == "model",
                "receipt_id": None if receipt is None else receipt["id"],
            })
        return headers

    def count_events(self) -> int:
        return len(self.events)

    def get_decision(self, did: str) -> dict | None:
        row = self.decisions.get(did)
        if not row:
            return None
        links = [x for x in self.decision_evidence if x["decision_id"] == did]
        links.sort(key=lambda x: x["position"])
        return {**row, "evidence_ids": [x["evidence_id"] for x in links]}

    def model_calls_on_day(self, day: str) -> int:
        return sum(
            1
            for row in self.decisions.values()
            if row.get("decision_source") == "model" and str(row.get("created_at_utc", "")).startswith(day)
        )

    def insert_fill(self, row: dict) -> dict:
        key = row["idempotency_key"]
        if key in self.fills:
            return self.fills[key]
        self.fills[key] = dict(row)
        self._append_fill_event(row["id"], row["status"], row["cost_json"])
        return self.fills[key]

    def fill_for_key(self, key: str) -> dict | None:
        return self.fills.get(key)

    def abandon_unsigned(self, decision_id: str) -> None:
        if self.receipt_for_decision(decision_id):
            return
        row = self.decisions.pop(decision_id, None)
        if row and row.get("idempotency_key"):
            self.idempotency.pop(row["idempotency_key"], None)
            self.fills.pop(row["idempotency_key"], None)
        self.decision_evidence = [item for item in self.decision_evidence if item["decision_id"] != decision_id]

    def insert_run(self, row: dict) -> dict:
        key = row["idempotency_key"]
        if key in self.runs:
            return self.runs[key]
        self.runs[key] = dict(row)
        return self.runs[key]

    def latest_run(self) -> dict | None:
        if not self.runs:
            return None
        return sorted(self.runs.values(), key=lambda item: item["started_at_utc"])[-1]

    def dashboard_counts(self) -> dict:
        run = self.latest_run()
        if run and run.get("decision_id"):
            receipt = self.receipt_for_decision(run["decision_id"])
            run = {**run, "receipt_id": None if receipt is None else receipt["id"]}
        opened = [row for row in self.fills.values() if row.get("status") in ("PAPER_FILLED", "CLOSED")]
        books = 0
        precedents = 0
        for row in self.events.values():
            payload = row.get("payload") or {}
            if row.get("event_type") == "book":
                books += 1
            reaction = payload.get("reaction_bp")
            if payload.get("counted") is True and isinstance(reaction, (int, float)) and not isinstance(reaction, bool):
                precedents += 1
        return {
            "latest_run": run,
            "fill_count": len(opened),
            "decision_count": len(self.decisions),
            "event_count": len(self.events),
            "book_count": books,
            "precedent_count": precedents,
        }

    def operation_status(self, *, now: datetime | None = None) -> dict:
        moment = now or datetime.now(timezone.utc)
        runs = [
            row for row in self.runs.values()
            if _started_in_lookback(row.get("started_at_utc"), moment)
        ]
        start, end = _window_bounds(runs, moment)
        decisions = [
            row for row in self.decisions.values()
            if row.get("decision_source") == "model" and _fact_in_window(row.get("idempotency_key"), row.get("created_at_utc"), moment, start, end)
        ]
        fills = [
            row for row in self.fills.values()
            if row.get("status") in ("PAPER_FILLED", "CLOSED") and _fact_in_window(row.get("idempotency_key"), row.get("created_at_utc"), moment, start, end)
        ]
        return build_operation_status(runs, decisions, len(fills), moment)

    def run_for_key(self, key: str) -> dict | None:
        return self.runs.get(key)

    def list_fills(self) -> list:
        return list(self.fills.values())

    def update_fill(self, fill_id: str, **fields) -> dict | None:
        for row in self.fills.values():
            if row.get("id") == fill_id:
                row.update(fields)
                self._append_fill_event(fill_id, row.get("status"), row.get("cost_json"))
                return row
        return None

    def _append_fill_event(self, fill_id: str, status, cost_json) -> None:
        self.fill_events.append({
            "fill_id": fill_id,
            "seq": len(self.fill_events) + 1,
            "status": status,
            "cost_json": copy.deepcopy(cost_json),
        })

    def list_ledger(self) -> list:
        return list(self.ledger)

    def last_prev(self) -> str:
        return self.ledger[-1]["line_hash"] if self.ledger else "GENESIS"

    def append_ledger(self, row: dict) -> dict:
        prev = self.last_prev()
        if row.get("prev_hash") != prev:
            raise Immutable("ledger prev_hash mismatch")
        stored = dict(row)
        stored["seq"] = len(self.ledger) + 1
        self.ledger.append(stored)
        return stored

    def receipt_for_decision(self, decision_id: str) -> dict | None:
        for rec in self.receipts.values():
            line = self.ledger[rec["ledger_seq"] - 1]
            if line["body"].get("decision_id") == decision_id:
                return {**rec, "line": line}
        return None

    def insert_receipt(self, row: dict) -> dict:
        self.receipts[row["id"]] = dict(row)
        return row

    def get_receipt(self, rid: str) -> dict | None:
        rec = self.receipts.get(rid)
        if not rec:
            return None
        line = self.ledger[rec["ledger_seq"] - 1]
        return {**rec, "line": line}


class PostgresStore:
    """Durable store. Tests must pass schema='aftermath_test' and drop only that schema."""

    def __init__(self, url: str, schema: str = "aftermath"):
        if not schema.replace("_", "").isalnum():
            raise ValueError("schema name")
        self.url = url
        self.schema = schema

    def _connect(self):
        from .db import connect

        return connect(self.url, prepare=False)

    def ping(self) -> bool:
        with self._connect() as conn:
            conn.execute("SELECT 1")
        return True

    def decision_for_key(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(f"SELECT id FROM {self.schema}.decisions WHERE idempotency_key = %s", (key,)).fetchone()
        return row[0] if row else None

    def insert_event(self, row: dict) -> dict:
        from psycopg.types.json import Json

        sql = f"""
        INSERT INTO {self.schema}.events
        (id, instrument_id, event_type, event_time_utc, fetched_at_utc, source, schema_version, payload, payload_hash, mapping_confidence, conflict, created_at_utc)
        VALUES (%(id)s, %(instrument_id)s, %(event_type)s, %(event_time_utc)s, %(fetched_at_utc)s, %(source)s, %(schema_version)s, %(payload)s, %(payload_hash)s, %(mapping_confidence)s, %(conflict)s, %(created_at_utc)s)
        ON CONFLICT (id) DO NOTHING
        """
        params = {**row, "payload": Json(row["payload"])}
        with self._connect() as conn:
            conn.execute(sql, params)
            conn.commit()
        return self.get_event(row["id"])

    def update_event(self, _eid: str, _payload: dict) -> None:
        raise Immutable("events are append-only")

    def get_event(self, eid: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(f"SELECT * FROM {self.schema}.events WHERE id = %s", (eid,)).fetchone()
        return _event_row(row) if row else None

    def list_events(self, limit: int = 50, cursor: str | None = None) -> dict:
        sql = f"SELECT * FROM {self.schema}.events"
        args: list = []
        if cursor:
            ts, eid = cursor.split("|", 1)
            sql += " WHERE (event_time_utc, id) < (%s, %s)"
            args.extend([ts, eid])
        sql += " ORDER BY event_time_utc DESC, id DESC LIMIT %s"
        args.append(limit + 1)
        with self._connect() as conn:
            rows = conn.execute(sql, args).fetchall()
        items = [_event_row(r) for r in rows[:limit]]
        nxt = None
        if len(rows) > limit and items:
            last = items[-1]
            nxt = f"{last['event_time_utc']}|{last['id']}"
        return {"items": items, "next_cursor": nxt}

    def has_accession(self, accession: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                f"""SELECT 1 FROM {self.schema}.events
                    WHERE source = 'sec-edgar'
                      AND payload->>'accession' = %s
                      AND COALESCE(payload->>'status', '') <> 'document_pending'
                    LIMIT 1""",
                (accession,),
            ).fetchone()
        return row is not None

    def count_reactions(self, symbol: str | None = None) -> int:
        sql = f"""SELECT COUNT(*) FROM {self.schema}.events
                  WHERE payload->>'counted' = 'true'
                    AND jsonb_typeof(payload->'reaction_bp') = 'number'"""
        args: list = []
        if symbol is not None:
            sql += " AND source = 'sec-edgar' AND instrument_id = %s"
            args.append(symbol)
        with self._connect() as conn:
            row = conn.execute(sql, args).fetchone()
        return int(row[0])

    def insert_evidence(self, row: dict) -> dict:
        sql = f"""
        INSERT INTO {self.schema}.evidence (id, event_id, schema_version, payload_hash, included_at_utc)
        VALUES (%(id)s, %(event_id)s, %(schema_version)s, %(payload_hash)s, %(included_at_utc)s)
        ON CONFLICT (id) DO NOTHING
        """
        with self._connect() as conn:
            conn.execute(sql, row)
            conn.commit()
        found = self.get_evidence(row["id"])
        return {k: found[k] for k in ("id", "event_id", "schema_version", "payload_hash", "included_at_utc")}

    def get_evidence(self, eid: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(f"SELECT * FROM {self.schema}.evidence WHERE id = %s", (eid,)).fetchone()
        if not row:
            return None
        ev = {"id": row[0], "event_id": row[1], "schema_version": row[2], "payload_hash": row[3], "included_at_utc": _iso(row[4])}
        event = self.get_event(ev["event_id"])
        return {**ev, "event": event}

    def insert_decision(self, row: dict, links: list[dict]) -> dict:
        key = row.get("idempotency_key")
        with self._connect() as conn:
            if key:
                existing = conn.execute(f"SELECT id FROM {self.schema}.decisions WHERE idempotency_key = %s", (key,)).fetchone()
                if existing:
                    return self.get_decision(existing[0])
            conn.execute(
                f"""INSERT INTO {self.schema}.decisions
                (id, status, decision_source, prompt_hash, input_snapshot_hash, schema_version, reason, idempotency_key, created_at_utc)
                VALUES (%(id)s, %(status)s, %(decision_source)s, %(prompt_hash)s, %(input_snapshot_hash)s, %(schema_version)s, %(reason)s, %(idempotency_key)s, %(created_at_utc)s)""",
                row,
            )
            for link in links:
                conn.execute(
                    f"INSERT INTO {self.schema}.decision_evidence (decision_id, evidence_id, position) VALUES (%s, %s, %s)",
                    (link["decision_id"], link["evidence_id"], link["position"]),
                )
            conn.commit()
        return self.get_decision(row["id"])

    def update_decision(self, did: str, **fields) -> dict:
        allowed = {"status", "reason"}
        sets = []
        args = []
        for key, value in fields.items():
            if key not in allowed:
                raise Immutable(key)
            sets.append(f"{key} = %s")
            args.append(value)
        args.append(did)
        with self._connect() as conn:
            conn.execute(f"UPDATE {self.schema}.decisions SET {', '.join(sets)} WHERE id = %s", args)
            conn.commit()
        return self.get_decision(did)

    def get_decision(self, did: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(f"SELECT * FROM {self.schema}.decisions WHERE id = %s", (did,)).fetchone()
            links = conn.execute(
                f"SELECT evidence_id FROM {self.schema}.decision_evidence WHERE decision_id = %s ORDER BY position",
                (did,),
            ).fetchall()
        if not row:
            return None
        return {
            "id": row[0],
            "status": row[1],
            "decision_source": row[2],
            "prompt_hash": row[3],
            "input_snapshot_hash": row[4],
            "schema_version": row[5],
            "reason": row[6],
            "idempotency_key": row[7],
            "created_at_utc": _iso(row[8]),
            "evidence_ids": [x[0] for x in links],
        }

    def count_decisions(self) -> int:
        with self._connect() as conn:
            row = conn.execute(f"SELECT COUNT(*) FROM {self.schema}.decisions").fetchone()
        return int(row[0])

    def list_decisions(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT id FROM {self.schema}.decisions ORDER BY created_at_utc DESC LIMIT %s",
                (limit,),
            ).fetchall()
        return [self.get_decision(row[0]) for row in rows]

    def list_decision_headers(self, limit: int = 50) -> list[dict]:
        """One round trip. The list page needs the receipt id, not the evidence join."""
        sql = f"""
        SELECT d.id, d.created_at_utc, d.status, d.reason, d.decision_source,
               (
                 SELECT r.id
                 FROM {self.schema}.receipts r
                 JOIN {self.schema}.ledger_lines l ON l.seq = r.ledger_seq
                 WHERE l.body->>'decision_id' = d.id
                 ORDER BY l.seq DESC
                 LIMIT 1
               ) AS receipt_id
        FROM {self.schema}.decisions d
        ORDER BY d.created_at_utc DESC
        LIMIT %s
        """
        with self._connect() as conn:
            rows = conn.execute(sql, (limit,)).fetchall()
        return [
            {
                "id": row[0],
                "created_at_utc": _iso(row[1]),
                "status": row[2],
                "reason": row[3],
                "decision_source": row[4],
                "model_called": row[4] == "model",
                "receipt_id": row[5],
            }
            for row in rows
        ]

    def count_events(self) -> int:
        with self._connect() as conn:
            row = conn.execute(f"SELECT COUNT(*) FROM {self.schema}.events").fetchone()
        return int(row[0])

    def model_calls_on_day(self, day: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) FROM {self.schema}.decisions WHERE decision_source = 'model' AND created_at_utc::text LIKE %s",
                (day + "%",),
            ).fetchone()
        return int(row[0])

    def insert_fill(self, row: dict) -> dict:
        from psycopg.types.json import Json

        with self._connect() as conn:
            existing = conn.execute(f"SELECT id, decision_id, idempotency_key, status, cost_json, created_at_utc FROM {self.schema}.paper_fills WHERE idempotency_key = %s", (row["idempotency_key"],)).fetchone()
            if existing:
                return _fill_row(existing)
            conn.execute(
                f"""INSERT INTO {self.schema}.paper_fills (id, decision_id, idempotency_key, status, cost_json, created_at_utc)
                VALUES (%s, %s, %s, %s, %s, %s)""",
                (row["id"], row["decision_id"], row["idempotency_key"], row["status"], Json(row["cost_json"]), row["created_at_utc"]),
            )
            _insert_fill_event(conn, self.schema, row["id"], row["status"], Json(row["cost_json"]))
            conn.commit()
        return row

    def list_fills(self) -> list:
        with self._connect() as conn:
            rows = conn.execute(f"SELECT id, decision_id, idempotency_key, status, cost_json, created_at_utc FROM {self.schema}.paper_fills").fetchall()
        return [_fill_row(r) for r in rows]

    def update_fill(self, fill_id: str, **fields) -> dict | None:
        from psycopg.types.json import Json

        with self._connect() as conn:
            row = conn.execute(
                f"UPDATE {self.schema}.paper_fills SET status = %s, cost_json = %s WHERE id = %s RETURNING id, decision_id, idempotency_key, status, cost_json, created_at_utc",
                (fields["status"], Json(fields["cost_json"]), fill_id),
            ).fetchone()
            if row:
                _insert_fill_event(conn, self.schema, fill_id, fields["status"], Json(fields["cost_json"]))
            conn.commit()
        return _fill_row(row) if row else None

    def fill_for_key(self, key: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT id, decision_id, idempotency_key, status, cost_json, created_at_utc FROM {self.schema}.paper_fills WHERE idempotency_key = %s",
                (key,),
            ).fetchone()
        return _fill_row(row) if row else None

    def abandon_unsigned(self, decision_id: str) -> None:
        with self._connect() as conn:
            existing = conn.execute(
                f"SELECT r.id FROM {self.schema}.receipts r JOIN {self.schema}.ledger_lines l ON l.seq = r.ledger_seq WHERE l.body->>'decision_id' = %s",
                (decision_id,),
            ).fetchone()
            if existing:
                return
            conn.execute(f"DELETE FROM {self.schema}.paper_fills WHERE decision_id = %s", (decision_id,))
            conn.execute(f"DELETE FROM {self.schema}.decision_evidence WHERE decision_id = %s", (decision_id,))
            conn.execute(f"DELETE FROM {self.schema}.decisions WHERE id = %s", (decision_id,))
            conn.commit()

    def insert_run(self, row: dict) -> dict:
        from psycopg.types.json import Json

        with self._connect() as conn:
            existing = conn.execute(
                f"SELECT id, idempotency_key, status, reason, decision_id, started_at_utc, finished_at_utc, detail FROM {self.schema}.paper_runs WHERE idempotency_key = %s",
                (row["idempotency_key"],),
            ).fetchone()
            if existing:
                return _run_row(existing)
            conn.execute(
                f"""INSERT INTO {self.schema}.paper_runs
                (id, idempotency_key, status, reason, decision_id, started_at_utc, finished_at_utc, detail)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (row["id"], row["idempotency_key"], row["status"], row["reason"], row["decision_id"], row["started_at_utc"], row["finished_at_utc"], Json(row["detail"])),
            )
            conn.commit()
        return row

    def latest_run(self) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT id, idempotency_key, status, reason, decision_id, started_at_utc, finished_at_utc, detail FROM {self.schema}.paper_runs ORDER BY started_at_utc DESC LIMIT 1"
            ).fetchone()
        return _run_row(row) if row else None

    def dashboard_counts(self) -> dict:
        """Counts and the latest run in one database session."""
        with self._connect() as conn:
            decisions = conn.execute(f"SELECT COUNT(*) FROM {self.schema}.decisions").fetchone()[0]
            events, books, precedents = conn.execute(
                f"""SELECT COUNT(*),
                           COUNT(*) FILTER (WHERE event_type = 'book'),
                           COUNT(*) FILTER (
                             WHERE payload->>'counted' = 'true'
                               AND jsonb_typeof(payload->'reaction_bp') = 'number'
                           )
                    FROM {self.schema}.events"""
            ).fetchone()
            fills = conn.execute(
                f"SELECT COUNT(*) FROM {self.schema}.paper_fills WHERE status IN ('PAPER_FILLED', 'CLOSED')"
            ).fetchone()[0]
            run_row = conn.execute(
                f"SELECT id, idempotency_key, status, reason, decision_id, started_at_utc, finished_at_utc, detail FROM {self.schema}.paper_runs ORDER BY started_at_utc DESC LIMIT 1"
            ).fetchone()
            receipt_id = None
            if run_row and run_row[4]:
                receipt = conn.execute(
                    f"""SELECT r.id FROM {self.schema}.receipts r
                        JOIN {self.schema}.ledger_lines l ON l.seq = r.ledger_seq
                        WHERE l.body->>'decision_id' = %s
                        ORDER BY l.seq DESC LIMIT 1""",
                    (run_row[4],),
                ).fetchone()
                receipt_id = receipt[0] if receipt else None
        run = _run_row(run_row) if run_row else None
        if run is not None:
            run = {**run, "receipt_id": receipt_id}
        return {
            "latest_run": run,
            "fill_count": int(fills),
            "decision_count": int(decisions),
            "event_count": int(events),
            "book_count": int(books),
            "precedent_count": int(precedents),
        }

    def operation_status(self, *, now: datetime | None = None) -> dict:
        """Trailing-hour operation snapshot. One run scan plus one counts read."""
        moment = now or datetime.now(timezone.utc)
        with self._connect() as conn:
            run_rows = conn.execute(
                f"""SELECT idempotency_key, status, reason, started_at_utc, finished_at_utc, detail
                    FROM {self.schema}.paper_runs
                    WHERE started_at_utc >= now() - interval '{OPERATION_LOOKBACK_HOURS} hours'"""
            ).fetchall()
            counted = conn.execute(
                f"""SELECT kind, status, reason, decision_source, idempotency_key, created_at_utc FROM (
                        SELECT 'decision'::text AS kind, status, reason, decision_source, idempotency_key, created_at_utc
                        FROM {self.schema}.decisions
                        WHERE decision_source = 'model'
                          AND created_at_utc >= now() - interval '{OPERATION_LOOKBACK_HOURS} hours'
                        UNION ALL
                        SELECT 'fill'::text, status, NULL::text, NULL::text, idempotency_key, created_at_utc
                        FROM {self.schema}.paper_fills
                        WHERE status IN ('PAPER_FILLED', 'CLOSED')
                          AND created_at_utc >= now() - interval '{OPERATION_LOOKBACK_HOURS} hours'
                    ) counted"""
            ).fetchall()
        runs = [
            {
                "idempotency_key": row[0],
                "status": row[1],
                "reason": row[2],
                "started_at_utc": row[3],
                "finished_at_utc": row[4],
                "detail": row[5],
            }
            for row in run_rows
        ]
        start, end = _window_bounds(runs, moment)
        decisions = []
        fills = 0
        for kind, status, reason, source, key, created in counted:
            if not _fact_in_window(key, created, moment, start, end):
                continue
            if kind == "fill":
                fills += 1
            else:
                decisions.append({"status": status, "reason": reason, "decision_source": source, "idempotency_key": key})
        return build_operation_status(runs, decisions, fills, moment)

    def run_for_key(self, key: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT id, idempotency_key, status, reason, decision_id, started_at_utc, finished_at_utc, detail FROM {self.schema}.paper_runs WHERE idempotency_key = %s",
                (key,),
            ).fetchone()
        return _run_row(row) if row else None

    def append_ledger(self, row: dict) -> dict:
        from psycopg.types.json import Json

        with self._connect() as conn:
            prev = conn.execute(f"SELECT line_hash FROM {self.schema}.ledger_lines ORDER BY seq DESC LIMIT 1").fetchone()
            expected = prev[0] if prev else "GENESIS"
            if row.get("prev_hash") != expected:
                raise Immutable("ledger prev_hash mismatch")
            inserted = conn.execute(
                f"""INSERT INTO {self.schema}.ledger_lines (line_hash, prev_hash, body, signature, pubkey_id)
                VALUES (%s, %s, %s, %s, %s) RETURNING seq""",
                (row["line_hash"], row["prev_hash"], Json(row["body"]), row["signature"], row["pubkey_id"]),
            ).fetchone()
            conn.commit()
        return {**row, "seq": inserted[0]}

    def insert_receipt(self, row: dict) -> dict:
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO {self.schema}.receipts (id, ledger_seq, ots_status) VALUES (%s, %s, %s)",
                (row["id"], row["ledger_seq"], row["ots_status"]),
            )
            conn.commit()
        return row

    def list_ledger(self) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT seq, line_hash, prev_hash, body, signature, pubkey_id FROM {self.schema}.ledger_lines ORDER BY seq"
            ).fetchall()
        return [{"seq": r[0], "line_hash": r[1], "prev_hash": r[2], "body": r[3], "signature": r[4], "pubkey_id": r[5]} for r in rows]

    def last_prev(self) -> str:
        with self._connect() as conn:
            row = conn.execute(f"SELECT line_hash FROM {self.schema}.ledger_lines ORDER BY seq DESC LIMIT 1").fetchone()
        return row[0] if row else "GENESIS"

    def receipt_for_decision(self, decision_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT r.id FROM {self.schema}.receipts r JOIN {self.schema}.ledger_lines l ON l.seq = r.ledger_seq WHERE l.body->>'decision_id' = %s",
                (decision_id,),
            ).fetchone()
        return self.get_receipt(row[0]) if row else None

    def get_receipt(self, rid: str) -> dict | None:
        with self._connect() as conn:
            rec = conn.execute(f"SELECT id, ledger_seq, ots_status FROM {self.schema}.receipts WHERE id = %s", (rid,)).fetchone()
            if not rec:
                return None
            line = conn.execute(
                f"SELECT seq, line_hash, prev_hash, body, signature, pubkey_id FROM {self.schema}.ledger_lines WHERE seq = %s",
                (rec[1],),
            ).fetchone()
        return {
            "id": rec[0],
            "ledger_seq": rec[1],
            "ots_status": rec[2],
            "line": {"seq": line[0], "line_hash": line[1], "prev_hash": line[2], "body": line[3], "signature": line[4], "pubkey_id": line[5]},
        }


def _iso(value) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _event_row(row) -> dict:
    return {
        "id": row[0],
        "instrument_id": row[1],
        "event_type": row[2],
        "event_time_utc": _iso(row[3]),
        "fetched_at_utc": _iso(row[4]),
        "source": row[5],
        "schema_version": row[6],
        "payload": row[7],
        "payload_hash": row[8],
        "mapping_confidence": float(row[9]) if row[9] is not None else None,
        "conflict": row[10],
        "created_at_utc": _iso(row[11]),
    }


def _fill_row(row) -> dict:
    return {"id": row[0], "decision_id": row[1], "idempotency_key": row[2], "status": row[3], "cost_json": row[4], "created_at_utc": _iso(row[5])}


def _run_row(row) -> dict:
    return {
        "id": row[0],
        "idempotency_key": row[1],
        "status": row[2],
        "reason": row[3],
        "decision_id": row[4],
        "started_at_utc": _iso(row[5]),
        "finished_at_utc": _iso(row[6]) if row[6] else None,
        "detail": row[7],
    }


OPERATION_HOURS = 48
OPERATION_LOOKBACK_HOURS = 72
# Cycles before the v2 key used "paper-cycle:<hour>"; both are persisted cycle runs.
_HOUR_KEY = re.compile(r"^paper-cycle:(?:v2:)?(\d{4}-\d{2}-\d{2}T\d{2})(?:$|:)")
# Reasons written before the model is called. filing_document_missing is the cycle's document_not_ready.
_PRE_MODEL_REASONS = frozenset({
    "no_qualifying_event",
    "scheduled_no_new_evidence",
    "source_unavailable",
    "missing_order_book",
    "document_not_ready",
    "filing_document_missing",
})
# Failed check names from governor.check. A refusal stores them joined by comma.
_GOVERNOR_REFUSAL_CHECKS = frozenset({
    "emergency_stop_off",
    "symbol_matches_event",
    "symbol_whitelisted",
    "contract_tradeable",
    "llm_confidence",
    "data_fresh",
    "event_fresh",
    "daily_loss_ok",
    "drawdown_ok",
    "symbol_loss_ok",
    "not_already_positioned",
    "open_positions_ok",
    "precedents_ok",
    "hedge_fit_ok",
    "spread_ok",
    "gross_leverage_ok",
    "depth_ok",
    "horizon_ok",
})
# Model rows that abstain while waiting for the next book are holds, not refusals.
_MODEL_HOLDS = frozenset({"awaiting_next_book"})
_REFUSAL_STATUSES = frozenset({"ABSTAIN", "REJECTED", "RISK_REJECTED"})


def _parse_ts(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _hour_floor(moment: datetime) -> datetime:
    return moment.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def _hour_token(moment: datetime) -> str:
    return _hour_floor(moment).strftime("%Y-%m-%dT%H")


def _hour_from_key(key) -> datetime | None:
    if not isinstance(key, str):
        return None
    match = _HOUR_KEY.match(key)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)


def _as_detail(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _as_number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _started_in_lookback(value, moment: datetime) -> bool:
    started = _parse_ts(value)
    if started is None:
        return False
    return started >= moment - timedelta(hours=OPERATION_LOOKBACK_HOURS)


def _runs_by_hour(runs: list[dict]) -> dict[datetime, dict]:
    chosen: dict[datetime, dict] = {}
    for run in runs:
        hour = _hour_from_key(run.get("idempotency_key"))
        if hour is None:
            continue
        previous = chosen.get(hour)
        if previous is None or (_duration_seconds(previous) is None and _duration_seconds(run) is not None):
            chosen[hour] = run
    return chosen


def _window_bounds(runs: list[dict], moment: datetime) -> tuple[datetime, datetime]:
    current = _hour_floor(moment)
    by_hour = _runs_by_hour(runs)
    end = current if current in by_hour else current - timedelta(hours=1)
    start = end - timedelta(hours=OPERATION_HOURS - 1)
    return start, end


def _fact_in_window(key, created_at, moment: datetime, start: datetime, end: datetime) -> bool:
    created = _parse_ts(created_at)
    if created is None or created < moment - timedelta(hours=OPERATION_LOOKBACK_HOURS):
        return False
    hour = _hour_from_key(key)
    if hour is not None:
        return start <= hour <= end
    created_hour = _hour_floor(created)
    return start <= created_hour <= end


def _duration_seconds(run: dict) -> float | None:
    started = _parse_ts(run.get("started_at_utc"))
    finished = _parse_ts(run.get("finished_at_utc"))
    if started is None or finished is None:
        return None
    return round((finished - started).total_seconds(), 3)


def _model_calls(run: dict) -> float | None:
    return _as_number(_as_detail(run.get("detail")).get("model_calls"))


def _is_pre_model_refusal(run: dict) -> bool:
    reason = run.get("reason")
    if isinstance(reason, str) and reason in _PRE_MODEL_REASONS:
        return True
    return _model_calls(run) == 0 and run.get("status") == "refused"


def _is_governor_refusal(reason) -> bool:
    if not isinstance(reason, str) or not reason.strip():
        return False
    parts = [part.strip() for part in reason.split(",") if part.strip()]
    if not parts:
        return False
    if parts == ["refused"]:
        return True
    return all(part in _GOVERNOR_REFUSAL_CHECKS for part in parts)


def _classify_model_decision(row: dict) -> str | None:
    if row.get("decision_source") != "model":
        return None
    status = str(row.get("status") or "").upper()
    if status not in _REFUSAL_STATUSES:
        return None
    reason = row.get("reason") or ""
    if reason in _MODEL_HOLDS:
        return None
    if _is_governor_refusal(reason):
        return "risk"
    return "other"


def _consecutive_hours(by_hour: dict[datetime, dict], end: datetime, start: datetime) -> int:
    streak = 0
    cursor = end
    while cursor >= start and cursor in by_hour:
        streak += 1
        cursor -= timedelta(hours=1)
    return streak


def build_operation_status(runs: list[dict], decisions: list[dict], paper_fills: int, moment: datetime) -> dict:
    """Hour gaps come from the idempotency key, so a late retry stays on its scheduled hour."""
    by_hour = _runs_by_hour(runs)
    current = _hour_floor(moment)
    end = current if current in by_hour else current - timedelta(hours=1)
    start = end - timedelta(hours=OPERATION_HOURS - 1)
    hours = [start + timedelta(hours=offset) for offset in range(OPERATION_HOURS)]
    first_seen = min(by_hour) if by_hour else None
    tracked = [hour for hour in hours if first_seen is not None and hour >= first_seen]
    recorded = [hour for hour in tracked if hour in by_hour]
    missing = [hour for hour in tracked if hour not in by_hour]
    streak = _consecutive_hours(by_hour, end, start)
    last_completed = current - timedelta(hours=1)
    observed_start = last_completed - timedelta(hours=OPERATION_HOURS - 1)
    observed_streak = _consecutive_hours(by_hour, last_completed, observed_start)
    latest = by_hour[recorded[-1]] if recorded else None
    risk = 0
    other = 0
    for row in decisions:
        kind = _classify_model_decision(row)
        if kind == "risk":
            risk += 1
        elif kind == "other":
            other += 1
    in_window = [by_hour[hour] for hour in recorded]
    return {
        "window_hours": OPERATION_HOURS,
        "expected_hours": len(tracked),
        "before_first_run_hours": OPERATION_HOURS - len(tracked),
        "recorded_hours": len(recorded),
        "missing_hours": [_hour_token(hour) for hour in reversed(missing)][:OPERATION_HOURS],
        "first_recorded_hour": _hour_token(recorded[0]) if recorded else None,
        "last_recorded_hour": _hour_token(recorded[-1]) if recorded else None,
        "consecutive_recorded_hours_ending_now": streak,
        "gap_free_since": _hour_token(end - timedelta(hours=streak - 1)) if streak else None,
        "latest_duration_seconds": _duration_seconds(latest) if latest else None,
        "continuous_operation_observed": observed_streak >= 24,
        "counters": {
            "scheduled_cycles": len(recorded),
            "pre_model_refusals": sum(1 for run in in_window if _is_pre_model_refusal(run)),
            "llm_decisions": sum(1 for run in in_window if (_model_calls(run) or 0) > 0),
            "risk_refusals": risk,
            "other": other,
            "paper_fills": int(paper_fills),
            "fetch_error_runs": sum(
                1 for run in in_window
                if (_as_number(_as_detail(run.get("detail")).get("fetch_errors")) or 0) > 0
            ),
        },
    }
