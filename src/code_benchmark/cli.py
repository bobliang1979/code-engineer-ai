"""CLI: code-benchmark --repo <路径> --output report.json"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .metrics import benchmark_repo


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="code-benchmark", description="代码工程师能力基准 (4 维)")
    ap.add_argument("--repo", required=True, help="要评测的仓库路径")
    ap.add_argument("--output", default="report.json", help="输出 JSON 路径")
    args = ap.parse_args(argv)

    report = benchmark_repo(args.repo)
    report["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
