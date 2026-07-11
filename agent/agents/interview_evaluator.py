# agent/agents/interview_evaluator.py
# InterviewEvaluatorAgent — 面试回答评估专用 Agent
#
# 面试话术：
# "面试者回答完问题后，InterviewEvaluator 会从 4 个维度评估答案质量：
#  技术准确性、逻辑结构、表达清晰度、改进空间。
#  它和 QuestionGenerator 是两个独立 Agent，一个负责出题一个负责评分，
#  职责分离让每个 Agent 的 prompt 更聚焦。"
#
# 面试考点：
# - 评估 Agent 的 temperature 居中 (0.4)：需要判断力但不要过于随机
# - 评估维度设计体现了对面试流程的理解

from typing import Any

from agent.agents.base_agent import BaseAgent
from agent.state import JobState


class InterviewEvaluatorAgent(BaseAgent):
    """面试回答评估 Agent

    职责:
        评估候选人对面试题的回答，从以下维度打分：
        1. 技术准确性 (35%) — 答案是否正确
        2. 逻辑结构 (25%) — 回答是否有条理
        3. 深度与见解 (25%) — 是否展示了深入理解
        4. 改进建议 (15%) — 具体可操作的改进方向

    特点:
        - 中等 temperature (0.4)：需要判断力但不要过于随机
        - 结构化输出，便于前端展示
        - 支持后续自动汇总面试报告
    """

    def __init__(self):
        super().__init__(
            name="InterviewEvaluator",
            temperature=0.4,  # 中等温度：需要判断力但不要过于随机
        )

    def evaluate(
        self,
        question: str,
        answer: str,
        question_type: str = "技术",
        context: str = "",
    ) -> dict:
        """评估单个面试回答

        参数:
            question: 面试题
            answer: 候选人的回答
            question_type: 题型（技术/设计/行为）
            context: 额外上下文（如 JD 要求、简历信息）

        返回:
            {
                "score": 7.5,           # 综合评分 (满分10)
                "accuracy": 8,           # 技术准确性
                "structure": 7,          # 逻辑结构
                "depth": 7,              # 深度与见解
                "suggestion": "...",      # 改进建议
                "strengths": [...],       # 优点列表
                "weaknesses": [...]       # 缺点列表
            }
        """
        prompt = f"""你是一位资深技术面试官，正在评估候选人的面试回答。

=== 题目类型 ===
{question_type}

=== 面试题 ===
{question}

=== 候选人的回答 ===
{answer}

{context}

=== 评估要求 ===
请从以下 4 个维度评估候选人的回答，并给出综合评分（满分 10 分）：

1. **技术准确性** (权重 35%)
   - 回答中的技术概念是否正确？
   - 如果有错误或不准确之处，请明确指出

2. **逻辑结构** (权重 25%)
   - 回答是否有清晰的逻辑层次（如总-分-总）？
   - 是否使用了 STAR 或其他结构化方法？

3. **深度与见解** (权重 25%)
   - 回答是否停留在表面，还是展现了深入的理解？
   - 有没有提到权衡、取舍、踩坑经验等有价值的点？

4. **改进建议** (权重 15%)
   - 给出 1-2 条具体可操作的改进建议

=== 输出格式 ===
综合评分: <0-10 的分数>

技术准确性: <0-10 的分数>
逻辑结构: <0-10 的分数>
深度与见解: <0-10 的分数>

优点:
- <优点1>
- <优点2>
- <优点3>

改进建议:
- <建议1>
- <建议2>

注意：评分要客观，不要虚高。好的回答 7-8 分，优秀的 9 分以上。"""

        response = self._call_llm(prompt)
        content = response.content

        # 解析评分
        score = self._parse_score(content, "综合评分")
        accuracy = self._parse_score(content, "技术准确性")
        structure = self._parse_score(content, "逻辑结构")
        depth = self._parse_score(content, "深度与见解")

        # 解析优缺点
        strengths = self._parse_list(content, "优点")
        suggestions = self._parse_list(content, "改进建议")

        return {
            "score": score,
            "accuracy": accuracy,
            "structure": structure,
            "depth": depth,
            "suggestion": suggestions[0] if suggestions else "",
            "strengths": strengths,
            "weaknesses": [],  # 从改进建议反推
            "raw_feedback": content,
        }

    def run(self, state: JobState, **kwargs) -> JobState:
        """批量评估所有已回答的问题（如果需要）

        在 interviewer_node 中逐题评估时，直接调用 evaluate() 方法。
        此 run() 主要用于汇总评估。
        """
        # 目前 interviewer_node 逐题调用 evaluate()
        # run() 保留用于后续批量评估场景
        return state

    def _parse_score(self, content: str, label: str) -> float:
        """从评估文本中提取分数"""
        import re
        # 匹配 "技术准确性: 8" 或 "综合评分: 7.5" 等
        pattern = rf"{re.escape(label)}:\s*(\d+(?:\.\d+)?)"
        match = re.search(pattern, content)
        if match:
            return float(match.group(1))
        return 0.0

    def _parse_list(self, content: str, section: str) -> list:
        """从评估文本中提取列表项"""
        import re
        items = []
        # 找到 section 所在区域
        pattern = rf"{re.escape(section)}:(.*?)(?=\n\n|\Z)"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            block = match.group(1)
            # 提取所有以 - 开头的行
            items = re.findall(r"-\s*(.+)", block)
        return items
