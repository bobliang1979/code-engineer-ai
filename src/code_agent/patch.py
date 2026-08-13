"""结构化 patch 协议 — 外科手术式编辑, 替代整文件重写。

LLM 输出 ```patch JSON 数组, 每项:
    {"path": "src/calc.py", "old": "return a - b", "new": "return a + b"}   # replace
    {"path": "src/new.py", "mode": "create", "new": "..."}                  # create
    {"path": "src/old.py", "mode": "delete"}                                # delete

应用纪律 (证据门):
- replace: old 必须在文件中精确出现且唯一; 零次/多次 → 该 op 失败 (歧义不猜)
- 失败的 op 返回详细原因, 供教训库记录 (patch_no_match:<path>)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PatchOp:
    path: str
    new: str = ""
    old: str = ""
    mode: str = "replace"  # replace | create | delete

    def __post_init__(self) -> None:
        if self.mode not in ("replace", "create", "delete"):
            raise ValueError(f"非法 mode: {self.mode}")
        if ".." in self.path or self.path.startswith("/"):
            raise ValueError(f"非法路径: {self.path}")


@dataclass
class PatchResult:
    applied: list[str] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


def parse_patch_json(content: str) -> list[PatchOp]:
    """从 ```patch 围栏块解析 ops。块缺失 → 空列表 (调用方判断)。"""
    for m in re.finditer(r"```(?:patch|json-patch)\n(.*?)```", content, re.DOTALL):
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"patch JSON 解析失败: {e}") from e
        if not isinstance(data, list):
            raise ValueError("patch 必须是 JSON 数组")
        return [PatchOp(**op) for op in data]
    return []


def apply_patch_ops(repo: str | Path, ops: list[PatchOp]) -> PatchResult:
    repo_path = Path(repo)
    result = PatchResult()
    for op in ops:
        target = repo_path / op.path
        if op.mode == "create":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(op.new, encoding="utf-8")
            result.applied.append(op.path)
            continue
        if op.mode == "delete":
            if target.exists():
                target.unlink()
                result.applied.append(op.path)
            else:
                result.failures.append({"path": op.path, "mode": "delete",
                                        "reason": "file_not_found"})
            continue
        # replace
        if not target.exists():
            result.failures.append({"path": op.path, "mode": "replace",
                                    "reason": "file_not_found"})
            continue
        content = target.read_text(encoding="utf-8")
        n = content.count(op.old)
        if n == 0:
            result.failures.append({"path": op.path, "mode": "replace",
                                    "reason": "old_not_found",
                                    "old_preview": op.old[:80]})
        elif n > 1:
            result.failures.append({"path": op.path, "mode": "replace",
                                    "reason": "old_ambiguous",
                                    "occurrences": n})
        else:
            target.write_text(content.replace(op.old, op.new, 1), encoding="utf-8")
            result.applied.append(op.path)
    return result
