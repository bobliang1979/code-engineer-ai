"""4 维评测指标。全部用 stdlib(ast/subprocess), 零新依赖。"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


def _py_files(repo: Path) -> list[Path]:
    if not repo.exists():
        return []
    return [p for p in repo.rglob("*.py") if ".venv" not in p.parts and ".git" not in p.parts]


def _public_functions(tree: ast.Module) -> list[ast.FunctionDef]:
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not n.name.startswith("_")]


def _cyclomatic(node: ast.AST) -> int:
    """圈复杂度: if/for/while/and/or/except/comprehension 计数 + 1。"""
    score = 1
    for n in ast.walk(node):
        if isinstance(n, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
            score += 1
        elif isinstance(n, ast.BoolOp):
            score += len(n.values) - 1
        elif isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            score += 1
    return score


def correctness(repo: Path) -> float:
    """语法 + import 错误比例: 1 - error_ratio。"""
    files = _py_files(repo)
    if not files:
        return 0.0
    errors = 0
    for f in files:
        try:
            ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            errors += 1
    return round(max(0.0, 1.0 - errors / len(files)), 4)


def maintainability(repo: Path) -> float:
    """平均圈复杂度 + 超长文件惩罚, 映射到 0-1。"""
    files = _py_files(repo)
    if not files:
        return 0.0
    complexities: list[int] = []
    long_files = 0
    for f in files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            long_files += 1  # 不可解析视为维护性差
            continue
        for fn in _public_functions(tree):
            complexities.append(_cyclomatic(fn))
        if len(f.read_text(encoding="utf-8", errors="replace").splitlines()) > 400:
            long_files += 1
    if not complexities:
        avg_cc = 3.0  # 无函数时给中性值
    else:
        avg_cc = sum(complexities) / len(complexities)
    # 圈复杂度 <5 优, 5-10 中, >10 差
    cc_score = max(0.0, 1.0 - (avg_cc - 1.0) / 9.0)
    long_penalty = 1.0 - min(1.0, long_files / max(1, len(files)))
    return round(max(0.0, min(1.0, 0.7 * cc_score + 0.3 * long_penalty)), 4)


def regression(repo: Path) -> float:
    """既有测试破坏率: 1 - failed/total。无测试 → 0.5 中性。"""
    files = _py_files(repo)
    test_files = [f for f in files if "test" in f.name.lower()]
    if not test_files:
        return 0.5
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--no-header"],
            cwd=repo, capture_output=True, text=True, timeout=120,
        )
        out = r.stdout + r.stderr
    except (subprocess.TimeoutExpired, OSError):
        return 0.0
    # 解析 "N passed, M failed" 或 "M failed"
    passed = failed = 0
    for line in out.splitlines():
        if "passed" in line and "failed" in line:
            import re
            m = re.search(r"(\d+) passed", line)
            f = re.search(r"(\d+) failed", line)
            passed = int(m.group(1)) if m else 0
            failed = int(f.group(1)) if f else 0
            break
        elif "failed" in line and "error" not in line:
            import re
            f = re.search(r"(\d+) failed", line)
            failed = int(f.group(1)) if f else 0
            break
    total = passed + failed
    if total == 0:
        return 0.5
    return round(max(0.0, 1.0 - failed / total), 4)


def coverage(repo: Path) -> float:
    """测试覆盖代理: 测试文件 import 的公共函数名 / 全部公共函数名。"""
    files = _py_files(repo)
    src_files = [f for f in files if "test" not in f.name.lower()]
    test_files = [f for f in files if "test" in f.name.lower()]
    if not src_files:
        return 0.0
    all_fns = set()
    for f in src_files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        all_fns |= {fn.name for fn in _public_functions(tree)}
    if not all_fns:
        return 0.5
    used = set()
    for f in test_files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Name) and n.id in all_fns:
                used.add(n.id)
            elif isinstance(n, ast.Attribute) and n.attr in all_fns:
                used.add(n.attr)
    return round(len(used) / len(all_fns), 4)


def benchmark_repo(repo: str) -> dict:
    """对仓库跑全 4 维, 返回报告 dict。"""
    repo_path = Path(repo)
    dims = {
        "correctness": correctness(repo_path),
        "maintainability": maintainability(repo_path),
        "regression": regression(repo_path),
        "coverage": coverage(repo_path),
    }
    total = round(sum(dims.values()) / len(dims), 4)
    return {"total": total, "dimensions": dims, "raw": {"files": len(_py_files(repo_path))}}
