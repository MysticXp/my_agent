# agent/agents/question_generator.py
# QuestionGeneratorAgent — 面试题生成专用 Agent
#

from typing import Any

from agent.agents.base_agent import BaseAgent
from agent.state import JobState

from tools.interview import generate_interview_questions
from tools.question_store import save_questions, get_questions, build_avoid_context, get_all_roles

class QuestionGeneratorAgent(BaseAgent):
    """面试题生成 Agent

    职责:
        1. 根据 JD + 简历生成针对性面试题
        2. 查询历史题库做避重
        3. 保存新生成的题目到题库

    特点:
        - 高 temperature (0.7)：出题需要多样性
        - 集成历史避重逻辑 (RAG 模式)
    """

    def __init__(self):
        super().__init__(
            name="QuestionGenerator",
            temperature=0.7,  # 高温度：出题需要多样性
        )

    def run(self, state: JobState, **kwargs) -> JobState:
        """生成面试题

        参数:
            state: 当前状态
            **kwargs: 可覆盖参数

        返回:
            更新后的 state（interview_questions 字段填充）
        """
        # 提取参数
        role = (
            kwargs.get("role")
            or state.get("role")
            or state.get("target_role")
            or "开发工程师"
        )
        company = (
            kwargs.get("company")
            or state.get("company")
            or "目标公司"
        )

        # 构建避重上下文
        avoid_ctx = build_avoid_context(role=role, company=company)

        print(f"[{self.name}] 正在为 {company} - {role} 生成面试题...")

        # 生成面试题（注入自己的 LLM 实现 token 追踪）
        questions = generate_interview_questions(
            job_title=role,
            company=company,
            skills=state.get("user_skills", []),
            jd_text=state.get("job_description", ""),
            resume_text=state.get("resume_text", ""),
            avoid_context=avoid_ctx,
            llm=self._get_llm(),  # 注入 agent 自己的 LLM
        )
        state["interview_questions"] = questions

        print(f"[{self.name}] 生成 {len(questions)} 道面试题")

        # 保存到历史库
        if questions:
            try:
                save_questions(
                    role=role,
                    questions=questions,
                    company=company,
                )
                print(f"[{self.name}] 已保存到历史库")
            except Exception as e:
                print(f"[{self.name}] 保存失败（非致命）: {e}")

        return state
