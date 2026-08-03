"""失败教训库 — NFWST: 每次失败都改变系统。JSONL 持久化, 去重 + count 加权。"""

from __future__ import annotations

import json
import time
from pathlib import Path


class FailureMemory:
    """按任务关键词召回相似教训, 失败时写入 (去重, count 累加)。"""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                self._entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    def _save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for e in self._entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        tmp.replace(self.path)

    def record(self, task: str, symptom: str, fix: str) -> None:
        """写入一条教训。同 task+symptom 已存在 → count+1 (加权, 不重复堆)。"""
        key = f"{task}|{symptom}"
        for e in self._entries:
            if f"{e['task']}|{e['symptom']}" == key:
                e["count"] += 1
                e["last_seen"] = time.time()
                self._save()
                return
        self._entries.append({
            "task": task, "symptom": symptom, "fix": fix,
            "count": 1, "created": time.time(), "last_seen": time.time(),
        })
        self._save()

    def recall(self, task: str, limit: int = 3) -> list[dict]:
        """按 task 关键词与条目重叠度召回, count 加权排序。"""
        words = {w for w in task.lower().split() if len(w) > 2}
        if not words:
            return []
        scored = []
        for e in self._entries:
            ewords = {w for w in f"{e['task']} {e['symptom']}".lower().split() if len(w) > 2}
            overlap = len(words & ewords)
            if overlap:
                scored.append((overlap * e.get("count", 1), e))
        scored.sort(key=lambda x: -x[0])
        return [e for _, e in scored[:limit]]

    def __len__(self) -> int:
        return len(self._entries)
