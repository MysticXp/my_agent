"""
Day 1: 从零手写 ReAct Agent
不依赖 LangChain，只用 Python 标准库 + openai SDK（连接 DeepSeek API）

核心流程:
  User Input → [Thought → Action → Observation] × N → Final Answer
"""

import json
import time
from dataclasses import dataclass
from typing import Any, Optional
from openai import OpenAI

# ============================================================
# 1. 核心数据模型
# ============================================================

@dataclass
class AgentAction:
    """LLM 决定调用工具"""
    tool: str
    tool_input: dict

@dataclass
class AgentFinish:
    """LLM 认为任务完成"""
    return_values: dict

@dataclass
class AgentStep:
    """一轮完整的交互记录"""
    action: AgentAction
    observation: str  # 工具返回的结果


# ============================================================
# 2. 工具定义
# ============================================================

def search(query: str) -> str:
    """模拟搜索工具（实际使用时替换为真实搜索 API）"""
    # 这里用模拟数据，实际替换为搜索引擎 API
    return f'搜索结果：关于"{query}"，找到相关匹配内容...'


def calculator(expression: str) -> str:
    """安全计算数学表达式"""
    try:
        # 只允许数字和基本运算符，防止代码注入
        allowed = set("0123456789+-*/().% ")
        if not all(c in allowed for c in expression):
            return "错误：表达式包含不允许的字符"
        result = eval(expression)
        return str(result)
    except Exception as e:
        return f"计算错误：{e}"


# 工具注册表
TOOLS = {
    "search": {
        "function": search,
        "description": "搜索互联网获取信息。输入：query（搜索关键词）",
        "input_schema": {"query": "string"}
    },
    "calculator": {
        "function": calculator,
        "description": "计算数学表达式。输入：expression（数学表达式，如 100*23）",
        "input_schema": {"expression": "string"}
    }
}


# ============================================================
# 3. ReAct Prompt 模板
# ============================================================

REACT_PROMPT = """你是一个能使用工具的 AI 助手。请用以下格式回答：

可用工具：
{tools}

回答格式：
Thought: 我需要做什么，为什么
Action: 工具名
Action Input: {{"参数名": "参数值"}}
Observation: 工具返回结果
...（可重复 Thought/Action/Action Input/Observation 多轮）
Thought: 我现在有足够信息回答了
Final Answer: 最终答案

注意：
- Action Input 必须是合法的 JSON
- 不要自己编造 Observation，它由系统生成
- 当你有足够信息时，用 Final Answer 结束

用户问题：{question}
{agent_scratchpad}"""


# ============================================================
# 4. 输出解析器：从 LLM 文本中提取 Action 或 Final Answer
# ============================================================

def parse_output(text: str):
    """解析 LLM 输出，返回 AgentAction 或 AgentFinish"""
    if "Final Answer:" in text:
        answer = text.split("Final Answer:")[-1].strip()
        return AgentFinish(return_values={"output": answer})

    if "Action:" in text and "Action Input:" in text:
        # 提取 Action 名称
        action_line = text.split("Action:")[1].split("\n")[0].strip()
        # 提取 Action Input（JSON）
        input_start = text.index("Action Input:") + len("Action Input:")
        input_text = text[input_start:].strip()
        # 提取 JSON 对象
        brace_start = input_text.index("{")
        brace_end = input_text.rindex("}") + 1
        input_json = json.loads(input_text[brace_start:brace_end])
        return AgentAction(tool=action_line, tool_input=input_json)

    raise ValueError(f"无法解析 LLM 输出：{text[:200]}")


# ============================================================
# 5. 核心执行循环
# ============================================================

def run_react_agent(
    question: str,
    llm_client: OpenAI,
    model: str = "deepseek-v4-pro",
    max_iterations: int = 5,
    max_execution_time: float = 60.0,
    verbose: bool = True
) -> dict:
    """
    ReAct Agent 主循环

    参数:
        question: 用户问题
        llm_client: OpenAI 客户端
        model: 模型名称
        max_iterations: 最大迭代次数（防止死循环）
        max_execution_time: 最大执行时间（秒）
        verbose: 是否打印中间步骤
    """
    # 构建工具描述
    tools_desc = "\n".join([
        f"- {name}: {info['description']}"
        for name, info in TOOLS.items()
    ])

    intermediate_steps = []
    start_time = time.time()

    for i in range(max_iterations):
        # 时间检查
        if time.time() - start_time > max_execution_time:
            return {"output": "任务超时，已终止执行"}

        # 构建 agent_scratchpad（历史步骤）
        scratchpad = ""
        for step in intermediate_steps:
            scratchpad += f"\nAction: {step.action.tool}\n"
            scratchpad += f"Action Input: {json.dumps(step.action.tool_input)}\n"
            scratchpad += f"Observation: {step.observation}\n"

        # 构建完整 prompt
        prompt = REACT_PROMPT.format(
            tools=tools_desc,
            question=question,
            agent_scratchpad=scratchpad
        )

        if verbose:
            print(f"\n{'='*50}")
            print(f"🔄 第 {i+1} 轮")
            print(f"{'='*50}")

        # 调用 LLM
        response = llm_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            stop=["\nObservation", "Observation:"]
        )
        llm_output = response.choices[0].message.content

        if verbose:
            print(f"💭 LLM 输出:\n{llm_output}")

        # 解析输出
        parsed = parse_output(llm_output)

        # 如果是 Final Answer，直接返回
        if isinstance(parsed, AgentFinish):
            return parsed.return_values

        # 如果是 Action，执行工具
        if isinstance(parsed, AgentAction):
            tool_name = parsed.tool

            if tool_name not in TOOLS:
                observation = f"错误：工具 '{tool_name}' 不存在，可用工具：{list(TOOLS.keys())}"
            else:
                try:
                    tool_func = TOOLS[tool_name]["function"]
                    observation = tool_func(**parsed.tool_input)
                except Exception as e:
                    observation = f"工具执行失败：{e}"

            if verbose:
                print(f"🔧 执行 {tool_name}: {parsed.tool_input}")
                print(f"👁️ Observation: {observation}")

            intermediate_steps.append(AgentStep(action=parsed, observation=observation))

    # 超过最大迭代次数，强制终止
    return {"output": f"达到最大迭代次数 {max_iterations}，任务终止"}


# ============================================================
# 6. 运行示例
# ============================================================

if __name__ == "__main__":
    # 替换为你的 DeepSeek API Key
    client = OpenAI(
        api_key="sk-edcb3136fee44dba9b8a5cbb8f48f396",
        base_url="https://api.deepseek.com"
    )

    # 测试问题
    question = "计算 123 * 456 的结果，然后搜索一下这个数字有什么特殊含义"

    result = run_react_agent(
        question=question,
        llm_client=client,
        max_iterations=5,
        verbose=True
    )

    print(f"\n{'='*50}")
    print(f"✅ 最终答案: {result['output']}")