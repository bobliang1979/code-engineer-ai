"""能力门控自改进测试: 教训注入 / patch 驱动闭环 / 分数不升即回滚。"""

from __future__ import annotations

from code_agent.agent import CodeAgent
from code_agent.llm import GeneratedFile, Generation, Generator
from code_agent.patch import PatchOp


def _repo(tmp, bad: bool = True) -> object:
    """仓库: calc.add 期望 a+b; bad=True 时实现为 a-b。"""
    src = tmp / "src"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text("", encoding="utf-8")
    body = "def add(a, b):\n    return a - b\n" if bad else "def add(a, b):\n    return a + b\n"
    (src / "calc.py").write_text(body, encoding="utf-8")
    (tmp / "tests").mkdir()
    (tmp / "conftest.py").write_text(
        "import sys, pathlib\n"
        "sys.path.insert(0, str(pathlib.Path(__file__).parent / 'src'))\n",
        encoding="utf-8")
    (tmp / "tests" / "test_calc.py").write_text(
        "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8")
    return tmp


class RecordingGenerator(Generator):
    """坏→好, 记录每轮上下文 (验证教训注入)。"""

    def __init__(self):
        self.contexts: list[dict] = []
        self.calls = 0

    def generate(self, task: str, context: dict) -> Generation:
        self.contexts.append(context)
        self.calls += 1
        good = self.calls > 1
        body = "def add(a, b):\n    return a + b\n" if good else \
            "def add(a, b):\n    return a - b\n"
        return Generation(plan=f"plan-{self.calls}",
                          files=[GeneratedFile("src/calc.py", body)])


class PatchGenerator(Generator):
    """patch 协议驱动: 第一轮 old 不匹配(教训), 第二轮读教训后给出正确 old。"""

    def __init__(self):
        self.calls = 0
        self.saw_lesson = False

    def generate(self, task: str, context: dict) -> Generation:
        self.calls += 1
        self.saw_lesson = bool(context.get("lessons"))
        if self.calls == 1:
            ops = [PatchOp(path="src/calc.py", old="return a + b", new="return a - b")]
        else:
            ops = [PatchOp(path="src/calc.py", old="return a - b", new="return a + b")]
        return Generation(plan=f"plan-{self.calls}", patches=ops)


class GarbageGenerator(Generator):
    """每轮写一个 700 行高圈复杂度文件: 测试仍过但 benchmark 崩 → 触发回滚。"""

    def generate(self, task: str, context: dict) -> Generation:
        g = "def spam(x):\n" + "".join(
            f"    if x == {i}:\n        x = {i}\n" for i in range(100)) + \
            "    return x\n"
        g += "\n".join(f"# pad {i}" for i in range(400)) + "\n"
        return Generation(plan="add garbage",
                          files=[GeneratedFile("src/garbage.py", g)])


def test_lessons_injected_into_context(tmp_path):
    """第一轮失败 → 教训入库 → 第二轮 context 携带 lessons (NFWST 闭环)。"""
    repo = _repo(tmp_path)
    gen = RecordingGenerator()
    CodeAgent(repo, gen, max_rounds=3).run("修复 add 返回 a+b")

    assert gen.calls == 2
    assert gen.contexts[0]["lessons"] == []          # 首轮无历史
    assert len(gen.contexts[1]["lessons"]) == 1      # 第二轮注入失败教训


def test_patch_driven_agent_loop(tmp_path):
    """patch old 不匹配 → 失败进教训 → 第二轮读教训修复成功。"""
    repo = _repo(tmp_path, bad=True)
    gen = PatchGenerator()
    report = CodeAgent(repo, gen, max_rounds=3).run("修复 add 返回 a+b")

    assert gen.calls == 2
    assert gen.saw_lesson is True                     # 教训确实送达生成器
    assert report.ok is True
    assert "src/calc.py" in report.files_changed      # patch 应用计入产物
    assert (repo / "src" / "calc.py").read_text(
        encoding="utf-8").strip().endswith("return a + b")


def test_rollback_when_score_drops(tmp_path):
    """capability gate: 测试通过但 benchmark 崩 (垃圾代码) → 回滚, 不宣称完成。"""
    repo = _repo(tmp_path, bad=False)                 # 起点是好代码 (高 benchmark)
    gen = GarbageGenerator()
    report = CodeAgent(repo, gen, max_rounds=2).run("添加工具函数")

    assert report.rollback is True
    assert report.ok is False
    assert not (repo / "src" / "garbage.py").exists()  # 垃圾文件被还原删除
    assert (repo / "src" / "calc.py").read_text(
        encoding="utf-8").strip().endswith("return a + b")  # 原文件无损
    # 分数恢复起点
    assert report.verify.benchmark_after == report.verify.benchmark_before
