# agent/nodes.py
# 求职Agent的LangGraph节点函数（规划、执行、汇总、判断）
# 注意：所有 print 使用纯文本，避免 Windows GBK 编码崩溃
#
# 2026-07 重构：引入 Multi-Agent 架构 + Token 成本追踪
# - executor_node 现在使用 ResumeAnalyzerAgent / QuestionGeneratorAgent
# - interviewer_node 现在使用 InterviewEvaluatorAgent 评估回答
# - 所有 LLM 调用自动追踪 token 成本

import os
import json
import re
from typing import Dict, Any, Optional
from langgraph.types import interrupt

# LangChain 核心
from langchain_deepseek import ChatDeepSeek

# 导入状态和 Prompt
from agent.state import JobState
from agent.prompts import (
    PLANNER_PROMPT,
    EXECUTOR_PROMPT,
    AGGREGATOR_PROMPT,
    SKILL_EXTRACTION_PROMPT
)

# ===== Multi-Agent 专用 Agent =====
# 每个 Agent 有自己独立的 LLM 实例、temperature 和 system prompt
from agent.agents import (
    ResumeAnalyzerAgent,
    QuestionGeneratorAgent,
    InterviewEvaluatorAgent,
)

# ===== Token 成本追踪 =====
from agent.token_tracker import token_tracker

# ===== 工具函数（Agent 内部会用到） =====
from tools.resume_optimizer import optimize_resume
from tools.jd_retriever import search_similar_jds, build_rag_context
from tools.question_store import get_questions, build_avoid_context

# ===== Agent 实例（全局单例，只初始化一次） =====
_resume_analyzer = None
_question_generator = None
_interview_evaluator = None


def _get_resume_analyzer() -> ResumeAnalyzerAgent:
    global _resume_analyzer
    if _resume_analyzer is None:
        print("[Init] 初始化 ResumeAnalyzerAgent (temperature=0.2)")
        _resume_analyzer = ResumeAnalyzerAgent()
    return _resume_analyzer


def _get_question_generator() -> QuestionGeneratorAgent:
    global _question_generator
    if _question_generator is None:
        print("[Init] 初始化 QuestionGeneratorAgent (temperature=0.7)")
        _question_generator = QuestionGeneratorAgent()
    return _question_generator


def _get_interview_evaluator() -> InterviewEvaluatorAgent:
    global _interview_evaluator
    if _interview_evaluator is None:
        print("[Init] 初始化 InterviewEvaluatorAgent (temperature=0.4)")
        _interview_evaluator = InterviewEvaluatorAgent()
    return _interview_evaluator

# =========================================================
# 1. 初始化 LLM（配置 DeepSeek）
# =========================================================
def get_llm(temperature: float = 0.3):
    """统一获取 DeepSeek LLM 实例"""
    return ChatDeepSeek(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        api_base="https://api.deepseek.com",
        temperature=temperature,
        max_tokens=4096,
    )

# =========================================================
# 2. 规划节点（Planner Node）
# =========================================================
def planner_node(state: JobState) -> JobState:
    """规划阶段：RAG检索相似JD + 解析用户需求，生成执行计划"""
    print("[Planner] 正在分析用户需求并制定计划...")

    llm = get_llm(temperature=0.1)

    # RAG: 仅当用户未提供JD时检索历史相似JD（用户给了JD就以它为准，不查RAG）
    rag_context = ""
    has_jd = bool(state.get("job_description"))
    if not has_jd:
        rag_query = state.get("resume_text", "")
        if rag_query.strip():
            try:
                similar = search_similar_jds(rag_query, top_k=3)
                state["similar_jds"] = similar
                rag_context = build_rag_context(similar)
                state["rag_context"] = rag_context
                print(f"[Planner] RAG检索到 {len(similar)} 条相似JD (无JD，基于简历)")
            except Exception as e:
                print(f"[Planner] RAG检索失败（非致命）: {e}")
                state["similar_jds"] = []
                state["rag_context"] = ""

    # 检索历史面试题（按岗位/公司精确匹配，无需向量检索）
    similar_questions = []
    question_context = ""
    role = state.get("role") or ""
    company = state.get("company") or ""
    if role:
        try:
            similar_questions = get_questions(role=role, company=company)
            state["similar_questions"] = similar_questions
            if similar_questions:
                question_context = build_avoid_context(role=role, company=company)
            print(f"[Planner] 历史面试题检索: 岗位={role}, 共 {len(similar_questions)} 道")
        except Exception as e:
            print(f"[Planner] 面试题检索失败（非致命）: {e}")
            state["similar_questions"] = []

    # 构建 JD 上下文（没有 JD 但有 RAG 结果时，引导 LLM 使用历史 JD）
    jd_text = state.get("job_description", "")
    if not jd_text:
        if rag_context:
            jd_text = f"用户未提供具体JD，但向量库检索到以下相似历史JD可供参考：\n{rag_context}\n请基于最匹配的历史JD为用户提供分析建议。"
        else:
            jd_text = "用户未提供具体JD，请询问。"

    prompt_text = PLANNER_PROMPT.format(
        user_input=state["user_input"],
        resume_text=state.get("resume_text", "用户未提供简历"),
        company=state.get("company") or "（未填写）",
        role=state.get("role") or "（未填写）",
        job_description=jd_text,
        rag_context=rag_context or "（无历史JD记录）",
        question_context=question_context or "（无历史面试题记录）",
    )

    try:
        response = llm.invoke(prompt_text)
        # Token 追踪：记录 Planner 的消耗
        token_tracker.track(response, agent_name="Planner")
        content = response.content.strip()

        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            plan_str = json_match.group()
            plan = json.loads(plan_str)
        else:
            plan = json.loads(content)

        if not isinstance(plan, list):
            raise ValueError("Plan is not a list")

        state["plan"] = plan
        state["current_step"] = 0
        state["status"] = "executing"

        print(f"[Planner] 计划生成成功，共 {len(plan)} 步")
        for step in plan:
            print(f"   - 步骤 {step['step_id']}: {step['description']}")

    except Exception as e:
        print(f"[Planner] 规划失败: {e}")
        state["status"] = "error"
        state["error"] = f"规划失败: {str(e)}"
        state["current_step"] = 0

    return state

