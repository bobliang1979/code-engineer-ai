"""code-agent CLI — 自主编码智能体入口。"""

from __future__ import annotations

import argparse
import json
import sys

from .agent import CodeAgent, save_report
from .llm import Generator, HermesGenerator
from .memory import FailureMemory


def main(argv: list[str] | None = None) -> int:
    import io
    import sys as _sys
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="code-agent", description="自主编码智能体 (证据门控闭环)")
    ap.add_argument("--repo", required=True, help="目标仓库路径")
    ap.add_argument("--task", required=True, help="任务描述")
    ap.add_argument("--max-rounds", type=int, default=5)
    ap.add_argument("--model", default=None, help="LLM 模型 (默认用 hermes 当前 provider)")
    ap.add_argument("--memory", default=None, help="教训库路径 (默认 <repo>/.agent_memory.jsonl)")
    ap.add_argument("--output", default="agent_report.json")
    ap.add_argument("--generator", default="hermes",
                    help="生成后端: hermes (默认) | 其他自定义类路径")
    args = ap.parse_args(argv)

    generator: Generator
    if args.generator == "hermes":
        generator = HermesGenerator(model=args.model)
    else:
        # 支持 "module:ClassName" 动态加载自定义生成器
        mod, _, cls = args.generator.partition(":")
        import importlib
        generator = getattr(importlib.import_module(mod), cls)()
        if not isinstance(generator, Generator):
            print("错误: 自定义生成器必须继承 code_agent.llm.Generator", file=sys.stderr)
            return 2

    memory = FailureMemory(args.memory) if args.memory else None
    agent = CodeAgent(args.repo, generator, memory=memory, max_rounds=args.max_rounds)
    report = agent.run(args.task)
    save_report(report, args.output)
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
