"""智能体闭环测试 — 证据门控 / 修复循环 / 失败记忆 (确定性 FakeGenerator, 不调 LLM)。"""

from __future__ import annotations

import json
from pathlib import Path

from code_agent.agent import CodeAgent
from code_agent.llm import GeneratedFile, Generation, Generator
from code_agent.memory import FailureMemory
from code_agent.verifier import Verifier


class FakeGenerator(Generator):
    """第一轮写坏代码(触发失败), 第二轮写对。用于测试修复循环与证据门。"""

    def __init__(self, bad_content: str, good_content: str, path: str = "src/fixme.py"):
        self.bad = bad_content
        self.good = good_content
        self.path = path
        self.calls = 0

    def generate(self, task: str, context: dict) -> Generation:
        self.calls += 1
        content = self.bad if self.calls == 1 else self.good
        return Generation(plan=f"plan-{self.calls}", files=[GeneratedFile(self.path, content)])


def _make_repo(tmp: Path) -> Path:
    """仓库: 测试期望 fixme.add 返回 a+b, 但初始实现返回 a-b。"""
    src = tmp / "src"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "fixme.py").write_text(
        "def add(a, b):\n    return a - b\n", encoding="utf-8")
    (tmp / "tests").mkdir()
    (tmp / "conftest.py").write_text(
        "import sys, pathlib\n"
        "sys.path.insert(0, str(pathlib.Path(__file__).parent / 'src'))\n",
        encoding="utf-8")
    (tmp / "tests" / "test_fixme.py").write_text(
        "from fixme import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8")
    return tmp


def test_agent_fixes_via_loop(tmp_path):
    """第一轮坏代码失败 → 教训入库 → 第二轮好代码 → 证据门通过。"""
    repo = _make_repo(tmp_path)
    gen = FakeGenerator(
        bad_content="def add(a, b):\n    return a - b\n",
        good_content="def add(a, b):\n    return a + b\n",
    )
    agent = CodeAgent(repo, gen, max_rounds=3)
    report = agent.run("修复 add 函数使其返回 a+b")

    assert gen.calls == 2          # 失败后进入第二轮修复
    assert report.ok is True       # 证据门: 测试通过才宣称完成
    assert report.verify.passed >= 1
    assert report.verify.failed == 0
    assert report.lessons_recorded == 1
    assert "src/fixme.py" in report.files_changed
    assert (repo / "src" / "fixme.py").read_text(encoding="utf-8").strip() == "def add(a, b):\n    return a + b"


def test_agent_reports_failure_when_never_fixed(tmp_path):
    """max_rounds 耗尽仍未通过 → ok=False, 每轮失败都记录教训。"""
    repo = _make_repo(tmp_path)
    gen = FakeGenerator(
        bad_content="def add(a, b):\n    return a - b\n",
        good_content="def add(a, b):\n    return a - b\n",  # 永不修复
    )
    agent = CodeAgent(repo, gen, max_rounds=2)
    report = agent.run("修复 add 函数")

    assert report.ok is False
    assert report.rounds == 2
    assert report.lessons_recorded == 2
    assert report.verify.failed >= 1


def test_failure_memory_dedupe_and_recall(tmp_path):
    """同症状重复失败 → count 累加不重复堆; 召回按相关性。"""
    mem = FailureMemory(tmp_path / "mem.jsonl")
    mem.record("修复 add 函数", "pytest_failed:1", "fix A")
    mem.record("修复 add 函数", "pytest_failed:1", "fix A")   # 去重 → count=2
    mem.record("重构数据库", "pytest_errors:2", "fix B")
    assert len(mem) == 2

    hits = mem.recall("修复 add 函数返回 a+b")
    assert hits and hits[0]["task"] == "修复 add 函数"
    assert hits[0]["count"] == 2    # 加权: 高频教训排前

    # 持久化: 新实例读到同样数据
    mem2 = FailureMemory(tmp_path / "mem.jsonl")
    assert len(mem2) == 2
    assert mem2.recall("修复 add 函数")[0]["count"] == 2


def test_verifier_gate_blocks_broken_imports(tmp_path):
    """import 链断裂 → ok=False, 即使测试文件本身可收集。"""
    repo = _make_repo(tmp_path)
    (repo / "src" / "fixme.py").write_text(
        "import nonexistent_module_xyz\n\ndef add(a, b):\n    return a + b\n",
        encoding="utf-8")
    v = Verifier(repo)
    result = v.verify()
    assert result.ok is False
    assert any("nonexistent_module_xyz" in e for e in result.import_errors)


def test_report_json_serializable(tmp_path):
    """AgentReport 可序列化为 JSON (CLI 输出契约)。"""
    repo = _make_repo(tmp_path)
    gen = FakeGenerator(
        bad_content="def add(a, b):\n    return a - b\n",
        good_content="def add(a, b):\n    return a + b\n",
    )
    report = CodeAgent(repo, gen, max_rounds=3).run("修复 add")
    data = report.to_dict()
    json.dumps(data)  # 不抛 = 契约成立
    assert data["ok"] is True
    assert "rounds_log" in data
    assert data["benchmark_after"] > 0
