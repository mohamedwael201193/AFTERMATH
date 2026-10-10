import json

from aftermath_api.app import create_app
from aftermath_api.config import Settings
from aftermath_api.store import MemoryStore


def _app():
    return create_app(Settings(
        env="test", database_url="", direct_url="", llm_api_key="", llm_base_url="", llm_model="",
        llm_configured=False, reader_token="r", decision_token="d", job_token="j", signing_key_path="",
        sec_user_agent="", web_origin="https://app.example", decisions="abstain_only",
    ), MemoryStore())


def test_openapi_export_is_stable(tmp_path):
    first = json.dumps(_app().openapi(), sort_keys=True, separators=(",", ":"))
    second = json.dumps(_app().openapi(), sort_keys=True, separators=(",", ":"))
    assert first == second
    spec = json.loads(first)
    paths = spec["paths"]
    for path in ("/health", "/ready", "/v1/events", "/v1/decisions", "/internal/jobs/paper-cycle", "/v1/receipts/{receipt_id}/verify"):
        assert path in paths
    assert paths["/health"]["get"]["responses"]["200"]
    (tmp_path / "openapi.json").write_text(first, encoding="utf-8")
