import importlib.util
from pathlib import Path


def _twin():
    path = Path(__file__).resolve().parents[1] / "playbook_twin" / "strategy.py"
    spec = importlib.util.spec_from_file_location("sa_twin", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_studio_twin_keeps_its_own_label_and_fixed_size():
    twin = _twin()
    decision = twin.decide({"symbol": "NVDAUSDT", "residual_bp": 12})
    assert decision["action"] == "LONG"
    assert decision["size_frac"] == 0.05
    assert decision["horizon_hours"] == 24
    assert decision["merge_into_aftermath_metrics"] is False
    assert "no direct EDGAR" in decision["label"]
    assert twin.decide({"symbol": "BTCUSDT", "residual_bp": 12})["action"] == "NO_ACTION"
    assert twin.decide({"symbol": "NVDAUSDT"})["action"] == "NO_ACTION"