# =========================================================
# 3. 执行节点（Executor Node）
# =========================================================
def executor_node(state: JobState) -> JobState:
    """执行阶段：执行计划中的当前步骤"""
    current_step = state["current_step"]
    plan = state["plan"]

    if current_step >= len(plan):
        state["status"] = "finished"
        return state

    step = plan[current_step]
    action = step["action"]
    params = step.get("params", {})

    print(f"[Executor] 执行步骤 {current_step+1}/{len(plan)}: {step['description']}")
    print(f"    工具: {action}, 参数: {params}")

    result = None
    error = None

    try:
        if action == "analyze_jd_resume_fit":
            # === 使用 ResumeAnalyzerAgent（Multi-Agent 架构） ===
            # 面试话术："我把 JD-简历分析交给专门的 ResumeAnalyzer，它有自己的 LLM 实例
            #  和低 temperature 配置，保证分析结果的稳定性。"
            agent = _get_resume_analyzer()
            state = agent.run(state, **params)
            result = state.get("jd_resume_analysis", "")
            if not result:
                result = "请提供简历文本和目标岗位描述（JD），以便生成契合度分析报告。"

        elif action == "optimize_resume":
            jd = params.get("job_description") or state.get("job_description")
            if not jd and state.get("jobs"):
                jd = state["jobs"][0].get("description", "")

            if state.get("resume_text") and jd:
                result = optimize_resume(
                    resume_text=state["resume_text"],
                    job_description=jd,
                    job_title=params.get("job_title", "目标岗位")
                )
                state["resume_advice"] = result
            else:
                result = "请提供简历文本和目标岗位描述（JD），以便生成个性化优化建议。"

        elif action == "generate_questions":
            # === 使用 QuestionGeneratorAgent（Multi-Agent 架构） ===
            # 面试话术："QuestionGenerator 有高 temperature 配置保证题目多样性，
            #  自动查询历史题库做避重。"
            agent = _get_question_generator()
            state = agent.run(state, **params)
            result = "已生成面试题"

        else:
            error = f"未知工具: {action}"
            result = f"错误: {error}"

    except Exception as e:
        error = str(e)
        result = f"执行异常: {error}"
        print(f"[Executor] 工具执行失败: {error}")
        # 关键：即使执行失败，也要确保 jd_resume_analysis 有值
        # 否则 fit_review_node 会因为 jd_resume_analysis 为空而跳过 HITL
        if action == "analyze_jd_resume_fit" and not state.get("jd_resume_analysis"):
            state["jd_resume_analysis"] = f"（分析暂不可用: {error}）"

    step["result"] = result
    step["error"] = error
    state["current_step"] = current_step + 1

    if state["current_step"] >= len(state["plan"]):
        state["status"] = "finished"
        print("[Executor] 所有步骤执行完成")

    return state

