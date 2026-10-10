"""Evidence-grounded decisions. A missing model abstains. It does not switch strategy."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import requests

VENDOR = Path(__file__).resolve().parents[2] / "third_party" / "aftermath"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

from FINAL_CANDIDATE.components.numnorm import Fact, check_text  # noqa: E402

from .config import Settings
from .ids import SCHEMA_VERSION, snapshot_hash

PROMPT = (Path(__file__).resolve().parents[2] / "prompts" / "decision_v1.txt").read_text(encoding="utf-8")
PROMPT_HASH = hashlib.sha256(PROMPT.encode()).hexdigest()


def abstain(reason: str, rows: list[tuple[str, str]]) -> dict:
    return {
        "status": "ABSTAIN",
        "decision_source": "abstain",
        "reason": reason,
        "prompt_hash": PROMPT_HASH,
        "input_snapshot_hash": snapshot_hash(SCHEMA_VERSION, PROMPT_HASH, rows),
        "schema_version": SCHEMA_VERSION,
        "proposal": None,
    }


def call_model(settings: Settings, evidence_rows: list[dict], transport=None) -> str:
    facts = [{"id": r["id"], "payload_hash": r["payload_hash"], "facts": r.get("facts", {})} for r in evidence_rows]
    body = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": PROMPT},
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
    if not settings.llm_configured:
        return abstain("llm_unconfigured", rows)
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


def _parse(text: str) -> dict | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or "action" not in data:
        return None
    return data
