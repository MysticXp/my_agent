# tests/conftest.py
# pytest 公共 fixture
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 修复 Windows GBK 编码问题
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import json
import pytest
from unittest.mock import patch, MagicMock
from typing import Dict, Any


# ============================================================
# 公共 Fixture
# ============================================================

@pytest.fixture
def mock_env():
    """模拟环境变量（避免真实 API Key 依赖）"""
    with patch.dict(os.environ, {
        "DEEPSEEK_API_KEY": "sk-test-fake-key",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
    }, clear=False):
        yield


@pytest.fixture
def mock_llm():
    """模拟 ChatDeepSeek 的 invoke 返回"""
    with patch("agent.nodes.ChatDeepSeek") as mock:
        instance = mock.return_value
        mock_response = MagicMock()
        mock_response.content = json.dumps([
            {"step_id": 1, "action": "analyze_jd_resume_fit",
             "params": {"job_description": "JD text", "resume_text": "resume text"},
             "description": "JD-简历契合度分析"}
        ])
        mock_response.response_metadata = {
            "token_usage": {"prompt_tokens": 100, "completion_tokens": 50}
        }
        instance.invoke.return_value = mock_response
        yield instance


@pytest.fixture
def mock_agent_llm():
    """模拟 agent.agents 中 ChatDeepSeek 的 invoke"""
    with patch("agent.agents.base_agent.ChatDeepSeek") as mock:
        instance = mock.return_value
        mock_response = MagicMock()
        mock_response.content = "模拟的 LLM 输出内容"
        mock_response.response_metadata = {
            "token_usage": {"prompt_tokens": 50, "completion_tokens": 30}
        }
        instance.invoke.return_value = mock_response
        yield instance


@pytest.fixture
def sample_state() -> Dict[str, Any]:
    """通用的测试状态样本"""
    return {
        "user_input": "帮我找前端工作",
        "resume_text": "5年React经验，熟悉TypeScript",
        "job_description": "招聘高级前端工程师，要求React、TypeScript",
        "company": "字节跳动",
        "role": "高级前端开发工程师",
        "user_skills": ["React", "TypeScript", "Python"],
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
        "conversation_history": [
            {"role": "user", "content": "帮我找前端工作"}
        ],
        "user_preferences": {},
    }