# =========================================================
# 4. 汇总节点（Aggregator Node）
# =========================================================
def aggregator_node(state: JobState) -> JobState:
    """汇总阶段：生成最终报告"""
    print("[Aggregator] 正在生成最终求职报告...")

    llm = get_llm(temperature=0.5)

    interview_str = json.dumps(state.get("interview_questions", []), ensure_ascii=False, indent=2)
    if not interview_str or interview_str == "[]":
        interview_str = "（未生成面试题）"

    fit_analysis = state.get("jd_resume_analysis")
    if not fit_analysis:
        fit_analysis = "（未生成契合度分析，请上传简历和JD）"

    resume_advice = state.get("resume_advice")
    if not resume_advice:
        resume_advice = "（未生成简历建议，请上传简历或提供更多信息）"

    prompt_text = AGGREGATOR_PROMPT.format(
        user_input=state["user_input"],
        fit_analysis=fit_analysis,
        similar_jds_context=build_rag_context(state.get("similar_jds", [])),
        resume_advice=resume_advice,
        interview_questions=interview_str,
    )

    try:
        # 改用 stream() 实现逐 token 输出
        full_content = ""
        last_chunk = None
        for chunk in llm.stream(prompt_text):
            if chunk.content:
                full_content += chunk.content
                last_chunk = chunk
        # Token 追踪：记录 Aggregator 的消耗
        if last_chunk and hasattr(last_chunk, 'response_metadata') and last_chunk.response_metadata:
            token_tracker.track_raw(
                prompt_tokens=last_chunk.response_metadata.get("token_usage", {}).get("prompt_tokens", 0),
                completion_tokens=last_chunk.response_metadata.get("token_usage", {}).get("completion_tokens", 0),
                agent_name="Aggregator",
            )
        state["final_output"] = full_content
        state["status"] = "finished"
        print(f"[Aggregator] 报告生成完成，长度={len(full_content)}")

        # 汇总 Token 消耗到 state（方便前端展示）
        try:
            state["token_usage"] = token_tracker.summary()
            token_tracker.save_to_file("data/token_usage.jsonl")
            print(f"[Aggregator] Token消耗汇总: "
                  f"{state['token_usage']['total_calls']} 次调用, "
                  f"{state['token_usage']['total_tokens']} tokens, "
                  f"¥{state['token_usage']['estimated_cost_cny']:.4f}")
        except Exception as e:
            print(f"[Aggregator] Token保存失败（非致命）: {e}")

    except Exception as e:
        print(f"[Aggregator] 生成报告失败: {e}")
        state["final_output"] = f"生成报告时出错: {str(e)}\n\n请检查网络或重试。"
        state["status"] = "error"

    return state

# =========================================================
# 5. 契合度审查节点（Fit Review Node）—— 暂停，等用户决定是否继续面试
# =========================================================
def fit_review_node(state: JobState) -> JobState:
    """契合度审查节点：展示匹配分析结果，让用户决定是否继续模拟面试"""
    has_jd = bool(state.get("job_description"))
    has_resume = bool(state.get("resume_text"))

    # 如果没有 JD 或简历，直接跳过（无需审查）
    if not has_jd or not has_resume:
        print("[FitReview] 缺少 JD 或简历，跳过审查直接进入面试")
        state["skip_interview"] = True  # 没数据，面试也会跳过
        return state

    fit_analysis = state.get("jd_resume_analysis", "")
    if not fit_analysis:
        print("[FitReview] 无契合度分析结果，直接进入面试")
        return state

    # 暂停，让用户查看契合度分析并决定是否继续面试
    print("[FitReview] 暂停执行，等待用户决定是否继续面试...")
    user_decision = interrupt({
        "type": "fit_review",
        "fit_analysis": fit_analysis,
        "similar_jds": state.get("similar_jds", []),
        "similar_questions": state.get("similar_questions", []),
        "question": "契合度分析已完成，是否继续进行模拟面试？",
        "options": ["continue", "skip"]
    })

    # 解析用户决策
    if user_decision and str(user_decision).lower() in ("skip", "no", "跳过", "不", "n"):
        state["skip_interview"] = True
        print("[FitReview] 用户选择跳过面试")
    else:
        state["skip_interview"] = False
        print("[FitReview] 用户选择继续面试")

    return state


