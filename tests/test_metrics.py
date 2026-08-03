"""metrics 4 维测试 — 用 tmp_path 迷你仓库验证。"""

from pathlib import Path

from code_benchmark.metrics import (
    benchmark_repo, correctness, coverage, maintainability, regression,
)


def _make_repo(tmp: Path, good: bool = True) -> Path:
    src = tmp / "src" / "mylib"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    if good:
        (src / "calc.py").write_text(
            "def add(a, b):\n    return a + b\n\ndef loop(n):\n"
            "    total = 0\n    for i in range(n):\n        if i % 2 == 0:\n"
            "            total += i\n    return total\n",
            encoding="utf-8",
        )
    else:
        (src / "calc.py").write_text("def broken(:\n", encoding="utf-8")
    return tmp


def test_correctness_good_repo(tmp_path):
    repo = _make_repo(tmp_path)
    assert correctness(repo) == 1.0


def test_correctness_broken_repo(tmp_path):
    repo = _make_repo(tmp_path, good=False)
    assert correctness(repo) < 1.0


def test_maintainability_in_range(tmp_path):
    repo = _make_repo(tmp_path)
    score = maintainability(repo)
    assert 0.0 <= score <= 1.0


def test_regression_no_tests_neutral(tmp_path):
    repo = _make_repo(tmp_path)
    assert regression(repo) == 0.5


def test_coverage_with_test_references_functions(tmp_path):
    repo = _make_repo(tmp_path)
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_calc.py").write_text(
        "from mylib.calc import add, loop\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    # 公共函数: add, loop, (test_calc 里的 test_add 不算 src)
    score = coverage(repo)
    assert score > 0.0


def test_benchmark_repo_full_report(tmp_path):
    repo = _make_repo(tmp_path)
    report = benchmark_repo(str(repo))
    assert set(report["dimensions"]) == {
        "correctness", "maintainability", "regression", "coverage",
    }
    assert 0.0 <= report["total"] <= 1.0
