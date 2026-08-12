"""演示: LLM 代理注入的危险代码 (测试 code-guard push 拦截)。"""
import os


def handle(user_input):
    os.system("rm -rf " + user_input)
    return eval(user_input)
