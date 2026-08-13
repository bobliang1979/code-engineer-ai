"""可插拔代码生成后端: Hermes CLI (真实 LLM) + 确定性模板 (测试/离线)。"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field

from .patch import PatchOp, parse_patch_json


@dataclass
class GeneratedFile:
    path: str
    content: str


@dataclass
class Generation:
    """一次生成的产物: 计划 + 整文件集 + 结构化 patch 集。"""
    plan: str
    files: list[GeneratedFile] = field(default_factory=list)
    patches: list[PatchOp] = field(default_factory=list)


class Generator:
    """生成器接口。子类实现 generate(task, context) -> Generation。"""

    def generate(self, task: str, context: dict) -> Generation:
        raise NotImplementedError


class HermesGenerator(Generator):
    """真实 LLM 后端: 通过 `hermes chat -q` 路由到当前 provider, 零 API key。"""

    def __init__(self, model: str | None = None, timeout: int = 180):
        self.model = model
        self.timeout = timeout

    def _call(self, prompt: str) -> str:
        # -t "" 禁用子会话工具: 生成器只能输出文本, 绝不能自己改文件
        # (否则 agent 的证据门/教训/回滚闭环全被旁路)
        cmd = ["hermes", "chat", "-q", prompt, "-Q", "-t", ""]
        if self.model:
            cmd.extend(["-m", self.model])
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=self.timeout,
            encoding="utf-8", errors="replace",
        )
        out = result.stdout.strip()
        # 剥离子会话插件日志行 ([conscious-engine] / [unified-bridge] / 无括号追踪等)
        lines = [ln for ln in out.splitlines()
                 if not re.match(r"^\[[a-zA-Z][a-zA-Z-]*(?:\s[^\]]*)?\]\s", ln.strip())
                 and not ln.strip().startswith("插件工具失败追踪")]
        out = "\n".join(lines).strip()
        if out.startswith("session_id:"):
            out = "\n".join(out.split("\n")[1:]).strip()
        if result.returncode != 0 and not out:
            raise RuntimeError(f"hermes CLI failed: {result.stderr.strip()[:500]}")
        return out

    @staticmethod
    def _parse_files(content: str) -> list[GeneratedFile]:
        """解析 ```path\ncontent``` 围栏块为文件集。排除协议块 (patch/json)。"""
        files: list[GeneratedFile] = []
        for m in re.finditer(r"```([^\n`]+)\n(.*?)```", content, re.DOTALL):
            path = m.group(1).strip().lstrip("/")
            if path in ("patch", "json", "json-patch"):
                continue  # 结构化协议块, 非文件
            files.append(GeneratedFile(path=path, content=m.group(2)))
        return files

    def generate(self, task: str, context: dict) -> Generation:
        prompt_parts = [
            "You are an elite autonomous code engineer generating a RESPONSE, not "
            "executing. You have NO tools and NO file access — you cannot modify "
            "files or run commands. Produce a plan and precise edits as text only.",
            f"TASK: {task}",
            f"REPO CONTEXT:\n{json.dumps(context, ensure_ascii=False, indent=1)}",
        ]
        lessons = context.get("lessons") or []
        if lessons:
            prompt_parts.append(
                "LESSONS FROM PAST FAILURES (avoid repeating these mistakes):\n"
                + json.dumps(lessons, ensure_ascii=False, indent=1)
            )
        prompt_parts.append(
            "Respond with:\n"
            "1. PLAN: 2-4 bullet steps (short).\n"
            "2. PATCHES: a single JSON fenced block for surgical edits:\n"
            "```patch\n"
            '[{"path": "src/calc.py", "old": "return a - b", "new": "return a + b"}]\n'
            "```\n"
            "- For a new file: {\"path\": \"src/new.py\", \"mode\": \"create\", \"new\": \"<full content>\"}\n"
            "- For deletion: {\"path\": \"src/old.py\", \"mode\": \"delete\"}\n"
            "- `old` must match the current file EXACTLY and appear exactly once.\n"
            "3. Only for brand-new files that cannot be expressed as patches, a fenced "
            "block with the full content:\n"
            "```relative/path.py\n<complete new file content>\n```\n"
            "Do not use full-file blocks to rewrite existing files."
        )
        content = self._call("\n\n".join(prompt_parts))
        plan = re.split(r"```", content)[0].strip()
        files = self._parse_files(content)
        patches: list[PatchOp] = []
        try:
            patches = parse_patch_json(content)
        except ValueError as e:
            plan += f"\n[patch_parse_error] {e}"
        return Generation(plan=plan[:2000], files=files, patches=patches)


class TemplateGenerator(Generator):
    """确定性后端: 无 LLM 时也能闭环。由子类提供 fix 逻辑。"""

    def generate(self, task: str, context: dict) -> Generation:
        raise NotImplementedError
