# tests/test_nodes.py
# Agent 节点单元测试
# 所有 LLM 调用用 unittest.mock 模拟，不依赖真实 API
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import json
from unittest.mock import patch, MagicMock, PropertyMock

from agent.nodes import (
    planner_node,
    executor_node,
    aggregator_node,
    fit_review_node,
    should_continue,
    should_continue_from_fit_review,
    should_continue_interview,
)


# ============================================================
# 辅助函数：构造测试状态
# ============================================================

def make_state(overrides=None):
    """构造最小化的 JobState 测试样本"""
    state = {
        "user_input": "帮我分析简历",
        "resume_text": "5年React经验，熟悉TypeScript",
        "job_description": "招聘高级前端工程师",
        "company": "字节跳动",
        "role": "高级前端开发工程师",
        "user_skills": ["React"],
        "target_role": "前端开发工程师",
        "target_location": "上海",
        "plan": [],
        "current_step": 0,
        "max_steps": 5,
        "similar_jds": [],
        "rag_context": "",
        "similar_questions": [],
        "jd_resume_analysis": None,
        "resume_advice": None,
        "interview_questions": [],
        "current_q_index": 0,
        "interview_feedback": [],
        "interview_complete": False,
        "pending_question": None,
        "skip_interview": False,
        "status": "planning",
        "error": None,
        "final_output": "",
        "token_usage": {},
        "conversation_history": [],
        "user_preferences": {},
    }
    if overrides:
        state.update(overrides)
    return state


# ============================================================
# 模拟 LLM 响应
# ============================================================

def mock_llm_response(content="mock content", prompt_tokens=100, completion_tokens=50):
    """创建模拟的 LLM invoke 返回值"""
    mock = MagicMock()
    mock.content = content
    mock.response_metadata = {
        "token_usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
    }
    return mock


MOCK_PLAN_JSON = json.dumps([
    {"step_id": 1, "action": "analyze_jd_resume_fit",
     "params": {"job_description": "JD", "resume_text": "resume"},
     "description": "JD-简历契合度分析"},
    {"step_id": 2, "action": "optimize_resume",
     "params": {"job_description": "JD"},
     "description": "简历优化"},
    {"step_id": 3, "action": "generate_questions",
     "params": {"job_title": "前端工程师", "company": "字节跳动"},
     "description": "生成面试题"},
])


# ============================================================
# Planner 节点测试
# ============================================================

class TestPlannerNode:

    @patch("agent.nodes.ChatDeepSeek")
    def test_planner_node_creates_plan(self, mock_deepseek):
        """Planner 正确生成执行计划"""
        instance = mock_deepseek.return_value
        instance.invoke.return_value = mock_llm_response(MOCK_PLAN_JSON)

        state = make_state()
        result = planner_node(state)

        assert result["status"] == "executing"
        assert len(result["plan"]) == 3
        assert result["plan"][0]["action"] == "analyze_jd_resume_fit"
        assert result["plan"][1]["action"] == "optimize_resume"
        assert result["plan"][2]["action"] == "generate_questions"
        assert result["current_step"] == 0

    @patch("agent.nodes.ChatDeepSeek")
    def test_planner_node_handles_rag_error(self, mock_deepseek):
        """RAG 检索失败不阻断规划"""
        instance = mock_deepseek.return_value
        instance.invoke.return_value = mock_llm_response(MOCK_PLAN_JSON)

        # 模拟 RAG 搜索失败
        with patch("agent.nodes.search_similar_jds", side_effect=Exception("RAG down")):
            state = make_state()
            result = planner_node(state)
            # 仍能生成 plan
            assert result["status"] == "executing"
            assert len(result["plan"]) > 0

    @patch("agent.nodes.ChatDeepSeek")
    def test_planner_node_invalid_llm_output(self, mock_deepseek):
        """LLM 返回非 JSON 时优雅降级"""
        instance = mock_deepseek.return_value
        instance.invoke.return_value = mock_llm_response("这不是JSON")

        state = make_state()
        result = planner_node(state)
        # 不会崩溃，标记为 error
        assert result["status"] == "error" or result.get("error") is not None


# ============================================================
# Executor 节点测试
# ============================================================

