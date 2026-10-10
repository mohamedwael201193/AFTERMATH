"""Persistence. Prod uses Postgres. Tests may use MemoryStore, which is not a live source."""

from __future__ import annotations

from dataclasses import dataclass, field


class Immutable(Exception):
    pass


@dataclass
class MemoryStore:
    events: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)
    decisions: dict = field(default_factory=dict)
    decision_evidence: list = field(default_factory=list)
    fills: dict = field(default_factory=dict)
    idempotency: dict = field(default_factory=dict)
    ledger: list = field(default_factory=list)
    receipts: dict = field(default_factory=dict)

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

    def get_decision(self, did: str) -> dict | None:
        row = self.decisions.get(did)
        if not row:
            return None
        links = [x for x in self.decision_evidence if x["decision_id"] == did]
        links.sort(key=lambda x: x["position"])
        return {**row, "evidence_ids": [x["evidence_id"] for x in links]}

    def insert_fill(self, row: dict) -> dict:
        key = row["idempotency_key"]
        if key in self.fills:
            return self.fills[key]
        self.fills[key] = dict(row)
        return self.fills[key]

    def list_fills(self) -> list:
        return list(self.fills.values())

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
            conn.commit()
        return row

    def list_fills(self) -> list:
        with self._connect() as conn:
            rows = conn.execute(f"SELECT id, decision_id, idempotency_key, status, cost_json, created_at_utc FROM {self.schema}.paper_fills").fetchall()
        return [_fill_row(r) for r in rows]

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
