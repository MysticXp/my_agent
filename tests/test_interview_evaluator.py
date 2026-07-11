# tests/test_interview_evaluator.py
# InterviewEvaluatorAgent 的解析逻辑测试（不依赖 API Key）
import sys, os
os.environ['PYTHONIOENCODING'] = 'utf-8'

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.agents.interview_evaluator import InterviewEvaluatorAgent


def test_parse_score():
    """测试从评估文本中提取分数"""
    agent = InterviewEvaluatorAgent()

    text = """
综合评分: 7.5

技术准确性: 8
逻辑结构: 7
深度与见解: 6
    """
    assert agent._parse_score(text, "综合评分") == 7.5
    assert agent._parse_score(text, "技术准确性") == 8
    assert agent._parse_score(text, "逻辑结构") == 7
    assert agent._parse_score(text, "深度与见解") == 6
    print("  [PASS] test_parse_score")


def test_parse_score_not_found():
    """测试未找到分数时的 fallback"""
    agent = InterviewEvaluatorAgent()
    assert agent._parse_score("no score here", "综合评分") == 0.0
    print("  [PASS] test_parse_score_not_found")


def test_parse_list():
    """测试提取列表项"""
    agent = InterviewEvaluatorAgent()

    text = """
优点:
- 回答结构清晰，使用了STAR原则
- 技术概念理解准确
- 展示了实际项目经验

改进建议:
- 可以增加对性能优化的讨论
- 建议补充具体的量化指标
    """
    strengths = agent._parse_list(text, "优点")
    assert len(strengths) == 3
    assert "STAR" in strengths[0]

    suggestions = agent._parse_list(text, "改进建议")
    assert len(suggestions) == 2
    assert "性能" in suggestions[0]
    print("  [PASS] test_parse_list")


def test_parse_list_not_found():
    """测试未找到列表时的 fallback"""
    agent = InterviewEvaluatorAgent()
    items = agent._parse_list("no list here", "优点")
    assert items == []
    print("  [PASS] test_parse_list_not_found")


if __name__ == "__main__":
    print("Running InterviewEvaluator parsing tests...\n")
    test_parse_score()
    test_parse_score_not_found()
    test_parse_list()
    test_parse_list_not_found()
    print("\n--- All 4 tests passed! ---")
