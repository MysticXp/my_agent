# tests/test_state.py
# 状态管理单元测试
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.state import create_initial_state, state_summary, update_state_with_preferences


def test_create_initial_state_defaults():
    """所有字段默认值正确"""
    state = create_initial_state(user_input="帮我找工作")

    assert state["user_input"] == "帮我找工作"
    assert state["resume_text"] is None
    assert state["job_description"] is None
    assert state["company"] is None
    assert state["role"] is None
    assert state["user_skills"] == []
    assert state["target_role"] == ""
    assert state["target_location"] == ""
    assert state["plan"] == []
    assert state["current_step"] == 0
    assert state["max_steps"] == 5
    assert state["status"] == "planning"
    assert state["error"] is None
    assert state["final_output"] == ""
    assert state["skip_interview"] is False
    assert state["interview_complete"] is False
    assert state["token_usage"] == {}
    assert len(state["conversation_history"]) == 1
    assert state["conversation_history"][0]["role"] == "user"


def test_create_initial_state_with_resume():
    """带简历和 JD 时正确填充"""
    state = create_initial_state(
        user_input="分析简历",
        resume="5年Python经验",
        job_description="招聘Python后端",
        company="腾讯",
        role="后端开发",
    )
    assert state["resume_text"] == "5年Python经验"
    assert state["job_description"] == "招聘Python后端"
    assert state["company"] == "腾讯"
    assert state["role"] == "后端开发"


def test_state_summary():
    """生成摘要不含异常"""
    state = create_initial_state(user_input="帮我找前端工作")
    summary = state_summary(state)
    assert "状态摘要" in summary
    assert "前端" in summary


def test_state_summary_long_input():
    """长输入不截断出错"""
    state = create_initial_state(user_input="X" * 100)
    summary = state_summary(state)
    assert summary is not None


def test_update_preferences():
    """偏好更新正确"""
    state = create_initial_state(user_input="测试")
    assert state["user_preferences"] == {}

    updated = update_state_with_preferences(state, {"min_salary": 50000})
    assert updated["user_preferences"]["min_salary"] == 50000

    # 再追加
    update_state_with_preferences(state, {"target_city": "北京"})
    assert state["user_preferences"]["min_salary"] == 50000
    assert state["user_preferences"]["target_city"] == "北京"


def test_max_steps_limit():
    """max_steps 默认 5"""
    state = create_initial_state(user_input="测试")
    assert state["max_steps"] == 5
