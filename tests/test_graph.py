# tests/test_graph.py
# LangGraph 工作流测试
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from unittest.mock import patch, MagicMock

from agent.graph import build_job_agent
from agent.nodes import (
    should_continue,
    should_continue_from_fit_review,
    should_continue_interview,
)
from agent.state import JobState


# ============================================================
# Graph 编译测试
# ============================================================

class TestBuildGraph:

    @patch("agent.graph.MemorySaver")
    @patch("agent.graph.StateGraph")
    def test_build_graph_compiles(self, mock_state_graph, mock_memory):
        """build_job_agent() 能正常编译"""
        mock_graph = MagicMock()
        mock_state_graph.return_value = mock_graph
        mock_graph.compile.return_value = "compiled_graph"

        result = build_job_agent()
        assert result == "compiled_graph"
        mock_graph.compile.assert_called_once()

    @patch("agent.graph.MemorySaver")
    @patch("agent.graph.StateGraph")
    def test_build_graph_adds_all_nodes(self, mock_state_graph, mock_memory):
        """验证 5 个核心节点都被添加"""
        mock_graph = MagicMock()
        mock_state_graph.return_value = mock_graph

        build_job_agent()

        # 验证节点被添加
        assert mock_graph.add_node.call_count >= 5
        node_names = [call[0][0] for call in mock_graph.add_node.call_args_list]
        assert "planner" in node_names
        assert "executor" in node_names
        assert "fit_review" in node_names
        assert "interviewer" in node_names
        assert "aggregator" in node_names

    @patch("agent.graph.MemorySaver")
    @patch("agent.graph.StateGraph")
    def test_build_graph_entry_point(self, mock_state_graph, mock_memory):
        """起始节点为 planner"""
        mock_graph = MagicMock()
        mock_state_graph.return_value = mock_graph

        build_job_agent()
        mock_graph.set_entry_point.assert_called_with("planner")


# ============================================================
# 条件路由测试
# ============================================================

class TestEdges:

    def test_should_continue_error(self):
        """错误状态 → 终止"""
        result = should_continue({"error": "fail", "status": "executing", "current_step": 0, "plan": []})
        assert result == "error"

    def test_should_continue_finished(self):
        """完成状态 → finish"""
        result = should_continue({"error": None, "status": "finished", "current_step": 3, "plan": [1, 2, 3]})
        assert result == "finish"

    def test_should_continue_steps_left(self):
        """还有步骤 → continue"""
        result = should_continue({"error": None, "status": "executing", "current_step": 1, "plan": [1, 2, 3]})
        assert result == "continue"

    def test_fit_review_skip(self):
        """跳过面试 → finish (去 aggregator)"""
        result = should_continue_from_fit_review({"skip_interview": True, "error": None})
        assert result == "finish"

    def test_fit_review_continue(self):
        """继续面试 → continue (去 interviewer)"""
        result = should_continue_from_fit_review({"skip_interview": False, "error": None})
        assert result == "continue"

    def test_fit_review_error(self):
        """错误 → error"""
        result = should_continue_from_fit_review({"skip_interview": False, "error": "err"})
        assert result == "error"

    def test_interview_complete(self):
        """面试完成 → finish"""
        result = should_continue_interview({"interview_complete": True, "error": None})
        assert result == "finish"

    def test_interview_not_complete(self):
        """面试未完成 → continue"""
        result = should_continue_interview({"interview_complete": False, "error": None})
        assert result == "continue"

    def test_interview_error(self):
        """面试错误 → error"""
        result = should_continue_interview({"interview_complete": False, "error": "err"})
        assert result == "error"
