"""SEC EDGAR submissions reader. It does not run without a configured user agent."""

from __future__ import annotations

import hashlib
import json

from ..connectors import require_sec_user_agent

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


def fetch_filings(user_agent: str, transport, fetched_at: str) -> list[dict]:
    require_sec_user_agent(user_agent)
    found: list[dict] = []
    for cik, symbol in CIK_TO_SYMBOL.items():
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        response = transport(url, {"User-Agent": user_agent, "Accept": "application/json"})
        payload = response if isinstance(response, dict) else json.loads(response)
        filing = filing_from_submissions(symbol, payload, fetched_at)
        if filing:
            found.append(filing)
    return found


def filing_from_submissions(symbol: str, payload: dict, fetched_at: str) -> dict | None:
    recent = ((payload or {}).get("filings") or {}).get("recent") or {}
    forms = recent.get("form") or []
    items = recent.get("items") or []
    dates = recent.get("filingDate") or []
    accessions = recent.get("accessionNumber") or []
    documents = recent.get("primaryDocument") or []
    cik = str((payload or {}).get("cik") or "").zfill(10)
    for index, form in enumerate(forms):
        if form not in QUALIFYING_FORMS:
            continue
        item = str(items[index] if index < len(items) else "")
        if not any(code in item for code in QUALIFYING_ITEMS):
            continue
        accession = accessions[index] if index < len(accessions) else ""
        document = documents[index] if index < len(documents) else ""
        filed = dates[index] if index < len(dates) else ""
        if not accession or not filed:
            continue
        source_url = _archive_url(cik, accession, document)
        body = {
            "form": form,
            "items": item,
            "accession": accession,
            "source_url": source_url,
            "qualifies": True,
        }
        return {
            "source": "sec-edgar",
            "instrument_id": symbol,
            "event_type": "filing",
            "event_time_utc": f"{filed}T00:00:00+00:00",
            "fetched_at_utc": fetched_at,
            "payload": {**body, "content_sha256": hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()},
            "mapping_confidence": 1.0,
        }
    return None


def _archive_url(cik: str, accession: str, document: str) -> str:
    bare = accession.replace("-", "")
    number = str(int(cik)) if cik.strip("0") else "0"
    name = document or f"{accession}.txt"
    return f"https://www.sec.gov/Archives/edgar/data/{number}/{bare}/{name}"
