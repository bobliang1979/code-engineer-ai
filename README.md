# Code Engineer AI — 超越顶级代码工程师的自主智能体

证据门控的自主编码智能体 + 能力度量基准。让智能体自主完成
"理解任务 → 生成代码 → 测试验证 → 失败修复 → 教训沉淀" 闭环,
任何一步没有测试证据就不宣称完成。

## 两个包

| 包 | 作用 | 入口 |
|---|---|---|
| `code_benchmark` | 4 维能力度量: correctness / maintainability / regression / coverage | `code-benchmark --repo <path>` |
| `code_agent` | 自主编码智能体: plan→implement→verify→fix→memorize | `code-agent --repo <path> --task "<任务>"` |

## 智能体闭环 (证据门控)

```
┌─ plan: LLM 生成实现计划 + 文件内容 (hermes CLI 路由, 零 API key)
│  implement: 应用文件
│  verify: 验证门 ── pytest 全过 + import 链干净 + benchmark 分数
│  fix: 失败 → 症状入教训库 (去重+count加权) → 下一轮带失败上下文重生成
└─ memorize: NFWST — 每次失败都改变系统, 相似任务召回教训避免重犯
```

- **证据门**: `ok=True` 仅当 pytest passed>0 且 0 failed 且 0 errors 且 import 链干净
- **失败记忆**: `<repo>/.agent_memory.jsonl`, 同症状去重、count 加权、按任务召回
- **能力度量**: 每轮任务前后 benchmark 分数差 = 可验证的能力变化

## 安装

```bash
pip install -e .
```

依赖: 仅 python>=3.9, 零第三方依赖 (ast/subprocess/stdlib)。

## 用法

```bash
# 度量一个仓库的能力分
code-benchmark --repo <路径> --output report.json

# 派智能体修复一个仓库
code-agent --repo <路径> --task "修复 src/calc.py 的 bug, 不要改 tests" \
  --max-rounds 5 --output agent_report.json
```

`code-agent` 默认用 `hermes chat -q` 路由到当前配置的 LLM provider
(DeepSeek/Claude/Gemini 等, 无需 API key)。自定义生成后端:
`--generator mymodule:MyGenerator` (继承 `code_agent.llm.Generator`)。

## 测试

```bash
python -E -m pytest -q   # 13 tests: 度量层 8 + 智能体闭环 5
```

## 真实验证 (2026-08-03)

对含 3 个故意 bug 的迷你仓库 (`add` 乘除颠倒 / `factorial(0)` 错 / `fib` 边界错):

| 指标 | 修复前 | 修复后 |
|---|---|---|
| pytest | 3 failed / 1 passed | **4 passed** |
| benchmark total | 0.793 | **0.856** |
| 轮次 | — | 1 (LLM 一轮修复 3 bug) |
| 修改文件 | — | `src/calc.py` 仅此一个 |

报告: `agent_report.json` 含 task / ok / rounds / benchmark 前后 / tests /
files_changed / rounds_log / lessons。
