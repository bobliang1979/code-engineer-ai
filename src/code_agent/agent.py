"""自主编码智能体主循环: plan → implement → verify → fix → memorize。
证据门控: 无测试通过 = 不宣称完成。失败教训入库, 下次召回避免重犯 (NFWST)。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from .llm import Generator
from .memory import FailureMemory
from .verifier import VerifyResult, Verifier


@dataclass
class AgentReport:
    task: str
    rounds: int = 0
    ok: bool = False
    verify: VerifyResult = field(default_factory=VerifyResult)
    plan: str = ""
    lessons_recalled: list[dict] = field(default_factory=list)
    lessons_recorded: int = 0
    files_changed: list[str] = field(default_factory=list)
    rounds_log: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "ok": self.ok,
            "rounds": self.rounds,
            "benchmark_before": self.verify.benchmark_before,
            "benchmark_after": self.verify.benchmark_after,
            "tests": {"passed": self.verify.passed, "failed": self.verify.failed,
                      "errors": self.verify.errors},
            "import_errors": self.verify.import_errors,
            "plan": self.plan,
            "lessons_recalled": self.lessons_recalled,
            "lessons_recorded": self.lessons_recorded,
            "files_changed": self.files_changed,
            "rounds_log": self.rounds_log,
        }


class CodeAgent:
    def __init__(self, repo: str | Path, generator: Generator,
                 memory: FailureMemory | None = None,
                 max_rounds: int = 5, verifier: Verifier | None = None):
        self.repo = Path(repo)
        self.generator = generator
        self.memory = memory or FailureMemory(self.repo / ".agent_memory.jsonl")
        self.max_rounds = max_rounds
        self.verifier = verifier or Verifier(self.repo)

    def _context(self, task: str, round_no: int, last_result: VerifyResult | None) -> dict:
        ctx: dict = {"task": task, "round": round_no, "repo": str(self.repo)}
        files = sorted(p for p in self.repo.rglob("*.py")
                       if ".venv" not in p.parts and ".git" not in p.parts)
        ctx["files"] = [
            {"path": str(p.relative_to(self.repo)), "size": p.stat().st_size}
            for p in files[:50]
        ]
        if last_result:
            ctx["last_verification"] = {
                "passed": last_result.passed, "failed": last_result.failed,
                "errors": last_result.errors,
                "import_errors": last_result.import_errors,
                "pytest_output_tail": last_result.pytest_output[-1500:],
            }
        return ctx

    def run(self, task: str) -> AgentReport:
        # 0) 证据门: 任务前基准
        before = self.verifier.verify()
        baseline = before.benchmark_after
        report = AgentReport(task=task)
        report.verify.benchmark_before = baseline
        report.lessons_recalled = self.memory.recall(task)

        last_result: VerifyResult | None = None
        for r in range(1, self.max_rounds + 1):
            report.rounds = r
            ctx = self._context(task, r, last_result)
            if ctx.get("lessons"):
                pass  # 教训通过 memory.recall 已注入 generator 端
            try:
                gen = self.generator.generate(task, ctx)
            except Exception as e:  # 生成失败也是失败, 记录教训
                self.memory.record(task, f"generation_error: {e}", "检查生成后端可用性")
                report.rounds_log.append({"round": r, "action": "generate", "ok": False,
                                          "error": str(e)[:300]})
                last_result = last_result or VerifyResult(errors=1)
                continue

            report.plan = gen.plan or report.plan
            applied = self._apply_files(gen)
            report.files_changed.extend(applied)

            result = self.verifier.verify(before=baseline)
            report.verify = result
            report.rounds_log.append({
                "round": r, "action": "verify",
                "passed": result.passed, "failed": result.failed, "errors": result.errors,
                "benchmark": result.benchmark_after,
            })
            if result.ok:
                report.ok = True
                break
            # 失败 → 提取症状, 记录教训
            symptom = self._symptom(result)
            fix = f"修复 round{r} 失败: pytest {result.failed}f/{result.errors}e, benchmark {result.benchmark_after}"
            self.memory.record(task, symptom, fix)
            report.lessons_recorded += 1
            last_result = result

        report.verify.benchmark_after = (last_result or report.verify).benchmark_after
        return report

    def _apply_files(self, gen) -> list[str]:
        applied: list[str] = []
        for f in gen.files:
            if not f.path or ".." in f.path:
                continue
            target = self.repo / f.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f.content, encoding="utf-8")
            applied.append(f.path)
        return applied

    @staticmethod
    def _symptom(result: VerifyResult) -> str:
        if result.errors:
            return f"pytest_errors:{result.errors} import:{len(result.import_errors)}"
        if result.failed:
            return f"pytest_failed:{result.failed}"
        return "no_tests"


def run_agent(repo: str, task: str, generator: Generator,
              max_rounds: int = 5) -> AgentReport:
    return CodeAgent(repo, generator, max_rounds=max_rounds).run(task)


def save_report(report: AgentReport, path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
                   encoding="utf-8")
