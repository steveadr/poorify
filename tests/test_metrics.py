import os
import sys
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from poorify import db, metrics


@pytest.fixture(autouse=True)
def _patch_db(monkeypatch, tmp_path):
    test_db = tmp_path / "test_harness.db"
    monkeypatch.setattr(db, "DB_PATH", str(test_db))
    monkeypatch.setattr(db, "HARNESS_DIR", str(tmp_path))
    db.init_db()


def test_new_pipeline_id():
    pid = metrics.new_pipeline_id()
    assert pid.startswith("P")
    assert len(pid) > 15


def test_log_token_metric():
    db.log_token_metric("PIPEX", "test", "f.py",
                        input_tokens=100, output_tokens=50,
                        cached_tokens=20, context_window_size=3000,
                        context_window_max=8000,
                        retry_attempt=1, skeleton_savings=500,
                        duration_ms=200)
    rows = db.get_metrics_for_pipeline("PIPEX")
    assert len(rows) == 1
    assert rows[0]["input_tokens"] == 100
    assert rows[0]["output_tokens"] == 50
    assert rows[0]["cached_tokens"] == 20


def test_multiple_metrics_same_pipeline():
    db.log_token_metric("PIPE2", "req", "a.py", input_tokens=50)
    db.log_token_metric("PIPE2", "dev", "a.py", input_tokens=200, output_tokens=80)
    rows = db.get_metrics_for_pipeline("PIPE2")
    assert len(rows) == 2


def test_get_all_pipeline_ids():
    db.log_token_metric("P_A", "req", "f.py")
    db.log_token_metric("P_B", "req", "f.py")
    pids = db.get_all_pipeline_ids()
    ids = [r["pipeline_id"] for r in pids]
    assert "P_A" in ids
    assert "P_B" in ids


def test_get_aggregate_metrics():
    db.log_token_metric("P1", "req", "f.py", input_tokens=100, output_tokens=50, duration_ms=100)
    db.log_token_metric("P2", "req", "f.py", input_tokens=200, output_tokens=100, duration_ms=200)
    db.log_token_metric("P1", "dev", "f.py", input_tokens=400, output_tokens=150, duration_ms=300)
    agg = db.get_aggregate_metrics()
    assert len(agg) == 2
    req = [r for r in agg if r["phase"] == "req"][0]
    assert req["runs"] == 2
    assert req["avg_input"] == 150.0


def test_meter_context():
    with metrics.MeterContext("P_METER", "test_phase", "target.py") as m:
        m.input_tokens = 42
        m.output_tokens = 10
    rows = db.get_metrics_for_pipeline("P_METER")
    assert len(rows) == 1
    assert rows[0]["input_tokens"] == 42
    assert rows[0]["output_tokens"] == 10
    assert rows[0]["duration_ms"] >= 0


def test_summary_returns_string():
    db.log_token_metric("P_SUM", "req", "f.py", input_tokens=50)
    s = metrics.summary("P_SUM")
    assert isinstance(s, str)
    assert "P_SUM" in s


def test_summary_empty():
    s = metrics.summary("NONEXIST")
    assert "No metrics" in s


def test_overall_stats_empty():
    s = metrics.overall_stats()
    assert "No metrics" in s


def test_overall_stats():
    db.log_token_metric("P", "req", "f.py", input_tokens=100, output_tokens=30, duration_ms=50)
    db.log_token_metric("P", "dev", "f.py", input_tokens=300, output_tokens=120, duration_ms=400)
    s = metrics.overall_stats()
    assert "req" in s
    assert "dev" in s
