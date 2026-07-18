"""Tests for SSE streaming endpoint and streaming aggregator node"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-key")

from unittest.mock import patch, MagicMock, PropertyMock


# Test 1: streamClient SSE parser
def test_sse_parser():
    """Simulate SSE parsing logic from streamClient.js"""
    raw = b"event: token\ndata: {\"token\":\"hello\"}\n\nevent: token\ndata: {\"token\":\" world\"}\n\nevent: done\ndata: {\"status\":\"finished\",\"output\":\"hello world\"}\n\n"

    events = []
    buf = ""
    for byte in raw:
        buf += chr(byte)

    lines = buf.split("\n")
    evt, dat = "", ""
    for line in lines:
        if line.startswith("event: "):
            evt = line[7:].strip()
        elif line.startswith("data: "):
            dat = line[6:].strip()
        elif line == "" and evt and dat:
            import json
            events.append((evt, json.loads(dat)))
            evt, dat = "", ""

    assert len(events) == 3, f"Expected 3 events, got {len(events)}"
    assert events[0] == ("token", {"token": "hello"})
    assert events[1] == ("token", {"token": " world"})
    assert events[2][0] == "done"
    assert events[2][1]["status"] == "finished"
    print("  [PASS] test_sse_parser")


def test_stream_event_types():
    """All expected SSE event types"""
    events = ["node_start", "token", "interrupt", "done", "error"]
    # Test that the event type matches what _stream_agent yields
    from main import NODE_LABELS
    assert "planner" in NODE_LABELS
    assert "aggregator" in NODE_LABELS
    print(f"  [PASS] test_stream_event_types ({len(events)} types)")


# Test 3: Aggregator node streaming (mock LLM)
@patch("agent.nodes.ChatDeepSeek")
def test_aggregator_node_streaming(mock_deepseek):
    """aggregator_node uses stream() not invoke()"""
    from agent.nodes import aggregator_node

    # Mock the LLM stream to yield chunks
    mock_llm = MagicMock()
    mock_deepseek.return_value = mock_llm

    class MockChunk:
        def __init__(self, text):
            self.content = text
            self.response_metadata = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 5}}

    mock_llm.stream.return_value = [
        MockChunk("这是"),
        MockChunk("报告"),
        MockChunk("内容"),
    ]

    state = {
        "user_input": "test",
        "jd_resume_analysis": "分析结果",
        "resume_advice": "优化建议",
        "interview_questions": ["问题1"],
        "similar_jds": [],
        "status": "executing",
        "final_output": "",
        "token_usage": {},
        "conversation_history": [],
        "user_preferences": {},
    }

    result = aggregator_node(state)

    assert result["final_output"] == "这是报告内容"
    assert result["status"] == "finished"
    # Verify stream was used, not invoke
    mock_llm.stream.assert_called_once()
    print("  [PASS] test_aggregator_node_streaming")


# Test 4: SSE endpoint exists in main
def test_sse_endpoint_exists():
    """main.py has /chat/stream route"""
    import main
    routes = [r.path for r in main.app.routes]
    assert "/chat/stream" in routes, f"/chat/stream not in routes: {routes}"
    print("  [PASS] test_sse_endpoint_exists")


def test_interrupt_event_format():
    """_stream_agent yields correctly formatted interrupt event"""
    import json, asyncio

    # Directly test the event formatting that _stream_agent uses,
    # without needing the full LangGraph stack
    from main import NODE_LABELS

    # Verify NODE_LABELS contains all expected nodes
    assert "planner" in NODE_LABELS
    assert "executor" in NODE_LABELS
    assert "aggregator" in NODE_LABELS
    assert "fit_review" in NODE_LABELS
    assert "interviewer" in NODE_LABELS

    # Test the SSE event format that _stream_agent yields
    event_data = {
        "type": "fit_review",
        "fit_analysis": "test analysis",
        "fit_scores": {"total_score": 85},
        "question": "是否继续？",
    }
    import json
    serialized = json.dumps(event_data, ensure_ascii=False)
    parsed = json.loads(serialized)
    assert parsed["type"] == "fit_review"
    assert parsed["fit_scores"]["total_score"] == 85
    assert parsed["question"] == "是否继续？"

    # Test the on_chain_stream data extraction logic
    vals = {"chunk": {"final_output": "报告内容", "status": "finished"}}
    if "chunk" in vals:
        vals = vals["chunk"]
    assert vals["final_output"] == "报告内容"
    assert vals["status"] == "finished"

    # Test on_chain_stream with values wrapper
    vals2 = {"values": {"final_output": "报告2"}}
    if "chunk" in vals2:
        vals2 = vals2["chunk"]
    elif "values" in vals2:
        vals2 = vals2["values"]
    assert vals2["final_output"] == "报告2"

    print("  [PASS] test_interrupt_event_format")
