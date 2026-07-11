# tests/test_token_tracker.py
import sys, os
os.environ['PYTHONIOENCODING'] = 'utf-8'

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.token_tracker import TokenTracker, MODEL_PRICING


class MockResponse:
    def __init__(self, prompt_tokens=100, completion_tokens=50):
        self.response_metadata = {
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
        }


def test_basic_tracking():
    tracker = TokenTracker()
    tracker.clear()
    resp = MockResponse(prompt_tokens=200, completion_tokens=100)
    tracker.track(resp, agent_name="TestAgent")
    summary = tracker.summary()
    assert summary["total_calls"] == 1
    assert summary["input_tokens"] == 200
    assert summary["output_tokens"] == 100
    assert summary["total_tokens"] == 300
    assert summary["estimated_cost_cny"] > 0
    print("  [PASS] test_basic_tracking")


def test_multiple_agents():
    tracker = TokenTracker()
    tracker.clear()
    tracker.track(MockResponse(prompt_tokens=100, completion_tokens=50), agent_name="AgentA")
    tracker.track(MockResponse(prompt_tokens=200, completion_tokens=100), agent_name="AgentB")
    summary = tracker.summary()
    assert summary["total_calls"] == 2
    assert len(summary["agent_breakdown"]) == 2
    assert summary["agent_breakdown"]["AgentA"]["calls"] == 1
    assert summary["agent_breakdown"]["AgentB"]["calls"] == 1
    print("  [PASS] test_multiple_agents")


def test_empty_tracker():
    tracker = TokenTracker()
    tracker.clear()
    summary = tracker.summary()
    assert summary["total_calls"] == 0
    assert summary["estimated_cost_cny"] == 0.0
    print("  [PASS] test_empty_tracker")


def test_pricing():
    tracker = TokenTracker()
    tracker.clear()
    resp = MockResponse(prompt_tokens=1000, completion_tokens=500)
    tracker.track(resp, agent_name="PricingTest")
    expected = (1000/1000 * 0.0005) + (500/1000 * 0.002)
    summary = tracker.summary()
    assert abs(summary["estimated_cost_cny"] - expected) < 0.0001
    print(f"  [PASS] test_pricing (expected={expected:.6f})")


def test_no_token_data():
    tracker = TokenTracker()
    tracker.clear()
    class NoTokenResponse:
        response_metadata = {}
    tracker.track(NoTokenResponse(), agent_name="NoToken")
    summary = tracker.summary()
    assert summary["total_calls"] == 1
    assert summary["total_tokens"] == 0
    print("  [PASS] test_no_token_data (graceful fallback)")


def test_raw_tracking():
    tracker = TokenTracker()
    tracker.clear()
    tracker.track_raw(prompt_tokens=500, completion_tokens=300, agent_name="RawAgent")
    summary = tracker.summary()
    assert summary["total_tokens"] == 800
    assert summary["agent_breakdown"]["RawAgent"]["calls"] == 1
    print("  [PASS] test_raw_tracking")


def test_formatted_summary():
    tracker = TokenTracker()
    tracker.clear()
    tracker.track(MockResponse(prompt_tokens=200, completion_tokens=100), agent_name="AgentA")
    formatted = tracker.get_formatted_summary()
    assert "AgentA" in formatted
    assert "tokens" in formatted.lower()
    print("  [PASS] test_formatted_summary")


if __name__ == "__main__":
    print("Running Token Tracker tests...\n")
    test_empty_tracker()
    test_basic_tracking()
    test_multiple_agents()
    test_pricing()
    test_no_token_data()
    test_raw_tracking()
    test_formatted_summary()
    print(f"\n--- All 7 tests passed! ---")
    print(f"(DeepSeek pricing: input=CNY {MODEL_PRICING['deepseek-chat']['input']}/K, output=CNY {MODEL_PRICING['deepseek-chat']['output']}/K)")
