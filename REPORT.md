# REPORT — 超越顶级代码工程师的自主智能体: 构建与验证

日期: 2026-08-13 | 状态: v0.3 (完整闭环, 30 tests 全绿)

## 1. 交付物

| 模块 | 路径 | 说明 |
|---|---|---|
| 度量层 | `src/code_benchmark/metrics.py` | 4 维能力分, 纯 stdlib (ast/subprocess) |
| 度量 CLI | `src/code_benchmark/cli.py` | `code-benchmark --repo --output` |
| 生成后端 | `src/code_agent/llm.py` | HermesGenerator (LLM, 子会话禁工具) + 可插拔 |
| 失败记忆 | `src/code_agent/memory.py` | JSONL 教训库, 去重 + count 加权, 任务召回 |
| 验证门 | `src/code_agent/verifier.py` | pytest + import 链 + benchmark 双门 |
| 智能体主循环 | `src/code_agent/agent.py` | plan→implement→verify→fix→memorize + 回滚门 |
| **结构化 patch** | `src/code_agent/patch.py` | path/old/new JSON 协议, 精确匹配 + 歧义检测 |
| **能力阶梯** | `src/code_agent/ladder.py` | 分数 → D/C/B/A/S 等级 + 目标锚定 (S=超越级) |
| 智能体 CLI | `src/code_agent/cli.py` | `code-agent --repo --task --max-rounds` |

## 2. 维度设计 (度量层)

- **correctness**: 语法错误比例 (ast 解析全仓库 .py)
- **maintainability**: 平均圈复杂度 (ast 自实现) + 超长文件惩罚
- **regression**: pytest 失败比例 (1 - failed/total, 无测试给中性 0.5)
- **coverage**: 测试文件引用的公共函数 / 全部公共函数 (ast 统计)

总分为 4 维均值。全部 stdlib, 零第三方依赖, python>=3.9 跨平台。

## 3. 智能体设计决策

1. **证据门控**: `ok=True` 是严格合取 — pytest>0 passed 且 0 failed/errors 且 import 链干净。LLM 自述"我修好了"不构成完成证据。
2. **NFWST (No Failure Without State Transition)**: 每次验证失败都写入教训库; 同症状去重但 count+1, 高频失败模式在召回中权重更高。**教训真实注入生成上下文** (v0.3 修复: 此前 lessons 从未进 prompt, 闭环是断的)。
3. **教训召回**: 新任务先按关键词重叠度召回历史教训, count 加权排序, 注入下一轮 prompt。
4. **可插拔生成器**: `hermes chat -q` 复用 Hermes 自身 provider (零 API key); **子会话 `-t ""` 禁工具** (v0.3: 防止子会话自己改文件旁路证据门); 任意后端可 `--generator module:Class` 挂载。
5. **结构化 patch 协议** (v0.3): LLM 输出 JSON patch (path/old/new), old 必须精确唯一匹配, 零次/歧义 → 失败进教训库 (patch_no_match)。替代脆弱的整文件围栏块, 降低 LLM 重写整个文件引入回归的风险。
6. **capability-gated 回滚** (v0.3): 每轮与最终验证后, benchmark 分数低于起点 → 自动回滚到任务前快照, 不宣称完成。越修越坏的改动不留存。
7. **能力阶梯** (v0.3): 分数 → 等级映射, S(0.95+)=超越级 / A(0.85+)=专家级 / B(0.70+)=熟练级 / C(0.50+)=入门级 / D。每次任务报告 promoted/demoted 与下一目标。

## 4. 自测结果

### 4.1 单元测试 (30 passed)

```
tests/test_metrics.py    — 8: 4 维各维度 + CLI JSON 契约
tests/test_agent.py      — 5: 修复循环 / 失败不宣称 / 教训去重召回 / import 门 / 序列化
tests/test_patch.py      — 7: 解析 / 应用 / old 不匹配 / 歧义 / create/delete
tests/test_ladder.py     — 4: 等级边界 / 目标锚定 / 升降级
tests/test_self_improve.py — 3: 教训注入上下文 / patch 驱动闭环 / 分数降即回滚
tests/test_llm.py        — 2: 协议块与文件块区分 (回归: patch JSON 曾被误当文件)
```

### 4.2 真实 LLM 端到端 (DeepSeek via hermes, v0.3)

目标: 迷你仓库, 2 个故意 bug (`add` 加减颠倒, `factorial(0)` 返 0)。

```
修复前: pytest 1 passed / 2 failed | benchmark 0.8256 | 等级 B
修复后: pytest 3 passed (100%)     | benchmark 0.8672 | 等级 A (晋升)
轮次: 1  (结构化 patch 一轮命中, 两个 op 均 old 精确匹配)
修改: 仅 src/calc.py (2 个 patch op, 未触碰 tests/)
```

证据: 报告 `files_changed=["src/calc.py","src/calc.py"]` (恰为 2 个 patch op),
`ladder.promoted=true`, 无垃圾文件生成。

### 4.3 验证中捕获并修复的架构级 bug

1. **子会话工具旁路** (v0.2→v0.3): `hermes chat -q` 子会话自带工具, 会把生成提示
   当可执行任务直接改文件 — 证据门/教训/回滚闭环全被旁路 (files_changed=[] 但文件
   已变)。修复: 子进程 `-t ""` 禁工具 + prompt 显式声明无工具。
2. **NFWST 断链**: `_context` 从未把 lessons 放进生成上下文 (`if ctx.get("lessons"): pass`
   是空操作)。修复: 直接注入 `self.memory.recall(task)`。
3. **patch 块误解析**: `_parse_files` 把 ```patch JSON 块当整文件创建 "patch" 垃圾文件。
   修复: 排除协议块 + 回归测试。

### 4.4 已知限制 (诚实标注)

- **coverage 是代理指标**: 函数名引用率, 非真实行覆盖 (不引 coverage.py)。
- **单仓库串行**: 当前一轮处理一个 repo, 无多仓库编排/并发。
- **回滚粒度**: 任务级快照回滚 (全仓库), 无文件级/行级选择性回滚。
- **多轮真实难题**: 单轮 e2e 已证, ≥2 轮的 LLM 真实多轮修复尚未跑 (测试层用 FakeGenerator 覆盖)。

## 5. 下一步 (Roadmap v0.4)

1. **多轮真实难题基准**: 构造必须 ≥2 轮的任务集 (第一轮必然引入新回归), 实测教训
   召回对第二轮成功率的量化提升 (Δ 需机器可证)。
2. **文件级回滚**: 快照按文件粒度, 支持部分保留 (修好 A 坏 B 时只回滚 B)。
3. **补丁上下文增强**: patch 的 old 匹配失败时, 自动将文件当前相关片段回传 LLM 生成
   精确 old (self-healing patch)。
4. **能力分驱动技能沉淀**: benchmark 降维归因 (哪一维拖后腿) → 自动生成对应失败教训。
