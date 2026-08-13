# Code Engineer AI — 超越顶级代码工程师的自主智能体

证据门控的自主编码智能体 + 能力度量基准。让智能体自主完成
"理解任务 → 生成代码 → 测试验证 → 失败修复 → 教训沉淀" 闭环,
任何一步没有测试证据就不宣称完成。

## 两个包

| 包 | 作用 | 入口 |
|---|---|---|
| `code_benchmark` | 4 维能力度量: correctness / maintainability / regression / coverage | `code-benchmark --repo <path>` |
| `code_agent` | 自主编码智能体: plan→implement→verify→fix→memorize | `code-agent --repo <path> --task "<任务>"` |

## 智能体闭环 (证据门控 + 能力门控)

```
┌─ plan: LLM 生成实现计划 + 结构化 patch (hermes CLI 路由, 零 API key)
│  implement: 应用 patch (old 精确匹配, 歧义拒绝) / 整文件
│  verify: 验证门 ── pytest 全过 + import 链干净 + benchmark 分数
│  fix: 失败 → 症状入教训库 (去重+count加权) → 教训注入下一轮生成
└─ memorize: NFWST — 每次失败都改变系统, 相似任务召回教训避免重犯
```

- **证据门**: `ok=True` 仅当 pytest passed>0 且 0 failed 且 0 errors 且 import 链干净
- **结构化 patch 协议**: LLM 输出 JSON patch `{"path","old","new","mode"}`; old 必须精确唯一匹配,
  零次/歧义 → 失败进教训库 (`patch_no_match`), 不猜测
- **能力阶梯**: benchmark 分数 → D/C/B/A/S 等级 (S=超越级 0.95+), 报告含 promoted/demoted 与下一目标
- **capability-gated 回滚**: 任何轮 benchmark 分数低于起点 → 自动回滚到任务前快照, 不宣称完成
- **失败记忆**: `<repo>/.agent_memory.jsonl`, 同症状去重、count 加权、按任务召回,
  教训真实注入生成上下文 (v0.3 修复 NFWST 断链)
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
(DeepSeek/Claude/Gemini 等, 无需 API key)。子会话以 `-t ""` 禁工具 —
生成器只能输出文本, 绝不能自己改文件 (否则证据门/教训/回滚闭环被旁路)。
自定义生成后端: `--generator mymodule:MyGenerator` (继承 `code_agent.llm.Generator`)。

## 测试

```bash
python -E -m pytest -q   # 30 tests: 度量层 8 + 闭环 5 + patch 7 + 阶梯 4 + 自改进 3 + 解析 2 + CLI 1
```

## 真实验证 (2026-08-13, v0.3)

对含 2 个故意 bug 的迷你仓库 (`add` 加减颠倒 / `factorial(0)` 错):

| 指标 | 修复前 | 修复后 |
|---|---|---|
| pytest | 1 passed / 2 failed | **3 passed** |
| benchmark total | 0.8256 | **0.8672** |
| 能力等级 | B (熟练级) | **A (专家级, 晋升)** |
| 轮次 | — | 1 (结构化 patch 一轮命中) |
| 修改 | — | `src/calc.py` 2 个 patch op, 未触碰 tests/ |

报告: `agent_report.json` 含 task / ok / rounds / rollback / benchmark 前后 /
ladder (等级+升降) / tests / files_changed / rounds_log / lessons。

详见 [REPORT.md](REPORT.md) (含验证中捕获的 3 个架构级 bug 修复记录)。
