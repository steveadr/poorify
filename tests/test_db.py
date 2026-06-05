import tempfile
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from poorify import db


@pytest.fixture(autouse=True)
def _patch_db_path(monkeypatch, tmp_path):
    test_db = tmp_path / "test_harness.db"
    monkeypatch.setattr(db, "DB_PATH", str(test_db))
    monkeypatch.setattr(db, "HARNESS_DIR", str(tmp_path))
    db.init_db()


def test_init_db():
    assert os.path.exists(db.DB_PATH)


def test_log_execution():
    rid = db.log_execution("test.py", "test_action", "ok", "SUCCESS")
    assert rid is not None


def test_get_recent_logs():
    db.log_execution("a.py", "fix", "done", "SUCCESS")
    logs = db.get_recent_logs()
    assert len(logs) >= 1


def test_save_and_get_technical_spec():
    db.save_technical_spec("/project", "target.py", "pre", "post", "const")
    spec = db.get_technical_spec("target.py")
    assert spec is not None
    assert spec["pre_conditions"] == "pre"
    assert spec["post_conditions"] == "post"


def test_router_entry():
    db.set_router_entry("file.py", 3, "SKELETON")
    entry = db.get_router_entry("file.py")
    assert entry is not None
    assert entry["ingestion_mode"] == "SKELETON"
    assert entry["cyclomatic_complexity"] == 3


def test_save_and_get_assertions():
    db.save_assertion("TEST_001", "target.py", '{"a":1}', '{"b":2}')
    rows = db.get_assertions_for_file("target.py")
    assert len(rows) == 1
    assert rows[0]["rule_key"] == "TEST_001"


def test_cascade_tasks():
    tid = db.add_cascade_task(1, "broken.py", "compile error")
    assert tid is not None
    tasks = db.get_pending_cascade_tasks()
    assert len(tasks) == 1
    db.mark_cascade_fixed(tid)
    tasks = db.get_pending_cascade_tasks()
    assert len(tasks) == 0


def test_inspect_module_empty(monkeypatch, tmp_path):
    test_db = tmp_path / "test_harness.db"
    monkeypatch.setattr(db, "DB_PATH", str(test_db))
    monkeypatch.setattr(db, "HARNESS_DIR", str(tmp_path))
    db.init_db()
    result = db.inspect_module("Trading")
    assert result["specs"] == []
    assert result["router"] == []
    assert result["assertions"] == []
    assert result["metrics"] == []
    assert result["cascade"] == []
    assert result["logs"] == []


def test_inspect_module_finds_data(monkeypatch, tmp_path):
    test_db = tmp_path / "test_harness.db"
    monkeypatch.setattr(db, "DB_PATH", str(test_db))
    monkeypatch.setattr(db, "HARNESS_DIR", str(tmp_path))
    db.init_db()
    db.save_technical_spec("/project", "src/trading/main.rs", "pre", "post", "")
    db.save_assertion("TRADE_001", "src/trading/calc.rs", "{}", "{}")
    db.set_router_entry("src/trading/main.rs", 8, "FULL")
    db.log_token_metric("P1", "dev", "src/trading/main.rs", input_tokens=100)
    db.log_execution("src/trading/main.rs", "patch", "ok", "SUCCESS")

    result = db.inspect_module("trading")
    assert len(result["specs"]) == 1
    assert result["specs"][0]["target_file"] == "src/trading/main.rs"
    assert len(result["assertions"]) == 1
    assert len(result["router"]) == 1
    assert result["router"][0]["cyclomatic_complexity"] == 8
    assert len(result["metrics"]) == 1
    assert len(result["logs"]) == 1
