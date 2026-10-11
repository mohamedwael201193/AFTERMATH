"""Migration against a disposable schema. Production rows are not read or deleted."""

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _direct_url() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DIRECT_URL="):
            return line.split("=", 1)[1].strip()
    return os.environ.get("DIRECT_URL", "")


@pytest.mark.postgres
def test_append_only_schema_and_restart_read():
    url = _direct_url()
    if not url:
        pytest.skip("DIRECT_URL missing")
    import psycopg

    from aftermath_api.db import apply_migration

    schema = "aftermath_test"
    try:
        conn = psycopg.connect(url, connect_timeout=15)
    except Exception as exc:
        raise AssertionError(f"postgres connection failed: {type(exc).__name__}") from None
    try:
        conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        conn.commit()
        apply_migration(conn, schema)
        conn.execute(
            f"INSERT INTO {schema}.events (id, instrument_id, event_type, event_time_utc, fetched_at_utc, source, schema_version, payload, payload_hash, mapping_confidence, conflict, created_at_utc) "
            "VALUES ('evn_t', 'BTCUSDT', 'ticker', now(), now(), 'bitget-rest', 1, '{\"last\": 1}'::jsonb, 'abc', 1, false, now())"
        )
        conn.commit()
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute(f"UPDATE {schema}.events SET source = 'changed' WHERE id = 'evn_t'")
            conn.commit()
        conn.rollback()
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute(f"DELETE FROM {schema}.events WHERE id = 'evn_t'")
            conn.commit()
        conn.rollback()
        conn.close()
        conn = psycopg.connect(url, connect_timeout=15)
        row = conn.execute(f"SELECT instrument_id FROM {schema}.events WHERE id = 'evn_t'").fetchone()
        assert row[0] == "BTCUSDT"
        from aftermath_api.app import create_app
        from aftermath_api.config import Settings
        from aftermath_api.store import PostgresStore
        from fastapi.testclient import TestClient

        store = PostgresStore(url, schema)
        http = TestClient(create_app(Settings(
            env="test", database_url=url, direct_url=url, llm_api_key="", llm_base_url="", llm_model="",
            llm_configured=False, reader_token="reader-token", decision_token="decision-token", job_token="job-token",
            signing_key_path="", sec_user_agent="", web_origin="", decisions="abstain_only",
        ), store))
        listed = http.get("/v1/events", headers={"Authorization": "Bearer reader-token"})
        assert listed.status_code == 200
        assert any(item["id"] == "evn_t" for item in listed.json()["items"])
        store2 = PostgresStore(url, schema)
        assert store2.get_event("evn_t")["instrument_id"] == "BTCUSDT"
        store2.insert_decision({
            "id": "dec_restart",
            "status": "ABSTAIN",
            "decision_source": "abstain",
            "prompt_hash": "p",
            "input_snapshot_hash": "s",
            "schema_version": 1,
            "reason": "awaiting_next_book",
            "idempotency_key": "restart-fill",
            "created_at_utc": "2026-10-11T04:00:00+00:00",
        }, [])
        marked = {
            "symbol": "NVDAUSDT",
            "mark": {"mid": 101.0, "book_hash": "mark-book", "counted_outcome": False},
        }
        store2.insert_fill({
            "id": "fill_restart",
            "decision_id": "dec_restart",
            "idempotency_key": "restart-fill:entry",
            "status": "PAPER_FILLED",
            "cost_json": marked,
            "created_at_utc": "2026-10-11T04:00:00+00:00",
        })
        repeated = store2.insert_fill({
            "id": "fill_other",
            "decision_id": "dec_restart",
            "idempotency_key": "restart-fill:entry",
            "status": "CLOSED",
            "cost_json": {"outcome_bp": 1},
            "created_at_utc": "2026-10-11T05:00:00+00:00",
        })
        assert repeated["id"] == "fill_restart"
        restarted = PostgresStore(url, schema)
        seen = restarted.fill_for_key("restart-fill:entry")
        assert seen["status"] == "PAPER_FILLED"
        assert seen["cost_json"]["mark"]["mid"] == 101.0
        assert seen["cost_json"]["mark"]["counted_outcome"] is False
        assert "outcome_bp" not in seen["cost_json"]
    finally:
        try:
            conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            conn.commit()
        finally:
            conn.close()
