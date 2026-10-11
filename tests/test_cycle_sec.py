"""Exhibit 99.1 is the earnings text. A failed fetch stays pending and can be retried."""

import hashlib
from datetime import datetime, timezone

from aftermath_api.cycle import _already_seen
from aftermath_api.sources.edgar import fetch_filings
from aftermath_api.store import MemoryStore


def _submissions(now: datetime):
    return {
        "cik": "1045810",
        "filings": {"recent": {
            "form": ["8-K"],
            "items": ["2.02"],
            "acceptanceDateTime": [now.isoformat().replace("+00:00", "Z")],
            "accessionNumber": ["0001045810-26-000073"],
            "primaryDocument": ["nvda-8k.htm"],
        }},
    }


def _header(now: datetime) -> str:
    from zoneinfo import ZoneInfo

    local = now.astimezone(ZoneInfo("America/New_York"))
    return f"<ACCEPTANCE-DATETIME>{local.strftime('%Y%m%d%H%M%S')}"


INDEX = '<tr><td>EX-99.1</td><td><a href="/Archives/edgar/data/1045810/000104581026000073/ex991.htm">ex991.htm</a></td></tr>'
EXHIBIT = "<html><body><p>Total revenue for the quarter was $46.7 billion.</p></body></html>"
PRIMARY = "<?xml version=\"1.0\"?><xbrl>cover page only</xbrl>"


def _transport(now, exhibit):
    payload = _submissions(now)

    def transport(url, _headers):
        text = str(url)
        if text.endswith(".json"):
            return payload
        if "index-headers" in text:
            return _header(now)
        if text.endswith("-index.htm"):
            return INDEX
        if text.endswith("ex991.htm"):
            if isinstance(exhibit, Exception):
                raise exhibit
            return exhibit
        return PRIMARY

    return transport


def test_exhibit_991_extracted_and_hashed():
    now = datetime(2026, 8, 26, 20, 30, tzinfo=timezone.utc)
    rows = fetch_filings("Research Desk research@example.com", _transport(now, EXHIBIT), now.isoformat(), now=now)
    counted = [row for row in rows if row["payload"].get("counted")]
    assert len(counted) == 1
    payload = counted[0]["payload"]
    assert payload["exhibit_url"].endswith("/ex991.htm")
    assert payload["exhibit_sha256"] == hashlib.sha256(EXHIBIT.encode()).hexdigest()
    assert "Total revenue" in payload["exhibit_excerpt"]
    assert "<?xml" not in payload["exhibit_excerpt"]
    assert "<?xml" not in payload["excerpt"]
    assert payload["document_sha256"] == hashlib.sha256(PRIMARY.encode()).hexdigest()
    assert payload.get("status") != "document_pending"


def test_transient_document_failure_retries():
    now = datetime(2026, 8, 26, 20, 30, tzinfo=timezone.utc)
    failed = fetch_filings(
        "Research Desk research@example.com",
        _transport(now, RuntimeError("sec timeout")),
        now.isoformat(),
        now=now,
    )
    assert failed[0]["payload"]["status"] == "document_pending"
    assert "excerpt" not in failed[0]["payload"]
    store = MemoryStore()
    store.insert_event({
        "id": "ev_pending",
        "source": failed[0]["source"],
        "instrument_id": "NVDAUSDT",
        "event_type": "filing",
        "event_time_utc": failed[0]["event_time_utc"],
        "payload": failed[0]["payload"],
    })
    assert _already_seen(store, failed[0]) is False
    recovered = fetch_filings(
        "Research Desk research@example.com",
        _transport(now, EXHIBIT),
        now.isoformat(),
        now=now,
    )
    assert "Total revenue" in recovered[0]["payload"]["excerpt"]
    assert recovered[0]["payload"]["exhibit_sha256"]
    store.insert_event({
        "id": "ev_ready",
        "source": recovered[0]["source"],
        "instrument_id": "NVDAUSDT",
        "event_type": "filing",
        "event_time_utc": recovered[0]["event_time_utc"],
        "payload": recovered[0]["payload"],
    })
    assert _already_seen(store, recovered[0]) is True