# =========================================================
# 6. 面试官节点（Interviewer Node）
# =========================================================
def interviewer_node(state: JobState) -> JobState:
    """面试官节点：支持中断等待用户回答"""
    # 0. 保镖检查
    has_jd = bool(state.get("job_description"))
    has_resume = bool(state.get("resume_text"))
    print(f"[Interviewer] JD={has_jd} (len={len(state.get('job_description') or '')}), "
          f"resume={has_resume} (len={len(state.get('resume_text') or '')})")

    if not has_jd or not has_resume or state.get("skip_interview"):
        print("[Interviewer] 缺少 JD/简历 或 用户选择跳过，跳过模拟面试")
        state["interview_complete"] = True
        return state

    # 1. 生成面试题（使用 QuestionGeneratorAgent 而非直接调用）
    if not state.get("interview_questions"):
        print("[Interviewer] 正在使用 QuestionGeneratorAgent 生成面试题...")
        agent = _get_question_generator()
        state = agent.run(state)
        state["current_q_index"] = 0
        q_count = len(state.get("interview_questions", []))
        print(f"[Interviewer] 生成 {q_count} 道题")

    idx = state["current_q_index"]
    questions = state["interview_questions"]

    # 2. 全部答完 → 生成总结
    if idx >= len(questions):
        state["interview_complete"] = True
        state["pending_question"] = None
        llm = get_llm(temperature=0.3)
        feedback_text = "\n".join(state.get("interview_feedback", []))
        summary = llm.invoke(f"根据以下面试反馈，给出总结评语：\n{feedback_text}")
        token_tracker.track(summary, agent_name="InterviewSummary")
        state["final_output"] = f"=== 面试结束 ===\n{summary.content}"
        return state

    # 3. 抛出当前题目，等待用户回答
    current_q = questions[idx]
    state["pending_question"] = current_q
    print(f"[Interviewer] 等待回答 Q{idx+1}: {current_q[:50]}...")

    user_answer = interrupt({
        "type": "interview",
        "question": current_q,
        "question_num": idx + 1,
        "total": len(questions)
    })

    # 4. 收到回答 → 评估（使用 InterviewEvaluatorAgent）
    if user_answer:
        print(f"[Interviewer] 收到回答，正在使用 InterviewEvaluatorAgent 评估...")
        evaluator = _get_interview_evaluator()
        # 判断题型：根据题目内容关键词
        q_type = "行为"
        if any(kw in current_q for kw in ["设计", "架构", "系统", "方案", "高并发", "扩展"]):
            q_type = "设计"
        elif any(kw in current_q for kw in ["原理", "源码", "性能", "实现", "算法", "技术"]):
            q_type = "技术"
        eval_result = evaluator.evaluate(
            question=current_q,
            answer=user_answer,
            question_type=q_type,
        )
        # 格式化反馈
        feedback = (
            f"第{idx+1}题反馈 (评分: {eval_result['score']}/10):\n"
            f"技术准确性: {eval_result['accuracy']}/10 | "
            f"逻辑结构: {eval_result['structure']}/10 | "
            f"深度: {eval_result['depth']}/10\n"
        )
        if eval_result["strengths"]:
            feedback += "优点:\n" + "\n".join(f"  ✅ {s}" for s in eval_result["strengths"][:2]) + "\n"
        if eval_result["suggestion"]:
            feedback += f"改进建议: {eval_result['suggestion']}\n"

        state["interview_feedback"].append(feedback)
        print(f"[Interviewer] 评估完成 (评分={eval_result['score']}/10)，进入下一题")
        state["current_q_index"] = idx + 1
        state["pending_question"] = None

    return state

# =========================================================
# 7. 条件判断函数（Conditional Edge）
# =========================================================
def should_continue_from_fit_review(state: JobState) -> str:
    """契合度审查后：用户选择跳过面试 → aggregator，否则 → interviewer"""
    if state.get("error"):
        return "error"
    if state.get("skip_interview"):
        print("[Router] 用户跳过面试，直接进入汇总")
        return "finish"  # 跳到 aggregator
    print("[Router] 用户继续面试，进入面试节点")
    return "continue"  # 进入 interviewer


def should_continue(state: JobState) -> str:
    """决定执行器的下一步"""
    if state.get("error"):
        print("[Router] 检测到错误，跳转到 END")
        return "error"

    if state["status"] == "finished":
        print("[Router] 所有步骤完成")
        if state.get("interview_requested"):
            print("[Router] 用户请求面试，跳转到 fit_review")
            return "interview"
        return "finish"

    if state["current_step"] >= len(state["plan"]):
        print("[Router] 步骤索引超出计划，强制结束")
        return "finish"

    print(f"[Router] 继续执行下一步 (步骤 {state['current_step']+1})")
    return "continue"


def should_continue_to_interview(state: JobState) -> str:
    """规划执行完后，判断是否进入面试"""
    if state.get("error"):
        return "error"
    if state.get("job_description") and state.get("resume_text"):
        return "interview"
    return "finish"


def should_continue_interview(state: JobState) -> str:
    """面试过程中判断是否继续下一题"""
    if state.get("error"):
        return "error"
    if state.get("interview_complete"):
        return "finish"
    return "continue"
