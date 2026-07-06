# agent/graph.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agent.state import JobState
from agent.nodes import (
    interviewer_node, planner_node, executor_node, aggregator_node,
    fit_review_node,
    should_continue, should_continue_from_fit_review,
    should_continue_interview
)


def build_job_agent():
    """构建并编译LangGraph状态图（带记忆，支持 interrupt 暂停/恢复）

    流程：
    planner → executor ⟲ (循环执行工具：契合度分析 → 简历优化 → 生成面试题)
                  ↓ (全部完成)
            fit_review  ← 展示契合度分析，用户决定是否继续面试
              ├─ continue: interviewer ⟲ (逐题问答，interrupt 暂停等用户回答)
              │                 ↓ (面试结束)
              └─ skip: ────→ aggregator → END
    """
    workflow = StateGraph(JobState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("fit_review", fit_review_node)
    workflow.add_node("aggregator", aggregator_node)
    workflow.add_node("interviewer", interviewer_node)

    workflow.set_entry_point("planner")
    workflow.add_edge("planner", "executor")

    # executor 循环完成后 → fit_review
    workflow.add_conditional_edges(
        "executor",
        should_continue,
        {
            "continue": "executor",
            "finish": "fit_review",
            "error": END
        }
    )

    # fit_review → 用户选择：继续面试 or 跳过
    workflow.add_conditional_edges(
        "fit_review",
        should_continue_from_fit_review,
        {
            "continue": "interviewer",
            "finish": "aggregator",
            "error": END
        }
    )

    workflow.add_conditional_edges(
        "interviewer",
        should_continue_interview,
        {
            "continue": "interviewer",
            "finish": "aggregator",
            "error": END
        }
    )

    workflow.add_edge("aggregator", END)

    # 关键：带 checkpointer 编译，interrupt() 才能正常工作
    return workflow.compile(checkpointer=MemorySaver())
