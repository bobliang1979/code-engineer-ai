"""可插拔代码生成后端: Hermes CLI (真实 LLM) + 确定性模板 (测试/离线)。"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field


@dataclass
class GeneratedFile:
    path: str
    content: str


@dataclass
class Generation:
    """一次生成的产物: 计划 + 文件集。"""
    plan: str
    files: list[GeneratedFile] = field(default_factory=list)


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
        cmd = ["hermes", "chat", "-q", prompt, "-Q"]
        if self.model:
            cmd.extend(["-m", self.model])
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=self.timeout,
            encoding="utf-8", errors="replace",
        )
        out = result.stdout.strip()
        if out.startswith("session_id:"):
            out = "\n".join(out.split("\n")[1:]).strip()
        if result.returncode != 0 and not out:
            raise RuntimeError(f"hermes CLI failed: {result.stderr.strip()[:500]}")
        return out

    @staticmethod
    def _parse_files(content: str) -> list[GeneratedFile]:
        """解析 ```path\ncontent``` 围栏块为文件集。"""
        files: list[GeneratedFile] = []
        for m in re.finditer(r"```([^\n`]+)\n(.*?)```", content, re.DOTALL):
            path = m.group(1).strip().lstrip("/")
            files.append(GeneratedFile(path=path, content=m.group(2)))
        return files

    def generate(self, task: str, context: dict) -> Generation:
        prompt = (
            "You are an elite autonomous code engineer. Produce a plan and the "
            "exact file contents to accomplish the task.\n\n"
            f"TASK: {task}\n\n"
            f"REPO CONTEXT:\n{json.dumps(context, ensure_ascii=False, indent=1)}\n\n"
            "Respond with:\n"
            "1. PLAN: 2-4 bullet steps (short).\n"
            "2. FILES: for each file to create/modify, a fenced block:\n"
            "```relative/path.py\n<complete new file content>\n```\n"
            "Only include files you actually change. Preserve existing correct code."
        )
        content = self._call(prompt)
        # 计划 = 第一段文本; 文件 = 围栏块
        plan = re.split(r"```", content)[0].strip()
        files = self._parse_files(content)
        return Generation(plan=plan[:2000], files=files)


class TemplateGenerator(Generator):
    """确定性后端: 无 LLM 时也能闭环。由子类提供 fix 逻辑。"""

    def generate(self, task: str, context: dict) -> Generation:
        raise NotImplementedError
