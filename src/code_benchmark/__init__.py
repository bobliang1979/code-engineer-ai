"""code_benchmark — 代码工程师能力基准。

4 维评测 (每维 0-1):
  correctness    正确率: 语法/import 错误比例
  maintainability 可维护性: 平均圈复杂度 + 文件长度代理
  regression     回归率: 既有测试失败比例
  coverage       测试覆盖代理: 测试引用的公共函数比例
"""
from .metrics import benchmark_repo

__all__ = ["benchmark_repo"]
__version__ = "0.1.0"
