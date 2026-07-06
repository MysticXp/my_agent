"""
Day 2：LangChain create_agent 上手实战（2026 新版 API）
替代已弃用的 create_react_agent

对比 Day 1 手写 ReAct（180 行 → 这里不到 30 行）
"""

from langchain_deepseek import ChatDeepSeek
from langchain_core.tools import tool
from langchain.agents import create_agent
import os
from dotenv import load_dotenv

load_dotenv()
# ============================================================
# 1. 定义工具（和 Day 1 一样，只是用 @tool 装饰器）
# ============================================================

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
        allowed = set("0123456789+-*/.() ")
        if not all(c in allowed for c in expression):
            return "表达式包含非法字符"
        result = eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误：{e}"


# ============================================================
# 2. 一行创建 Agent（对比 Day 1 ~180 行）
#    create_agent 是 LangChain 1.0 的新标准 API，
#    底层跑在 LangGraph 上，自带 middleware 系统。
# ============================================================

llm = ChatDeepSeek(
    model="deepseek-chat",  # 换成你用的模型
    temperature=0,
    api_key=os.getenv("DEEPSEEK_API_KEY"),
)

agent = create_agent(
    model=llm,
    tools=[get_weather, calculator],
    system_prompt="你是一个智能助手。调用工具获取信息后，用中文给出简洁自然的回答。",
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
# 4. 多步任务
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
print("进化路线一览")
print("=" * 50)
print("""
AgentExecutor（已弃用）     ← while 循环封装版
     ↓
create_react_agent（已弃用） ← LangGraph 预构建版
     ↓
create_agent（当前标准）    ← LangChain 1.0 + LangGraph 底层 + middleware

关键区别：
- create_agent 底层就是 LangGraph 状态机
- 自带 middleware 系统（before_model / after_model / wrap_tool_call）
- 支持 checkpointer、thread_id、response_format
""")