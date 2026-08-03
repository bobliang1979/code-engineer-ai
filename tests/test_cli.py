"""CLI 测试 — 产出有效 JSON 报告。"""

import json

from code_benchmark.cli import main


def test_cli_produces_json(tmp_path, capsys):
    src = tmp_path / "demo"
    src.mkdir()
    (src / "m.py").write_text("def f(x):\n    return x * 2\n", encoding="utf-8")
    out = tmp_path / "report.json"
    code = main(["--repo", str(src), "--output", str(out)])
    assert code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "total" in data
    assert len(data["dimensions"]) == 4
    assert "timestamp" in data


def test_cli_requires_repo():
    try:
        main([])
        raise AssertionError("should have exited with error")
    except SystemExit:
        pass