class TestExecutorNode:

    def test_executor_finished_when_no_plan(self):
        """没有 plan 时直接 finished"""
        state = make_state({"plan": [], "current_step": 0})
        result = executor_node(state)
        assert result["status"] == "finished"

    @patch("agent.nodes.ChatDeepSeek")
    def test_executor_analyze_jd(self, mock_deepseek):
        """analyze_jd_resume_fit 路径"""
        instance = mock_deepseek.return_value
        instance.invoke.return_value = mock_llm_response("分析报告内容")

        state = make_state({
            "plan": [{"step_id": 1, "action": "analyze_jd_resume_fit",
                      "params": {}, "description": "分析"}],
            "status": "executing",
        })
        result = executor_node(state)
        assert result["current_step"] == 1

    def test_executor_optimize(self):
        """optimize_resume 路径"""
        with patch("agent.nodes.optimize_resume", return_value="优化建议") as mock_opt:
            state = make_state({
                "plan": [{"step_id": 1, "action": "optimize_resume",
                          "params": {}, "description": "优化"}],
                "status": "executing",
            })
            result = executor_node(state)
            assert result["current_step"] == 1
            assert result["resume_advice"] == "优化建议"
            mock_opt.assert_called_once()

    def test_executor_generate_questions(self):
        """generate_questions 路径"""
        with patch("agent.nodes.ChatDeepSeek") as mock_ds:
            instance = mock_ds.return_value
            instance.invoke.return_value = mock_llm_response("1. 面试题1\n2. 面试题2")

            state = make_state({
                "plan": [{"step_id": 1, "action": "generate_questions",
                          "params": {}, "description": "出题"}],
                "status": "executing",
            })
            result = executor_node(state)
            assert result["current_step"] == 1

    def test_executor_unknown_action(self):
        """未知 action 不崩溃"""
        state = make_state({
            "plan": [{"step_id": 1, "action": "unknown_action",
                      "params": {}, "description": "未知"}],
            "status": "executing",
        })
        result = executor_node(state)
        assert result["current_step"] == 1
        assert result["plan"][0].get("error") is not None

    def test_executor_all_steps_done(self):
        """所有步骤执行完，status 变 finished"""
        state = make_state({
            "plan": [
                {"step_id": 1, "action": "analyze_jd_resume_fit",
                 "params": {}, "description": "分析"},
            ],
            "status": "executing",
            "current_step": 0,
        })
        with patch("agent.nodes.ChatDeepSeek") as mock_ds:
            instance = mock_ds.return_value
            instance.invoke.return_value = mock_llm_response("报告")
            result = executor_node(state)
            assert result["status"] == "finished"


# ============================================================
# Aggregator 节点测试
# ============================================================

class TestAggregatorNode:

    @patch("agent.nodes.ChatDeepSeek")
    def test_aggregator_fills_output(self, mock_deepseek):
        """Aggregator 正确生成最终报告"""
        instance = mock_deepseek.return_value
        instance.invoke.return_value = mock_llm_response("最终求职报告内容")

        state = make_state({
            "jd_resume_analysis": "分析结果",
            "resume_advice": "优化建议",
            "interview_questions": ["问题1", "问题2"],
            "status": "executing",
        })
        result = aggregator_node(state)
        assert result["status"] == "finished"
        assert "最终求职报告内容" in result["final_output"]


# ============================================================
# Fit Review 节点测试
# ============================================================

class TestFitReviewNode:

    def test_skip_when_no_jd(self):
        """无 JD 时跳过 interrupt"""
        state = make_state({"job_description": None, "resume_text": "resume"})
        result = fit_review_node(state)
        assert result["skip_interview"] is True

    def test_skip_when_no_resume(self):
        """无简历时跳过 interrupt"""
        state = make_state({"job_description": "JD", "resume_text": None})
        result = fit_review_node(state)
        assert result["skip_interview"] is True

    def test_skip_when_no_analysis(self):
        """无契合度分析时跳过 interrupt"""
        state = make_state({
            "job_description": "JD",
            "resume_text": "resume",
            "jd_resume_analysis": None,
        })
        result = fit_review_node(state)
        # 不加 interrupt，直接返回
        assert result is not None


# ============================================================
# Interviewer 节点测试
# ============================================================

class TestInterviewerNode:

    def test_interview_complete_returns_finish(self):
        """interview_complete=True → finish"""
        state = make_state({"interview_complete": True, "error": None})
        result = should_continue_interview(state)
        assert result == "finish"

    def test_skip_interview_flag(self):
        """should_continue_from_fit_review 正确路由"""
        state = make_state({"skip_interview": True})
        assert should_continue_from_fit_review(state) == "finish"

        state2 = make_state({"skip_interview": False, "error": None})
        assert should_continue_from_fit_review(state2) == "continue"


# ============================================================
# 条件路由测试
# ============================================================

class TestConditionalEdges:

    def test_should_continue_error(self):
        """错误状态 → error"""
        assert should_continue({"error": "出错啦", "status": "planning", "current_step": 0, "plan": []}) == "error"

    def test_should_continue_finish(self):
        """完成状态 → finish"""
        assert should_continue({"error": None, "status": "finished", "current_step": 2, "plan": [1, 2]}) == "finish"

    def test_should_continue_continue(self):
        """还有步骤 → continue"""
        assert should_continue({"error": None, "status": "executing", "current_step": 1, "plan": [1, 2, 3]}) == "continue"

    def test_should_continue_interview_finish(self):
        """面试完成 → finish"""
        assert should_continue_interview({"error": None, "interview_complete": True}) == "finish"

    def test_should_continue_interview_continue(self):
        """面试未完成 → continue"""
        assert should_continue_interview({"error": None, "interview_complete": False}) == "continue"

    def test_fit_review_skip(self):
        """跳过面试 → finish"""
        assert should_continue_from_fit_review({"skip_interview": True}) == "finish"

    def test_fit_review_continue(self):
        """继续面试 → continue"""
        assert should_continue_from_fit_review({"skip_interview": False, "error": None}) == "continue"
