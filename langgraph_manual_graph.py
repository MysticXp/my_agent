"""
Day 2 动手补完：手搭 LangGraph + Human-in-the-loop

和 Day 1 手写 ReAct 逐行对照，你就会发现：
  while 循环  →  Edge("tools", "agent")
  解析 Action →  tools_condition()
  拼接 scratchpad →  add_messages reducer
"""

from langchain_deepseek import ChatDeepSeek
from langchain_core.tools import tool
from langchain_core.messages import AIMessage, ToolMessage
from typing import Annotated, Literal
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
import os

# ============================================================
# 0. 工具定义（和 Day 1 完全一致）
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


tools = [get_weather, calculator]

llm = ChatDeepSeek(
    model="deepseek-chat",
    temperature=0,
    api_key=os.getenv("DEEPSEEK_API_KEY"),
)
llm_with_tools = llm.bind_tools(tools)

# ============================================================
# 1. 定义 State
#    对比 Day 1 的 intermediate_steps 列表
# ============================================================

class AgentState(TypedDict):
    """State = 所有节点共享的黑板"""
    messages: Annotated[list, add_messages]  # reducer 自动追加消息

# add_messages 的作用（对比 Day 1）：
#   Day 1：你手动 intermediate_steps.append(...)
#   这里：  ToolNode 返回的消息自动合并到 messages
#           如果消息 ID 重复，覆盖而不是追加

# ============================================================
# 2. 定义 Node
#    每个 Node 是一个函数：读取 State → 处理 → 返回更新
# ============================================================

def call_model(state: AgentState):
    """LLM 节点（对比 Day 1 的 llm(prompt)）"""
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}


# ToolNode 是官方预置的，等价于 Day 1 的：
#   for action in actions:
#       obs = tool_func(action.tool, action.tool_input)
#       intermediate_steps.append((action, obs))
tool_node = ToolNode(tools)

# ============================================================
# 3. 构建图
#    对比 Day 1：while True → 解析 → 执行 → 拼接 → 继续
# ============================================================

builder = StateGraph(AgentState)

# 注册节点
builder.add_node("agent", call_model)    # LLM 思考
builder.add_node("tools", tool_node)     # 工具执行

# 连边
builder.add_edge(START, "agent")                    # 开始 → 先思考
builder.add_conditional_edges(
    "agent",
    tools_condition,      # 判断：如果有 tool_calls → 走 tools，否则 → END
)
builder.add_edge("tools", "agent")  # 工具执行完 → 回到 agent 继续思考

# 对照 Day 1 的 while 循环：
#   Day 1：                          LangGraph：
#     while True:                      builder.add_edge("tools", "agent")
#       llm_output = llm(prompt)       call_model(state)
#       action = parse(llm_output)     tools_condition (判断 tool_calls)
#       obs = tool_func(action)        ToolNode
#       prompt += f"Observation: {obs}"  add_messages 自动拼接

# ============================================================
# 4. 编译
# ============================================================

graph = builder.compile()

# ============================================================
# 5. 测试运行
# ============================================================

print("=" * 60)
print("🔧 Part 1：手搭 Graph —— 测试运行")
print("=" * 60)

result = graph.invoke({
    "messages": [("human", "北京天气怎么样？")]
})
print(f"用户：北京天气怎么样？")
print(f"Agent：{result['messages'][-1].content}")
print()

# ============================================================
# 6. 流式观察：看每一步的思考过程
# ============================================================

print("=" * 60)
print("🔧 stream 模式——观察每个节点的执行")
print("=" * 60)

for event in graph.stream(
    {"messages": [("human", "计算 25 * 4 + 10 等于多少")]},
    stream_mode="updates",
):
    for node_name, update in event.items():
        if "messages" in update:
            msg = update["messages"][-1]
            if node_name == "agent":
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        print(f"  🤔 agent→ 调用: {tc['name']}({tc['args']})")
                else:
                    print(f"  💬 agent→ 回答: {msg.content[:60]}")
            elif node_name == "tools":
                print(f"  🔧 tools→ 结果: {msg.content[:60]}")
print()

print("对照 Day 1 的 while 循环，每一步都能看见了！")
print()

# ============================================================
# 7. Human-in-the-loop：工具调用前暂停
# ============================================================

print("=" * 60)
print("🔧 Part 2：Human-in-the-loop —— 工具调用前确认")
print("=" * 60)

# 加 checkpointer + interrupt_before
graph_with_hitl = builder.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["tools"],  # ⚠️ 进入 tools 节点前暂停
)

# 第一次调用——会在 tools 前暂停
thread_config = {"configurable": {"thread_id": "hitl-demo-1"}}

print("▶ 提问：'北京天气怎么样？'")
print()
print("执行过程：")
for event in graph_with_hitl.stream(
    {"messages": [("human", "北京天气怎么样？")]},
    config=thread_config,
    stream_mode="updates",
):
    for node_name, update in event.items():
        if "messages" in update:
            msg = update["messages"][-1]
            if node_name == "agent":
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        print(f"  🤔 agent 想调用: {tc['name']}({tc['args']})")
                else:
                    print(f"  💬 agent: {msg.content[:60]}")
            elif node_name == "tools":
                print(f"  🔧 tools: {msg.content[:60]}")

# 到这里会暂停，因为 interrupt_before=["tools"]
# 实际业务中，这里会等人工审批
print()
print("⚠️  暂停点：agent 想调工具，等待确认...")
print()

# 模拟确认——resume
print("▶ 人工确认通过，继续执行...")
print()
for event in graph_with_hitl.stream(
    None,  # 传 None = 从暂停点继续
    config=thread_config,
    stream_mode="updates",
):
    for node_name, update in event.items():
        if "messages" in update:
            msg = update["messages"][-1]
            if node_name == "tools":
                print(f"  🔧 tools: {msg.content[:60]}")
            elif node_name == "agent":
                print(f"  💬 agent: {msg.content[:60]}")

print()
print("✅ Human-in-the-loop 完成！")
print()
print("=" * 60)
print("🧠 和 Day 1 手写版的全面对照")
print("=" * 60)
print("""
Day 1 手写 ReAct (~180行)        手搭 LangGraph (~50行)
────────────────────────────    ────────────────────────────
class AgentAction/AgentFinish     TypedDict AgentState
while True:                       add_edge("tools", "agent")
llm_output = llm(prompt)          def call_model(state)
action = parse_action(text)       tools_condition (结构化)
obs = tool_func(args)             ToolNode
intermediate_steps.append()       add_messages reducer
if not action: break              有 tool_calls → tools, 否则 END
max_iterations 硬限制              Conditional Edge 控制

Human-in-the-loop❌               interrupt_before=["tools"] ✅
  while 循环里找不到插入点         编译时指定即可
""")