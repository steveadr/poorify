import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from poorify import router, db


def _write_temp(content: str, suffix: str = ".py") -> str:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False)
    tmp.write(content)
    tmp.close()
    return tmp.name


class TestPythonComplexity:
    def test_simple_no_branches(self):
        src = "x = 1\ny = 2\n"
        f = _write_temp(src)
        assert router.count_complexity_python(f) == 0
        os.unlink(f)

    def test_one_if(self):
        src = "if x > 0:\n    pass\n"
        f = _write_temp(src)
        assert router.count_complexity_python(f) == 1
        os.unlink(f)

    def test_nested_branches(self):
        src = """
if a:
    for b in c:
        try:
            pass
        except:
            pass
"""
        f = _write_temp(src)
        assert router.count_complexity_python(f) >= 3
        os.unlink(f)

    def test_match_statement(self):
        src = """
match x:
    case 1:
        pass
    case 2:
        pass
"""
        f = _write_temp(src)
        assert router.count_complexity_python(f) == 2
        os.unlink(f)


class TestRouting:
    @pytest.fixture(autouse=True)
    def _patch_db(self, monkeypatch, tmp_path):
        test_db = tmp_path / "test_harness.db"
        monkeypatch.setattr(db, "DB_PATH", str(test_db))
        monkeypatch.setattr(db, "HARNESS_DIR", str(tmp_path))
        db.init_db()

    def test_skeleton_for_low_complexity(self):
        src = "x = 1\n"
        f = _write_temp(src)
        mode = router.route_file(f)
        assert mode == "SKELETON"
        os.unlink(f)

    def test_full_for_high_complexity(self):
        lines = [f"if x == {i}: pass\n" for i in range(10)]
        src = "\n".join(lines)
        f = _write_temp(src)
        mode = router.route_file(f)
        assert mode == "FULL"
        os.unlink(f)


class TestSkeletonize:
    def test_skeletonize_python(self):
        src = """
def foo(a, b):
    c = a + b
    return c

class Bar:
    def baz(self):
        print("hello")
"""
        f = _write_temp(src)
        result = router.skeletonize_file(f)
        assert "def foo" in result
        assert "class Bar" in result
        os.unlink(f)
