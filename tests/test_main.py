# tests/test_main.py
# FastAPI 接口测试
# 注意：模块级 patch 必须在 import main 之前执行
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from unittest.mock import patch, MagicMock

# ============================================================
# 【关键】模块级 patch：在 import main 之前 mock 掉 agent 编译
# 否则 main.py 的模块级代码会触发真实的 LangGraph 初始化
# ============================================================
_mock_build = patch("agent.graph.build_job_agent").start()
_mock_build.return_value = MagicMock()

import pytest

# 现在安全地 import main
from main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """提供 TestClient 实例"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_mock():
    """每个测试前重置 mock 行为"""
    agent = _mock_build.return_value
    agent.invoke.return_value = {
        "final_output": "分析完成",
        "jd_resume_analysis": "契合度分析报告",
        "interview_feedback": ["反馈1"],
        "similar_jds": [],
        "similar_questions": [],
        "token_usage": {"total_calls": 3, "total_tokens": 500, "estimated_cost_cny": 0.002},
        "__interrupt__": [],
    }
    yield


class TestMainAPI:

    def test_root(self, client):
        """GET / 返回 200"""
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data

    def test_chat_basic(self, client):
        """POST /chat 基本请求"""
        resp = client.post("/chat", json={
            "message": "帮我找前端工作",
            "resume": "5年React经验",
            "job_description": "招聘前端工程师",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "finished"
        assert "token_usage" in data

    def test_chat_no_jd(self, client):
        """POST /chat 无 JD 时正常返回"""
        resp = client.post("/chat", json={
            "message": "帮我分析",
            "resume": "5年经验",
            "job_description": "",
        })
        assert resp.status_code == 200

    @pytest.fixture
    def _setup_interrupt(self, client):
        """模拟 fit_review interrupt 场景"""
        agent = _mock_build.return_value
        mock_interrupt = MagicMock()
        mock_interrupt.value = {
            "type": "fit_review",
            "fit_analysis": "匹配度85%",
            "similar_jds": [],
            "similar_questions": [],
            "question": "是否继续面试？",
            "options": ["continue", "skip"],
        }
        agent.invoke.return_value = {"__interrupt__": [mock_interrupt]}
        return agent

    def test_chat_fit_review_interrupt(self, client):
        """POST /chat 返回 fit_review 中断"""
        agent = _mock_build.return_value
        mock_interrupt = MagicMock()
        mock_interrupt.value = {
            "type": "fit_review",
            "fit_analysis": "匹配度85%",
            "similar_jds": [],
            "similar_questions": [],
            "question": "是否继续面试？",
            "options": ["continue", "skip"],
        }
        agent.invoke.return_value = {"__interrupt__": [mock_interrupt]}

        resp = client.post("/chat", json={
            "message": "帮我分析",
            "resume": "5年经验",
            "job_description": "招聘JD",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "fit_review"
        assert "匹配度" in data["fit_analysis"]

    def test_chat_interviewing_interrupt(self, client):
        """POST /chat 返回 interviewing 中断"""
        agent = _mock_build.return_value
        mock_interrupt = MagicMock()
        mock_interrupt.value = {
            "type": "interview",
            "question": "请解释React的Fiber架构",
            "question_num": 1,
            "total": 5,
        }
        agent.invoke.return_value = {"__interrupt__": [mock_interrupt]}

        resp = client.post("/chat", json={
            "message": "开始面试",
            "resume": "5年React经验",
            "job_description": "招聘前端",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "interviewing"
        assert "Fiber" in data["question"]

    def test_upload_resume_invalid_type(self, client):
        """非 PDF 文件上传返回 400"""
        resp = client.post("/upload-resume", files={
            "file": ("test.txt", b"hello world", "text/plain")
        })
        assert resp.status_code == 400
        assert "仅支持 PDF" in resp.text

    def test_upload_resume_empty(self, client):
        """空文件上传返回 400"""
        resp = client.post("/upload-resume", files={
            "file": ("empty.pdf", b"", "application/pdf")
        })
        assert resp.status_code == 400

    def test_jd_history(self, client):
        """GET /jd-history 返回 200"""
        resp = client.get("/jd-history")
        assert resp.status_code == 200

    def test_vector_stats(self, client):
        """GET /vector-stats 返回 200"""
        resp = client.get("/vector-stats")
        assert resp.status_code == 200

    def test_question_history(self, client):
        """GET /question-history 返回 200"""
        resp = client.get("/question-history")
        assert resp.status_code == 200

    def test_chat_resume_from_interrupt(self, client):
        """带 answer 参数恢复中断"""
        agent = _mock_build.return_value
        agent.invoke.return_value = {
            "final_output": "面试结束",
            "jd_resume_analysis": None,
            "interview_feedback": ["反馈1"],
            "similar_jds": [],
            "similar_questions": [],
            "token_usage": {},
            "__interrupt__": [],
        }

        resp = client.post("/chat", json={
            "message": "",
            "answer": "我的回答是React的虚拟DOM...",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "finished"
