# REPORT — 超越顶级代码工程师的自主智能体: 构建与验证

日期: 2026-08-03 | 状态: v0.2 (基准层 + 智能体本体, 全绿)

## 1. 交付物

| 模块 | 路径 | 说明 |
|---|---|---|
| 度量层 | `src/code_benchmark/metrics.py` | 4 维能力分, 纯 stdlib (ast/subprocess) |
| 度量 CLI | `src/code_benchmark/cli.py` | `code-benchmark --repo --output` |
| 生成后端 | `src/code_agent/llm.py` | HermesGenerator (LLM) + TemplateGenerator (可插拔) |
| 失败记忆 | `src/code_agent/memory.py` | JSONL 教训库, 去重 + count 加权, 任务召回 |
| 验证门 | `src/code_agent/verifier.py` | pytest + import 链 + benchmark 双门 |
| 智能体主循环 | `src/code_agent/agent.py` | plan→implement→verify→fix→memorize |
| 智能体 CLI | `src/code_agent/cli.py` | `code-agent --repo --task --max-rounds` |

## 2. 维度设计 (度量层)

- **correctness**: 语法错误比例 (ast 解析全仓库 .py)
- **maintainability**: 平均圈复杂度 (ast 自实现) + 超长文件惩罚
- **regression**: pytest 失败比例 (1 - failed/total, 无测试给中性 0.5)
- **coverage**: 测试文件引用的公共函数 / 全部公共函数 (ast 统计)

总分为 4 维均值。全部 stdlib, 零第三方依赖, python>=3.9 跨平台。

## 3. 智能体设计决策

1. **证据门控**: `ok=True` 是严格合取 — pytest>0 passed 且 0 failed/errors 且 import 链干净。LLM 自述"我修好了"不构成完成证据。
2. **NFWST (No Failure Without State Transition)**: 每次验证失败都写入教训库; 同症状去重但 count+1, 高频失败模式在召回中权重更高。
3. **教训召回**: 新任务先按关键词重叠度召回历史教训, count 加权排序。
4. **可插拔生成器**: `hermes chat -q` 复用 Hermes 自身 provider (零 API key、零新依赖); 测试用确定性 FakeGenerator 保证闭环可复现; 任意后端可通过 `--generator module:Class` 挂载。
5. **基准分数即能力变化**: benchmark_before→after 之差是每次任务可验证的能力增量, 为 capability-gated self-improvement 提供度量基础。

## 4. 自测结果

### 4.1 单元测试 (13 passed)

```
tests/test_metrics.py  — 8 测试: 4 维各维度 + CLI JSON 契约
tests/test_agent.py    — 5 测试: 修复循环 / 失败不宣称 / 教训去重召回 /
                         import 链证据门 / 报告序列化
```

### 4.2 真实 LLM 端到端 (DeepSeek via hermes)

目标: 迷你仓库, 3 个故意 bug (`add` 乘除颠倒, `factorial(0)` 返 0, `fib` 边界错)。

```
修复前: pytest 3 failed / 1 passed | benchmark 0.793
修复后: pytest 4 passed (100%)    | benchmark 0.856
轮次: 1  (LLM 一轮生成正确文件, 验证门一次通过)
修改: 仅 src/calc.py (未触碰 tests/)
```

证据: 修复后的 `src/calc.py`:
```python
def add(a, b):       return a + b          # 原 a*b
def factorial(n):    ... if n == 0: return 1   # 原 return 0
def fib(n):          ... return a          # 原 return b (边界错)
```

### 4.3 已知限制 (诚实标注)

- **原型级**: `HermesGenerator` 用字符串围栏块解析文件, 依赖 LLM 输出格式;
  复杂重构 (跨文件 API 变更) 未在 e2e 覆盖。生产级需结构化 diff 协议。
- **coverage 是代理指标**: 函数名引用率, 非真实行覆盖 (不引 coverage.py)。
- **单仓库串行**: 当前一轮处理一个 repo, 无多仓库编排/并发。
- **LLM 失败仅计数**: 生成后端抛错时记录教训但无重试策略切换。

## 5. 下一步 (Roadmap)

1. **能力阶梯**: benchmark 分数 → 阶梯映射 (青铜/白银/黄金), 目标锚定
2. **多轮真实修复**: 构造必须 ≥2 轮的难题, 验证教训召回确实改进第二轮
3. **结构化 patch 协议**: JSON diff (path/old/new) 替代围栏块, 提高生成可靠率
4. **capability-gated self-improvement**: 分数不升即回滚, 分数驱动技能更新
