"""Decision v4 input. The instrument is the server symbol, and only closed bars enter the residual."""

import json
import time
from datetime import datetime, timezone

from aftermath_api.config import Settings
from aftermath_api.decide import DECISION_SCHEMA, decide_bounded
from aftermath_api.model_input import build_decision_input


def _settings():
    return Settings(
        env="test", database_url="", direct_url="", llm_api_key="k", llm_base_url="https://example.test/v1",
        llm_model="m", llm_configured=True, reader_token="r", decision_token="d", job_token="j",
        signing_key_path="", sec_user_agent="", web_origin="", decisions="model",
    )


def _rows():
    now = datetime.now(timezone.utc).isoformat()
    return [
        {
            "id": "ev_filing",
            "payload_hash": "a" * 64,
            "facts": {"items": "2.02"},
            "event": {
                "source": "sec-edgar",
                "instrument_id": "NVDAUSDT",
                "event_type": "filing",
                "event_time_utc": "2026-08-26T20:21:19+00:00",
                "fetched_at_utc": now,
                "payload_hash": "a" * 64,
                "payload": {
                    "accession": "0001045810-26-000073",
                    "items": "2.02",
                    "clock_source": "sec_index_header",
                    "exhibit_excerpt": "Total revenue for the quarter was 46.7.",
                    "excerpt_untrusted": True,
                },
            },
        },
        {
            "id": "ev_book",
            "payload_hash": "b" * 64,
            "facts": {"bid": 100.0, "ask": 100.02},
            "event": {
                "source": "bitget-rest",
                "instrument_id": "NVDAUSDT",
                "event_type": "book",
                "event_time_utc": now,
                "fetched_at_utc": now,
                "payload_hash": "b" * 64,
                "payload": {"bid": 100.0, "ask": 100.02, "spread_bp": 2.0, "bids": [[100.0, 5]], "asks": [[100.02, 5]]},
            },
        },
    ]


def _body(**overrides):
    body = {
        "action": "LONG",
        "symbol": "NVDA",
        "confidence": 0.8,
        "thesis": "The exhibit supports a paper long.",
        "invalidation": "A later filing replaces this residual.",
        "cited_evidence_ids": ["ev_filing"],
    }
    body.update(overrides)
    return body


def _transport(body, seen):
    class Ok:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(body)}}]}

    def transport(_url, json=None, headers=None, timeout=None):
        seen.append(json)
        return Ok()

    return transport


def test_symbol_from_mapper_not_model():
    seen = []
    out = decide_bounded(
        _settings(), _rows(), symbol="NVDAUSDT", transport=_transport(_body(), seen),
        now=datetime(2026, 8, 26, 21, 0, tzinfo=timezone.utc),
    )
    assert out["reason"] == "awaiting_next_book"
    assert out["proposal"]["symbol"] == "NVDAUSDT"
    assert out["proposal"]["size_frac"] == 0.05
    assert out["proposal"]["horizon_hours"] == 24
    assert out["prompt_hash"]


def test_strict_schema_sent():
    seen = []
    decide_bounded(
        _settings(), _rows(), symbol="NVDAUSDT", transport=_transport(_body(action="NO_TRADE"), seen),
        now=datetime(2026, 8, 26, 21, 0, tzinfo=timezone.utc),
    )
    assert seen[0]["response_format"] == DECISION_SCHEMA
    sent = json.loads(seen[0]["messages"][1]["content"])
    assert sent["version"] == "decision_v4"
    assert sent["instrument"]["symbol"] == "NVDAUSDT"
    assert sent["event"]["exhibit_excerpt"].startswith("Total revenue")
    assert "NVDA" not in seen[0]["messages"][0]["content"]


def test_cited_ids_allowlist():
    out = decide_bounded(
        _settings(), _rows(), symbol="NVDAUSDT",
        transport=_transport(_body(cited_evidence_ids=["ev_other"]), []),
        now=datetime(2026, 8, 26, 21, 0, tzinfo=timezone.utc),
    )
    assert out["reason"] == "uncited_claim"
    assert out["model_called"] is True


