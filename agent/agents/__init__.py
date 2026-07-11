# agent/agents/__init__.py
# Multi-Agent 架构核心包
#
# 面试话术：
# "我把单 Agent 拆成了多个专用 Agent，每个只做一件事：
#  ResumeAnalyzer 只看 JD-简历匹配，QuestionGenerator 只出面试题，
#  InterviewEvaluator 只评分答案。职责单一、可独立测试、
#  每个 Agent 自己的 context window 只需要处理相关数据，
#  既降低了成本又提高了准确率。"
#
# 架构图：
#   Supervisor Agent (planner + router)
#       ├── ResumeAnalyzerAgent (JD-简历契合度分析)
#       ├── QuestionGeneratorAgent (生成面试题)
#       └── InterviewEvaluatorAgent (评估回答 + 评分)

from agent.agents.base_agent import BaseAgent
from agent.agents.resume_analyzer import ResumeAnalyzerAgent
from agent.agents.question_generator import QuestionGeneratorAgent
from agent.agents.interview_evaluator import InterviewEvaluatorAgent

__all__ = [
    "BaseAgent",
    "ResumeAnalyzerAgent",
    "QuestionGeneratorAgent",
    "InterviewEvaluatorAgent",
]
