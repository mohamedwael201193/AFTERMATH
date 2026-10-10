"""SEC EDGAR submissions reader. It does not run without a configured user agent."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from ..connectors import require_sec_user_agent

MAX_EVENT_AGE = timedelta(minutes=360)
EXCERPT_LIMIT = 480
COUNTED_ITEMS = {"2.02"}
SHADOW_ITEMS = {"7.01", "8.01"}

# Public SEC company_tickers CIKs for the whitelist. Zero-padded to 10 digits.
CIK_TO_SYMBOL = {
    "0001045810": "NVDAUSDT",
    "0001318605": "TSLAUSDT",
    "0000320193": "AAPLUSDT",
    "0001018724": "AMZNUSDT",
    "0000789019": "MSFTUSDT",
    "0001326801": "METAUSDT",
    "0001652044": "GOOGLUSDT",
    "0001679788": "COINUSDT",
    "0001050446": "MSTRUSDT",
}
QUALIFYING_FORMS = {"8-K"}
QUALIFYING_ITEMS = {"2.02", "7.01", "8.01"}


def fetch_filings(user_agent: str, transport, fetched_at: str, now: datetime | None = None) -> list[dict]:
    require_sec_user_agent(user_agent)
    found: list[dict] = []
    seen: set[str] = set()
    for cik, symbol in CIK_TO_SYMBOL.items():
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        response = transport(url, {"User-Agent": user_agent, "Accept": "application/json"})
        payload = response if isinstance(response, dict) else json.loads(response)
        found.extend(select_filings(symbol, payload, fetched_at, now=now, seen=seen))
    attached = []
    for row in found:
        if not (row.get("payload") or {}).get("counted"):
            attached.append(row)
            continue
        url = (row.get("payload") or {}).get("source_url")
        try:
            body = transport(url, {"User-Agent": user_agent, "Accept": "text/html"}) if url else None
        except Exception:
            attached.append(row)
            continue
        attached.append(attach_document(row, body) if isinstance(body, str) else row)
    attached.sort(key=lambda row: row["event_time_utc"])
    return attached


def attach_document(filing: dict, body: str) -> dict:
    """Bind a fetched filing body. The excerpt is evidence, not an instruction."""
    if not isinstance(body, str) or not body.strip():
        return filing
    payload = dict(filing.get("payload") or {})
    payload["document_sha256"] = hashlib.sha256(body.encode()).hexdigest()
    payload["excerpt"] = body[:EXCERPT_LIMIT]
    payload["excerpt_untrusted"] = True
    return {**filing, "payload": payload}


def filing_from_submissions(symbol: str, payload: dict, fetched_at: str, now: datetime | None = None) -> dict | None:
    counted = [row for row in select_filings(symbol, payload, fetched_at, now=now) if row["payload"].get("counted")]
    return counted[0] if counted else None


def select_filings(
    symbol: str,
    payload: dict,
    fetched_at: str,
    now: datetime | None = None,
    seen: set[str] | None = None,
) -> list[dict]:
    now = now or _parse(fetched_at) or datetime.now(timezone.utc)
    recent = ((payload or {}).get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    items = recent.get("items") or []
    accessions = recent.get("accessionNumber") or []
    documents = recent.get("primaryDocument") or []
    accepted = recent.get("acceptanceDateTime") or []
    index_times = recent.get("indexAcceptanceDateTime") or []
    cik = str((payload or {}).get("cik") or "").zfill(10)
    chosen: list[dict] = []
    seen = seen if seen is not None else set()
    for index, form in enumerate(forms):
        if form not in QUALIFYING_FORMS:
            continue
        item = str(items[index] if index < len(items) else "")
        kind = _item_kind(item)
        if kind is None:
            continue
        accession = accessions[index] if index < len(accessions) else ""
        if not accession or accession in seen:
            continue
        event_time = _accepted_at(accepted, index_times, index)
        if event_time is None:
            continue
        if now - event_time > MAX_EVENT_AGE or event_time > now + timedelta(minutes=5):
            continue
        document = documents[index] if index < len(documents) else ""
        source_url = _archive_url(cik, accession, document)
        body = {
            "form": form,
            "items": item,
            "accession": accession,
            "source_url": source_url,
            "qualifies": kind == "counted",
            "counted": kind == "counted",
            "shadow": kind == "shadow",
        }
        seen.add(accession)
        chosen.append({
            "source": "sec-edgar",
            "instrument_id": symbol,
            "event_type": "filing",
            "event_time_utc": event_time.isoformat(),
            "fetched_at_utc": fetched_at,
            "payload": {**body, "content_sha256": hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()},
            "mapping_confidence": 1.0,
        })
    chosen.sort(key=lambda row: row["event_time_utc"])
    return chosen


def _item_kind(item: str) -> str | None:
    if any(code in item for code in COUNTED_ITEMS):
        return "counted"
    if any(code in item for code in SHADOW_ITEMS):
        return "shadow"
    return None


def _accepted_at(accepted: list, index_times: list, index: int) -> datetime | None:
    primary = _parse(accepted[index] if index < len(accepted) else None)
    index_time = _parse(index_times[index] if index < len(index_times) else None)
    if primary and index_time and abs(primary - index_time) > timedelta(hours=24):
        return None
    if index_time:
        return index_time
    return primary


def _parse(value) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _archive_url(cik: str, accession: str, document: str) -> str:
    bare = accession.replace("-", "")
    number = str(int(cik)) if cik.strip("0") else "0"
    name = document or f"{accession}.txt"
    return f"https://www.sec.gov/Archives/edgar/data/{number}/{bare}/{name}"
