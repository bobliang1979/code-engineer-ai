"""验证门 — 证据门控: 无测试通过 = 无状态转移。pytest + import 链 + benchmark。"""

from __future__ import annotations

import ast
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VerifyResult:
    passed: int = 0
    failed: int = 0
    errors: int = 0
    import_errors: list[str] = field(default_factory=list)
    pytest_output: str = ""
    benchmark_before: float = 0.0
    benchmark_after: float = 0.0
    ok: bool = False

    @property
    def test_total(self) -> int:
        return self.passed + self.failed + self.errors


class Verifier:
    def __init__(self, repo: str | Path):
        self.repo = Path(repo)

    def check_imports(self) -> list[str]:
        """静态扫描 import 链: 所有 .py 里顶层 import 的模块能否解析。"""
        errors: list[str] = []
        for f in self.repo.rglob("*.py"):
            if ".venv" in f.parts or ".git" in f.parts or "test" in f.name:
                continue
            try:
                tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError as e:
                errors.append(f"{f}: syntax: {e}")
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        errors.extend(self._try_import(a.name, f))
                elif isinstance(node, ast.ImportFrom) and node.module:
                    errors.extend(self._try_import(node.module, f))
        return errors

    def _try_import(self, mod: str, f: Path) -> list[str]:
        try:
            __import__(mod.split(".")[0])
            return []
        except ImportError as e:
            # 相对导入/本地包跳过(可能依赖 repo 内布局)
            if mod.startswith("."):
                return []
            return [f"{f}: import {mod}: {e}"]
        except Exception:
            return []

    def run_pytest(self) -> tuple[int, int, int, str]:
        test_files = [f for f in self.repo.rglob("test_*.py") if ".venv" not in f.parts]
        if not test_files:
            return 0, 0, 0, ""
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "--no-header"],
                cwd=self.repo, capture_output=True, text=True, timeout=180,
                encoding="utf-8", errors="replace",
            )
            out = (r.stdout or "") + (r.stderr or "")
        except (subprocess.TimeoutExpired, OSError) as e:
            return 0, 0, 1, str(e)
        passed = failed = errors = 0
        for line in out.splitlines():
            m = __import__("re").search(r"(\d+) passed", line)
            n = __import__("re").search(r"(\d+) failed", line)
            e = __import__("re").search(r"(\d+) error", line)
            if m:
                passed = int(m.group(1))
            if n:
                failed = int(n.group(1))
            if e:
                errors = int(e.group(1))
        return passed, failed, errors, out[-3000:]

    def verify(self, before: float | None = None) -> VerifyResult:
        passed, failed, errors, out = self.run_pytest()
        imp_errs = self.check_imports()
        from code_benchmark.metrics import benchmark_repo
        after = benchmark_repo(str(self.repo))["total"]
        ok = failed == 0 and errors == 0 and not imp_errs and test_total(passed, failed, errors) > 0
        return VerifyResult(
            passed=passed, failed=failed, errors=errors, import_errors=imp_errs,
            pytest_output=out, benchmark_before=before or 0.0, benchmark_after=after,
            ok=ok,
        )


def test_total(passed: int, failed: int, errors: int) -> int:
    return passed + failed + errors
