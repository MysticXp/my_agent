# agent/agents/resume_analyzer.py
# ResumeAnalyzerAgent — JD-简历契合度分析专用 Agent

from typing import Any

from agent.agents.base_agent import BaseAgent
from agent.state import JobState

from tools.jd_resume_analyzer import (
    analyze_jd_resume_fit,
    extract_match_score,
)
from tools.jd_retriever import search_similar_jds, build_rag_context
from tools.jd_store import save_jd
from tools.cache import get_cache

class ResumeAnalyzerAgent(BaseAgent):
    """JD-简历契合度分析 Agent

    职责:
        1. 检索相似历史 JD（RAG）
        2. 深度分析 JD 与简历的匹配度
        3. 提取结构化评分
        4. 自动保存 JD 到历史库

    特点:
        - 低 temperature (0.2)：分析任务需要一致性
          面试官问"为什么设 0.2" → "分析报告需要客观可复现"
    """

    def __init__(self):
        super().__init__(
            name="ResumeAnalyzer",
            temperature=0.2,  # 低温度：分析任务需要确定性
        )

    def run(self, state: JobState, **kwargs) -> JobState:
        """执行 JD-简历契合度分析

        参数:
            state: 当前状态（需包含 job_description 和 resume_text）
            **kwargs: 可覆盖 jd 和 resume

        返回:
            更新后的 state（jd_resume_analysis 字段填充）
        """
        # 优先用 plan params 中的值，没有则从 state 取（原代码的兜底逻辑）
        jd = kwargs.get("job_description") or state.get("job_description", "")
        resume = kwargs.get("resume_text") or state.get("resume_text", "")

        if not jd or not resume:
            print(f"[{self.name}] 缺少 JD 或简历，跳过分析")
            # 不设置 jd_resume_analysis，让 fit_review_node 判断后跳过
            return state

        print(f"[{self.name}] 开始分析 JD-简历契合度 (JD长度={len(jd)}, 简历长度={len(resume)})")

        # === RAG 检索：仅当用户没提供 JD 才用 RAG（用户给了 JD 就以它为准） ===
        if not state.get("job_description"):
            try:
                similar = search_similar_jds(jd, top_k=3)
                state["similar_jds"] = similar
                state["rag_context"] = build_rag_context(similar)
            except Exception as e:
                print(f"[{self.name}] RAG 检索失败（非致命）: {e}")
                state["similar_jds"] = state.get("similar_jds", [])
                state["rag_context"] = ""

        # === 语义缓存：相同的 JD+简历组合不重复调 LLM ===
        cache = get_cache()
        cached = cache.lookup(jd, resume)
        if cached:
            print(f"[{self.name}] 缓存命中 (相似度={cached['similarity']}), 跳过 LLM 调用")
            state["jd_resume_analysis"] = cached["result"]
        else:
            # === 执行分析（核心逻辑） ===
            try:
                result = analyze_jd_resume_fit(
                    job_description=jd,
                    resume_text=resume,
                    llm=self._get_llm(),
                )
                state["jd_resume_analysis"] = result
                print(f"[{self.name}] 分析完成: {len(result)} 字符")
                # 缓存结果
                cache.store(jd, resume, result, agent=self.name)
            except Exception as e:
                print(f"[{self.name}] 分析失败: {e}")
                state["jd_resume_analysis"] = f"（契合度分析暂不可用: {e}）"

        # === 保存 JD 到历史库：仅当用户提供了 JD 且库中没有重复 ===
        if state.get("jd_resume_analysis") and state.get("job_description"):
            try:
                save_jd(
                    jd_text=state["job_description"],
                    company=state.get("company") or "",
                    role=state.get("role") or "",
                )
            except Exception as e:
                print(f"[{self.name}] JD 保存失败（非致命）: {e}")

        return state
