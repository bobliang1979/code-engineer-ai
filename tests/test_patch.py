"""结构化 patch 协议测试: 解析 / 应用 / 失败语义。"""

from __future__ import annotations

import pytest

from code_agent.patch import PatchOp, apply_patch_ops, parse_patch_json


def test_parse_patch_json_valid():
    content = (
        "PLAN: fix\n```patch\n"
        '[{"path": "a.py", "old": "x", "new": "y"},'
        ' {"path": "b.py", "mode": "create", "new": "z"}]\n'
        "```\n"
    )
    ops = parse_patch_json(content)
    assert len(ops) == 2
    assert ops[0].path == "a.py" and ops[0].old == "x" and ops[0].new == "y"
    assert ops[1].mode == "create" and ops[1].new == "z"


def test_parse_patch_json_empty_when_no_block():
    assert parse_patch_json("no patch here") == []


def test_parse_patch_json_bad_json_raises():
    with pytest.raises(ValueError):
        parse_patch_json("```patch\n{not json}\n```")


def test_apply_replace_ok(tmp_path):
    (tmp_path / "a.py").write_text("def f():\n    return a - b\n", encoding="utf-8")
    ops = [PatchOp(path="a.py", old="return a - b", new="return a + b")]
    r = apply_patch_ops(tmp_path, ops)
    assert r.ok and r.applied == ["a.py"]
    assert "return a + b" in (tmp_path / "a.py").read_text(encoding="utf-8")


def test_apply_replace_old_not_found(tmp_path):
    (tmp_path / "a.py").write_text("return a - b\n", encoding="utf-8")
    ops = [PatchOp(path="a.py", old="return a + b", new="return a * b")]
    r = apply_patch_ops(tmp_path, ops)
    assert not r.ok
    assert r.failures[0]["reason"] == "old_not_found"


def test_apply_replace_old_ambiguous(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\nx = 1\n", encoding="utf-8")
    ops = [PatchOp(path="a.py", old="x = 1", new="x = 2")]
    r = apply_patch_ops(tmp_path, ops)
    assert not r.ok
    assert r.failures[0]["reason"] == "old_ambiguous"


def test_apply_create_and_delete(tmp_path):
    ops = [PatchOp(path="new.py", mode="create", new="print(1)\n"),
           PatchOp(path="gone.py", mode="delete")]
    (tmp_path / "gone.py").write_text("old\n", encoding="utf-8")
    r = apply_patch_ops(tmp_path, ops)
    assert r.ok and len(r.applied) == 2
    assert (tmp_path / "new.py").exists()
    assert not (tmp_path / "gone.py").exists()


def test_invalid_mode_raises():
    with pytest.raises(ValueError):
        PatchOp(path="a.py", mode="explode")
