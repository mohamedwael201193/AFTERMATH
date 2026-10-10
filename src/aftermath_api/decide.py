"""Evidence-grounded decisions. A missing model abstains. It does not switch strategy."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import requests

VENDOR = Path(__file__).resolve().parents[2] / "third_party" / "aftermath"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

from FINAL_CANDIDATE.components.numnorm import Fact, check_text  # noqa: E402

from .config import Settings
from .gate import core_blockers, has_order_book
from .ids import SCHEMA_VERSION, snapshot_hash

PROMPT = (Path(__file__).resolve().parents[2] / "prompts" / "decision_v1.txt").read_text(encoding="utf-8")
PROMPT_HASH = hashlib.sha256(PROMPT.encode()).hexdigest()
PROMPT_V2 = (Path(__file__).resolve().parents[2] / "prompts" / "decision_v2.txt").read_text(encoding="utf-8")
PROMPT_V2_HASH = hashlib.sha256(PROMPT_V2.encode()).hexdigest()
PROPOSAL_FIELDS = (
    "action",
    "symbol",
    "size_frac",
    "confidence",
    "horizon_hours",
    "thesis",
    "invalidation",
    "cited_evidence_ids",
    "text",
)


def abstain(reason: str, rows: list[tuple[str, str]], prompt_hash: str | None = None) -> dict:
    digest = prompt_hash or PROMPT_HASH
    return {
        "status": "ABSTAIN",
        "decision_source": "abstain",
        "reason": reason,
        "prompt_hash": digest,
        "input_snapshot_hash": snapshot_hash(SCHEMA_VERSION, digest, rows),
        "schema_version": SCHEMA_VERSION,
        "proposal": None,
    }


def call_model(settings: Settings, evidence_rows: list[dict], transport=None, prompt: str | None = None) -> str:
    facts = [{"id": r["id"], "payload_hash": r["payload_hash"], "facts": r.get("facts", {})} for r in evidence_rows]
    body = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": prompt or PROMPT},
            {"role": "user", "content": json.dumps({"evidence": facts})},
        ],
    }
    post = transport or requests.post
    last = None
    for _attempt in range(2):
        response = post(
            settings.llm_base_url.rstrip("/") + "/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            timeout=30,
        )
        status = getattr(response, "status_code", 200)
        if status == 401 and _attempt == 0:
            last = response
            continue
        if status >= 400:
            response.raise_for_status()
        last = response
        break
    if last is None or getattr(last, "status_code", 200) >= 400:
        raise RuntimeError("llm request failed")
    return last.json()["choices"][0]["message"]["content"]


def decide(settings: Settings, evidence_rows: list[dict], transport=None) -> dict:
    rows = [(r["id"], r["payload_hash"]) for r in evidence_rows]
    if not evidence_rows:
        return abstain("insufficient_evidence", rows)
    events = [r["event"] for r in evidence_rows if isinstance(r.get("event"), dict)]
    if events:
        blocker = core_blockers(events)
        if blocker:
            return abstain(blocker, rows)
    if not settings.llm_configured:
        return abstain("llm_unconfigured", rows)
    if events and not has_order_book(events):
        return abstain("missing_order_book", rows)
    try:
        text = call_model(settings, evidence_rows, transport)
    except Exception:
        return abstain("llm_unavailable", rows)
    parsed = _parse(text)
    if parsed is None:
        return abstain("malformed_model_output", rows)
    facts = []
    for row in evidence_rows:
        raw = row.get("facts") or {}
        if isinstance(raw, dict):
            for key, value in raw.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    facts.append(Fact(str(key), float(value), "unknown"))
    text = parsed.get("text") or ""
    if text:
        verdict, _details = check_text(text, facts, allow_words=False)
        if verdict != "OK":
            return abstain("unverifiable_number", rows)
    out = abstain("model_no_action", rows)
    out["decision_source"] = "model"
    out["status"] = "NO_ACTION" if parsed.get("action") == "NO_ACTION" else "PAPER_PROPOSED"
    out["proposal"] = parsed
    if out["status"] == "NO_ACTION":
        out["reason"] = "model_no_action"
    return out


def decide_bounded(
    settings: Settings,
    evidence_rows: list[dict],
    *,
    symbol: str,
    transport=None,
    calls_today: int = 0,
    daily_cap: int = 3,
) -> dict:
    """Versioned cycle decision. A failed check refuses. It does not fill."""
    rows = [(r["id"], r["payload_hash"]) for r in evidence_rows]

    def refuse(reason: str, called: bool = False) -> dict:
        refused = abstain(reason, rows, PROMPT_V2_HASH)
        if called:
            refused["model_called"] = True
            refused["decision_source"] = "model"
        return refused

    if calls_today >= daily_cap:
        return refuse("llm_budget_exhausted")
    if not evidence_rows:
        return refuse("insufficient_evidence")
    events = [r["event"] for r in evidence_rows if isinstance(r.get("event"), dict)]
    blocker = core_blockers(events) if events else "insufficient_evidence"
    if blocker:
        return refuse(blocker)
    if not settings.llm_configured:
        return refuse("llm_unconfigured")
    if not has_order_book(events):
        return refuse("missing_order_book")
    try:
        text = call_model(settings, evidence_rows, transport, prompt=PROMPT_V2)
    except Exception:
        return refuse("llm_unavailable", called=True)
    parsed = _parse(text)
    error = _proposal_error(parsed, symbol, [r["id"] for r in evidence_rows])
    if error:
        return refuse(error, called=True)
    facts = []
    for row in evidence_rows:
        raw = row.get("facts") or {}
        if isinstance(raw, dict):
            for key, value in raw.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    facts.append(Fact(str(key), float(value), "unknown"))
    spoken = parsed.get("text") or ""
    if spoken:
        verdict, _details = check_text(spoken, facts, allow_words=False)
        if verdict != "OK":
            return refuse("unverifiable_number", called=True)
    out = abstain("model_no_action", rows, PROMPT_V2_HASH)
    out["model_called"] = True
    out["decision_source"] = "model"
    out["proposal"] = parsed
    if parsed.get("action") == "NO_ACTION":
        out["status"] = "NO_ACTION"
        out["reason"] = "model_no_action"
    else:
        out["status"] = "ABSTAIN"
        out["reason"] = "awaiting_next_book"
    return out


def _proposal_error(proposal: dict | None, symbol: str, evidence_ids: list[str]) -> str | None:
    if not isinstance(proposal, dict) or any(field not in proposal for field in PROPOSAL_FIELDS):
        return "malformed_model_output"
    if proposal.get("action") not in ("LONG", "SHORT", "NO_ACTION"):
        return "malformed_model_output"
    if proposal.get("symbol") != symbol:
        return "symbol_mismatch"
    try:
        size = float(proposal["size_frac"])
        confidence = float(proposal["confidence"])
        horizon = float(proposal["horizon_hours"])
    except (TypeError, ValueError):
        return "malformed_model_output"
    if not all(math.isfinite(value) for value in (size, confidence, horizon)):
        return "malformed_model_output"
    if size < 0 or size > 0.10 or confidence < 0 or confidence > 1 or horizon <= 0:
        return "malformed_model_output"
    cited = proposal.get("cited_evidence_ids")
    if not isinstance(cited, list) or not cited or any(item not in evidence_ids for item in cited):
        return "uncited_claim"
    if not str(proposal.get("thesis") or "").strip() or not str(proposal.get("invalidation") or "").strip():
        return "malformed_model_output"
    return None


def _parse(text: str) -> dict | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or "action" not in data:
        return None
    return data
