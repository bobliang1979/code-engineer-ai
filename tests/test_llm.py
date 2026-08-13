"""LLM 输出解析测试: 协议块 vs 文件块的区分 (回归: patch JSON 曾被误当文件)。"""

from __future__ import annotations

from code_agent.llm import HermesGenerator
from code_agent.patch import parse_patch_json


def test_parse_files_excludes_protocol_blocks():
    content = (
        "PLAN\n```patch\n"
        '[{"path": "a.py", "old": "x", "new": "y"}]\n'
        "```\n```src/new.py\nprint(1)\n```\n"
    )
    files = HermesGenerator._parse_files(content)
    assert [f.path for f in files] == ["src/new.py"]  # patch 块不产生文件


def test_parse_patch_roundtrip_with_files():
    content = (
        "```patch\n"
        '[{"path": "a.py", "old": "x", "new": "y"},'
        ' {"path": "b.py", "mode": "create", "new": "z"}]\n'
        "```\n"
    )
    ops = parse_patch_json(content)
    assert [o.path for o in ops] == ["a.py", "b.py"]
    assert HermesGenerator._parse_files(content) == []  # 纯协议 → 无文件