def test_thesis_number_is_checked():
    out = decide_bounded(
        _settings(), _rows(), symbol="NVDAUSDT",
        transport=_transport(_body(thesis="Revenue rose 3.1 percent."), []),
        now=datetime(2026, 8, 26, 21, 0, tzinfo=timezone.utc),
    )
    assert out["reason"] == "unverifiable_number"
    assert out["unbound_numbers"]


def test_pre_model_refusal_has_no_prompt_hash():
    out = decide_bounded(_settings(), _rows(), symbol="NVDAUSDT", calls_today=3, daily_cap=3)
    assert out["reason"] == "llm_budget_exhausted"
    assert out["prompt_hash"] is None
    assert out.get("model_called") is not True


def test_residual_uses_only_closed_bars():
    accepted = datetime(2026, 8, 26, 20, 21, 19, tzinfo=timezone.utc)
    decision = datetime(2026, 8, 26, 22, 30, tzinfo=timezone.utc)
    hour = 3_600_000
    base = int(datetime(2026, 8, 26, 19, 0, tzinfo=timezone.utc).timestamp() * 1000)
    symbol = [[base, 100.0], [base + hour, 100.0], [base + 2 * hour, 110.0], [base + 3 * hour, 999.0]]
    reference = [[base, 400.0], [base + hour, 400.0], [base + 2 * hour, 400.0], [base + 3 * hour, 400.0]]
    # Pad earlier hours so the hedge fit has a sample. The 22:00 bar closes at 23:00, after the decision.
    for index in range(30):
        opened = base - (index + 1) * hour
        symbol.append([opened, 100.0])
        reference.append([opened, 400.0])
    market = {"symbol_bars": symbol, "reference_bars": reference, "contract": {"status": "normal", "taker_fee_rate": 0.0006}}
    built = build_decision_input(
        [{
            "id": "ev_filing",
            "payload_hash": "a",
            "event": {
                "instrument_id": "NVDAUSDT",
                "event_type": "filing",
                "event_time_utc": accepted.isoformat(),
                "payload": {"accession": "0001045810-26-000073"},
            },
        }],
        "NVDAUSDT",
        market,
        decision,
    )
    assert built["residual"]["residual_bp"] == 1000
    assert built["instrument"]["symbol"] == "NVDAUSDT"
    early = build_decision_input(
        [{
            "id": "ev_filing",
            "payload_hash": "a",
            "event": {
                "instrument_id": "NVDAUSDT",
                "event_type": "filing",
                "event_time_utc": accepted.isoformat(),
                "payload": {},
            },
        }],
        "NVDAUSDT",
        market,
        datetime(2026, 8, 26, 21, 0, tzinfo=timezone.utc),
    )
    assert early["residual"]["residual_bp"] is None


def test_deadline_bounds_hung_read(monkeypatch):
    monkeypatch.setenv("AFTERMATH_LLM_DEADLINE_S", "1")
    calls = {"n": 0}

    def transport(_url, json=None, headers=None, timeout=None):
        calls["n"] += 1
        time.sleep(400)

    started = time.monotonic()
    out = decide_bounded(_settings(), _rows(), symbol="NVDAUSDT", transport=transport)
    assert time.monotonic() - started < 3
    assert calls["n"] == 1
    assert out["reason"] == "llm_timeout"
    assert out["status"] == "NO_ACTION"
    assert out["proposal"]["action"] == "NO_ACTION"
    assert out["model_called"] is True
    assert out["latency_ms"] < 3000


def test_timeout_is_counted_and_not_retried(monkeypatch):
    monkeypatch.setenv("AFTERMATH_LLM_DEADLINE_S", "1")
    calls = {"n": 0}

    def transport(_url, json=None, headers=None, timeout=None):
        calls["n"] += 1
        raise RuntimeError("proxy down")

    out = decide_bounded(_settings(), _rows(), symbol="NVDAUSDT", transport=transport)
    assert calls["n"] == 1
    assert out["reason"] == "llm_unavailable"
    assert out["status"] == "NO_ACTION"
    assert out["model_called"] is True
    blocked = decide_bounded(
        _settings(), _rows(), symbol="NVDAUSDT", transport=transport, calls_today=1, daily_cap=1,
    )
    assert blocked["reason"] == "llm_budget_exhausted"
    assert blocked.get("model_called") is not True
