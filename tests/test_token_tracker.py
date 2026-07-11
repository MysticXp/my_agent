# tests/test_token_tracker.py
# Token 追踪系统单元测试
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import json
import tempfile
from agent.token_tracker import TokenTracker, MODEL_PRICING


class MockResponse:
    """模拟 LangChain LLM 响应"""
    def __init__(self, prompt_tokens=100, completion_tokens=50):
        self.response_metadata = {
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
        }


class TestTokenTracker:
    def setup_method(self):
        """每个测试前清空 tracker 状态"""
        self.tracker = TokenTracker()
        self.tracker.clear()

    def test_singleton(self):
        """多次实例化返回同一对象"""
        t1 = TokenTracker()
        t2 = TokenTracker()
        assert t1 is t2

    def test_track(self):
        """记录 token 用量，成本计算正确"""
        resp = MockResponse(prompt_tokens=200, completion_tokens=100)
        self.tracker.track(resp, agent_name="TestAgent")
        summary = self.tracker.summary()
        assert summary["total_calls"] == 1
        assert summary["input_tokens"] == 200
        assert summary["output_tokens"] == 100
        assert summary["total_tokens"] == 300
        assert summary["estimated_cost_cny"] > 0

    def test_summary_empty(self):
        """无记录时返回 0"""
        summary = self.tracker.summary()
        assert summary["total_calls"] == 0
        assert summary["total_tokens"] == 0
        assert summary["estimated_cost_cny"] == 0.0

    def test_summary_with_data(self):
        """多 Agent 调用，按 Agent 分组统计正确"""
        self.tracker.track(MockResponse(prompt_tokens=100, completion_tokens=50), agent_name="AgentA")
        self.tracker.track(MockResponse(prompt_tokens=200, completion_tokens=100), agent_name="AgentA")
        self.tracker.track(MockResponse(prompt_tokens=50, completion_tokens=25), agent_name="AgentB")

        summary = self.tracker.summary()
        assert summary["total_calls"] == 3
        assert len(summary["agent_breakdown"]) == 2
        assert summary["agent_breakdown"]["AgentA"]["calls"] == 2
        assert summary["agent_breakdown"]["AgentB"]["calls"] == 1
        assert summary["agent_breakdown"]["AgentA"]["total_tokens"] == 300 + 150

    def test_pricing(self):
        """定价计算正确"""
        resp = MockResponse(prompt_tokens=1000, completion_tokens=500)
        self.tracker.track(resp, agent_name="PricingTest")
        expected = (1000 / 1000 * 0.0005) + (500 / 1000 * 0.002)
        summary = self.tracker.summary()
        assert abs(summary["estimated_cost_cny"] - expected) < 0.0001

    def test_no_token_data(self):
        """没有 token 数据时 graceful fallback"""
        class NoTokenResponse:
            response_metadata = {}
        self.tracker.track(NoTokenResponse(), agent_name="NoToken")
        summary = self.tracker.summary()
        assert summary["total_calls"] == 1
        assert summary["total_tokens"] == 0

    def test_raw_tracking(self):
        """直接记录（不用 response 对象）"""
        self.tracker.track_raw(prompt_tokens=500, completion_tokens=300, agent_name="RawAgent")
        summary = self.tracker.summary()
        assert summary["total_tokens"] == 800
        assert summary["agent_breakdown"]["RawAgent"]["calls"] == 1

    def test_formatted_summary(self):
        """生成人类可读报告"""
        self.tracker.track(MockResponse(prompt_tokens=200, completion_tokens=100), agent_name="AgentA")
        formatted = self.tracker.get_formatted_summary()
        assert "AgentA" in formatted
        assert "tokens" in formatted.lower()
        assert "¥" in formatted

    def test_save_to_file(self):
        """写入 JSONL 文件格式正确"""
        self.tracker.track(MockResponse(prompt_tokens=100, completion_tokens=50), agent_name="SaveTest")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
            self.tracker.save_to_file(f.name)
            with open(f.name, encoding="utf-8") as f_read:
                lines = f_read.readlines()
            assert len(lines) == 1
            entry = json.loads(lines[0])
            assert entry["agent"] == "SaveTest"
            assert entry["prompt_tokens"] == 100
            assert entry["completion_tokens"] == 50
            assert "cost_cny" in entry
            assert "timestamp" in entry
