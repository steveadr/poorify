import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from poorify import engine, db, utils


@pytest.fixture(autouse=True)
def _patch_db(monkeypatch, tmp_path):
    test_db = tmp_path / "test_harness.db"
    monkeypatch.setattr(db, "DB_PATH", str(test_db))
    monkeypatch.setattr(db, "HARNESS_DIR", str(tmp_path))
    db.init_db()


def test_requirements_phase(monkeypatch, tmp_path):
    target = tmp_path / "test_target.py"
    target.write_text("x = 1")
    monkeypatch.setattr(utils, "find_workspace_anchor",
                        lambda _: str(tmp_path))
    engine.run_requirements_phase(
        "P_TEST", str(target), "add feature", "pre", "post", "",
        '{"a":1}', '{"b":2}', "RULE_X")
    spec = db.get_technical_spec(str(target))
    assert spec is not None
    assertions = db.get_assertions_for_file(str(target))
    assert len(assertions) == 1


def test_ingestion_phase(tmp_path):
    src = "x = 1\n"
    target = tmp_path / "simple.py"
    target.write_text(src)
    mode = engine.run_ingestion_phase("P_TEST2", str(target))
    assert mode == "SKELETON"


def test_parse_search_replace():
    text = """
<<<<<<< SEARCH
    let discount = 0;
=======
    let discount = if user.is_vip { 0.15 } else { 0.0 };
>>>>>>> REPLACE
"""
    patches = utils.parse_search_replace(text)
    assert len(patches) == 1
    old, new = patches[0]
    assert "let discount = 0;" in old
    assert "user.is_vip" in new


def test_apply_patch(tmp_path):
    target = tmp_path / "patch_test.txt"
    target.write_text("hello world\nfoo bar\n")
    ok = utils.apply_patch(str(target), "foo bar", "baz qux")
    assert ok
    content = target.read_text()
    assert "baz qux" in content
    assert "hello world" in content


def test_backup_and_restore(tmp_path):
    target = tmp_path / "backup_test.txt"
    target.write_text("original content")
    bak = utils.backup_file(str(target))
    assert os.path.exists(bak)
    target.write_text("modified content")
    utils.restore_backup(bak, str(target))
    assert target.read_text() == "original content"
