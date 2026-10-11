"""Evidence-grounded decisions. A missing model abstains. It does not switch strategy."""

from __future__ import annotations

import hashlib
import json
import math
import re
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
from .model_input import HORIZON_HOURS, SIZE_FRAC, build_decision_input, mapped_symbol

PROMPT = (Path(__file__).resolve().parents[2] / "prompts" / "decision_v1.txt").read_text(encoding="utf-8")
PROMPT_HASH = hashlib.sha256(PROMPT.encode()).hexdigest()
PROMPT_V2 = (Path(__file__).resolve().parents[2] / "prompts" / "decision_v2.txt").read_text(encoding="utf-8")
PROMPT_V2_HASH = hashlib.sha256(PROMPT_V2.encode()).hexdigest()
PROMPT_V3 = (Path(__file__).resolve().parents[2] / "prompts" / "decision_v3.txt").read_text(encoding="utf-8")
PROMPT_V3_HASH = hashlib.sha256(PROMPT_V3.encode()).hexdigest()
PROMPT_V4 = (Path(__file__).resolve().parents[2] / "prompts" / "decision_v4.txt").read_text(encoding="utf-8")
PROMPT_V4_HASH = hashlib.sha256(PROMPT_V4.encode()).hexdigest()
DECISION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "decision_v4",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "action": {"type": "string", "enum": ["LONG", "SHORT", "NO_TRADE"]},
                "confidence": {"type": "number"},
                "thesis": {"type": "string"},
                "invalidation": {"type": "string"},
                "cited_evidence_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["action", "confidence", "thesis", "invalidation", "cited_evidence_ids"],
        },
    },
}
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
    return {
        "status": "ABSTAIN",
        "decision_source": "abstain",
        "reason": reason,
        "prompt_hash": prompt_hash,
        "input_snapshot_hash": snapshot_hash(SCHEMA_VERSION, prompt_hash, rows),
        "schema_version": SCHEMA_VERSION,
        "proposal": None,
    }


MODEL_TIMEOUT_S = 90


def call_model(
    settings: Settings,
    evidence_rows: list[dict],
    transport=None,
    prompt: str | None = None,
    decision_input: dict | None = None,
) -> str:
    facts = []
    for r in evidence_rows:
        row = {"id": r["id"], "payload_hash": r["payload_hash"], "facts": r.get("facts", {})}
        instrument = (r.get("event") or {}).get("instrument_id")
        if isinstance(instrument, str) and instrument:
            row["instrument_id"] = instrument
        facts.append(row)
    user = decision_input if decision_input is not None else {"evidence": facts}
    body = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": prompt or PROMPT},
            {"role": "user", "content": json.dumps(user)},
        ],
    }
    if decision_input is not None:
        body["response_format"] = DECISION_SCHEMA
    post = transport or requests.post
    last = None
    for _attempt in range(2):
        response = post(
            settings.llm_base_url.rstrip("/") + "/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            timeout=MODEL_TIMEOUT_S,
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
    out = abstain("model_no_action", rows, PROMPT_HASH)
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
    market: dict | None = None,
    now=None,
) -> dict:
    """Versioned cycle decision. A failed check refuses. It does not fill."""
    from datetime import datetime, timezone

    rows = [(r["id"], r["payload_hash"]) for r in evidence_rows]
    moment = now or datetime.now(timezone.utc)

    def refuse(reason: str, called: bool = False) -> dict:
        refused = abstain(reason, rows, PROMPT_V4_HASH if called else None)
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
    if mapped_symbol(symbol) is None:
        return refuse("unmapped_symbol")
    if not settings.llm_configured:
        return refuse("llm_unconfigured")
    if not has_order_book(events):
        return refuse("missing_order_book")
    decision_input = build_decision_input(evidence_rows, symbol, market, moment)
    try:
        text = call_model(settings, evidence_rows, transport, prompt=PROMPT_V4, decision_input=decision_input)
    except Exception:
        return refuse("llm_unavailable", called=True)
    parsed = _parse(text)
    if isinstance(parsed, dict):
        if parsed.get("action") == "NO_TRADE":
            parsed["action"] = "NO_ACTION"
        parsed["symbol"] = symbol
        parsed["size_frac"] = SIZE_FRAC
        parsed["horizon_hours"] = HORIZON_HOURS
        parsed.setdefault("text", "")
    error = _proposal_error(parsed, symbol, [r["id"] for r in evidence_rows])
    if error:
        refused = refuse(error, called=True)
        refused["decision_input"] = decision_input
        return refused
    facts = _input_facts(decision_input)
    for row in evidence_rows:
        raw = row.get("facts") or {}
        if isinstance(raw, dict):
            for key, value in raw.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    facts.append(Fact(str(key), float(value), "unknown"))
    facts.extend(SERVER_FIXED_FACTS)
    spoken = "\n".join(
        part for part in (parsed.get("thesis"), parsed.get("invalidation"), parsed.get("text")) if isinstance(part, str) and part
    )
    if spoken:
        verdict, details = check_text(_mask_names(spoken), facts, allow_words=False)
        if verdict != "OK":
            refused = refuse("unverifiable_number", called=True)
            refused["unbound_numbers"] = [str(token)[:32] for token in (details or {}).get("tokens", [])][:10]
            refused["decision_input"] = decision_input
            return refused
    out = abstain("model_no_action", rows, PROMPT_V4_HASH)
    out["model_called"] = True
    out["decision_source"] = "model"
    out["proposal"] = parsed
    out["decision_input"] = decision_input
    if parsed.get("action") == "NO_ACTION":
        out["status"] = "NO_ACTION"
        out["reason"] = "model_no_action"
    else:
        out["status"] = "ABSTAIN"
        out["reason"] = "awaiting_next_book"
    return out


SERVER_FIXED_FACTS = (
    Fact("server.size_frac", 0.05, "unknown"),
    Fact("server.horizon_hours", 24.0, "unknown"),
)
INDEX_NAMES = re.compile(r"\bNasdaq[- ]100\b", re.IGNORECASE)


def _mask_names(text: str) -> str:
    """The prompt names its reference index. A digit inside that name is not a claim."""
    return INDEX_NAMES.sub("Nasdaq reference", text)


def _input_facts(decision_input: dict) -> list:
    found = []

    def walk(value, name: str) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            if isinstance(value, dict):
                for key, item in value.items():
                    walk(item, f"{name}.{key}")
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    walk(item, f"{name}[{index}]")
            return
        if math.isfinite(float(value)):
            found.append(Fact(name, float(value), "unknown"))

    walk(decision_input, "input")
    return found


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
    thesis = str(proposal.get("thesis") or "")
    invalidation = str(proposal.get("invalidation") or "")
    if not thesis.strip() or not invalidation.strip():
        return "malformed_model_output"
    if len(thesis) > 400 or len(invalidation) > 200:
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
