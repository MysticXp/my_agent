"""
Day 2：LangGraph create_react_agent 上手实战
对比 Day 1 手写 ReAct（你的 180 行 → 这里不到 30 行）
"""

from langchain_deepseek import ChatDeepSeek
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
import os
from dotenv import load_dotenv

# ============================================================
# 1. 定义工具（和 Day 1 一样，只是用 @tool 装饰器）
# ============================================================
load_dotenv()
@tool
def get_weather(city: str) -> str:
    """获取指定城市的当前天气"""
    weather_data = {
        "北京": "25°C, 晴",
        "上海": "28°C, 多云",
        "广州": "30°C, 阵雨",
        "深圳": "29°C, 阴",
    }
    return f"{city} 天气：{weather_data.get(city, '未知城市')}"


@tool
def calculator(expression: str) -> str:
    """计算数学表达式，如 '1234 * 5678'"""
    try:
        # 安全起见，只允许数字和运算符
        allowed = set("0123456789+-*/.() ")
        if not all(c in allowed for c in expression):
            return "表达式包含非法字符"
        result = eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误：{e}"


# ============================================================
# 2. 一行创建 Agent（对比 Day 1 ~180 行）
# ============================================================

llm = ChatDeepSeek(
    model="deepseek-v4-flash",  # 换成你用的模型，如 gpt-4o-mini / deepseek / qwen
    temperature=0,
    api_key=os.getenv("DEEPSEEK_API_KEY"),  # 或直接填 key
    base_url=os.getenv("DEEPSEEK_BASE_URL")
)

agent = create_react_agent(
    model=llm,
    tools=[get_weather, calculator],
    prompt="你是一个智能助手。调用工具获取信息后，用中文给出简洁自然的回答。",
)

# ============================================================
# 3. invoke 调用
# ============================================================

print("=" * 50)
print("▶ 测试 1：单工具调用")
print("=" * 50)

result = agent.invoke({
    "messages": [("human", "北京天气怎么样？")]
})
print(f"用户：北京天气怎么样？")
print(f"Agent：{result['messages'][-1].content}")
print()

# ============================================================
# 4. 多步任务（对比 Day 1 max_iterations 的效果）
# ============================================================

print("=" * 50)
print("▶ 测试 2：多步任务——先查天气再算温差")
print("=" * 50)

result = agent.invoke({
    "messages": [("human", "北京25度，上海28度，温差多少？")]
})
print(f"用户：北京25度，上海28度，温差多少？")
print(f"Agent：{result['messages'][-1].content}")
print()

# ============================================================
# 5. stream 模式（观察 Agent 思考过程）
# ============================================================

print("=" * 50)
print("▶ 测试 3：stream 模式——观察每一步")
print("=" * 50)

for chunk in agent.stream(
    {"messages": [("human", "计算 1234 * 5678 的结果，然后告诉我深圳天气")]},
    stream_mode="values",
):
    last = chunk["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        for tc in last.tool_calls:
            print(f"  → 调用工具：{tc['name']}({tc['args']})")
    elif last.content:
        print(f"  → {last.content[:80]}")
    print()

print("=" * 50)
print("对比 Day 1 手写版")
print("=" * 50)
print("""
Day 1 手写版（~180行）:                    LangGraph（~30行）:
  while 循环 + 手动控制迭代              create_react_agent 一行创建
  文本解析 + 正则提取 Action              bind_tools 原生结构化输出
  手动拼接 scratchpad                     自动管理 messages 状态
  无 Checkpoint, 崩了重来                 支持 Checkpoint / Human-in-the-loop
  max_iterations 暴力截断                 条件边精确控制流程
""")