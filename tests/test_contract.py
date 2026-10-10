import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_decision_example_matches_contract():
    example = json.loads((ROOT / "contracts" / "examples" / "decision.json").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "contracts" / "decision.schema.json").read_text(encoding="utf-8"))
    assert example["fixture"] is True
    assert "evidence_id" not in example
    for key in schema["required"]:
        assert key in example
    assert example["status"] in schema["properties"]["status"]["enum"]
    assert example["source"]
    assert example["created_at_utc"].endswith("+00:00")
