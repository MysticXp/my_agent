# agent/nodes.py
# 求职Agent的LangGraph节点函数（规划、执行、汇总、判断）
# 注意：所有 print 使用纯文本，避免 Windows GBK 编码崩溃

import os
import json
import re
from typing import Dict, Any
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

# 导入所有工具函数
from tools.resume_optimizer import optimize_resume, extract_skills_from_resume
from tools.interview import generate_interview_questions

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
    """规划阶段：解析用户需求，生成执行计划"""
    print("[Planner] 正在分析用户需求并制定计划...")

    llm = get_llm(temperature=0.1)
    jd_text = state.get("job_description", "")
    if not jd_text:
        jd_text = "用户未提供具体JD，请询问。"

    prompt_text = PLANNER_PROMPT.format(
        user_input=state["user_input"],
        resume_text=state.get("resume_text", "用户未提供简历"),
        job_description=jd_text
    )

    try:
        response = llm.invoke(prompt_text)
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
        if action == "optimize_resume":
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
            result = generate_interview_questions(
                job_title=params.get("job_title", state.get("target_role", "开发工程师")),
                company=params.get("company", "目标公司"),
                skills=state.get("user_skills", []),
                jd_text=state.get("job_description", ""),
                resume_text=state.get("resume_text", "")
            )
            state["interview_questions"] = result

        else:
            error = f"未知工具: {action}"
            result = f"错误: {error}"

    except Exception as e:
        error = str(e)
        result = f"执行异常: {error}"
        print(f"[Executor] 工具执行失败: {error}")

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

    resume_advice = state.get("resume_advice")
    if not resume_advice:
        resume_advice = "（未生成简历建议，请上传简历或提供更多信息）"

    prompt_text = AGGREGATOR_PROMPT.format(
        user_input=state["user_input"],
        resume_advice=resume_advice,
        interview_questions=interview_str,
    )

    try:
        response = llm.invoke(prompt_text)
        state["final_output"] = response.content
        state["status"] = "finished"
        print(f"[Aggregator] 报告生成完成，长度={len(response.content)}")
    except Exception as e:
        print(f"[Aggregator] 生成报告失败: {e}")
        state["final_output"] = f"生成报告时出错: {str(e)}\n\n请检查网络或重试。"
        state["status"] = "error"

    return state

# =========================================================
# 5. 面试官节点（Interviewer Node）
# =========================================================
def interviewer_node(state: JobState) -> JobState:
    """面试官节点：支持中断等待用户回答"""
    # 0. 保镖检查
    has_jd = bool(state.get("job_description"))
    has_resume = bool(state.get("resume_text"))
    print(f"[Interviewer] JD={has_jd} (len={len(state.get('job_description') or '')}), "
          f"resume={has_resume} (len={len(state.get('resume_text') or '')})")

    if not has_jd or not has_resume:
        print("[Interviewer] 缺少 JD 或简历，跳过模拟面试")
        state["interview_complete"] = True
        return state

    # 1. 生成面试题
    if not state.get("interview_questions"):
        print("[Interviewer] 正在生成面试题...")
        questions = generate_interview_questions(
            job_title=state.get("target_role") or "开发工程师",
            company="目标公司",
            skills=state.get("user_skills", []),
            jd_text=state.get("job_description", ""),
            resume_text=state.get("resume_text", "")
        )
        state["interview_questions"] = questions
        state["current_q_index"] = 0
        print(f"[Interviewer] 生成 {len(questions)} 道题")

    idx = state["current_q_index"]
    questions = state["interview_questions"]

    # 2. 全部答完 → 生成总结
    if idx >= len(questions):
        state["interview_complete"] = True
        state["pending_question"] = None
        llm = get_llm(temperature=0.3)
        feedback_text = "\n".join(state.get("interview_feedback", []))
        summary = llm.invoke(f"根据以下面试反馈，给出总结评语：\n{feedback_text}")
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

    # 4. 收到回答 → 评估
    if user_answer:
        print(f"[Interviewer] 收到回答，正在评估...")
        llm = get_llm(temperature=0.4)
        eval_prompt = f"""
问题：{current_q}
候选人的回答：{user_answer}
请给出反馈（优点、缺点、改进建议），用2-3句话。
"""
        feedback = llm.invoke(eval_prompt).content
        state["interview_feedback"].append(f"第{idx+1}题反馈: {feedback}")
        print(f"[Interviewer] 评估完成，进入下一题")
        state["current_q_index"] = idx + 1
        state["pending_question"] = None

    return state

# =========================================================
# 6. 条件判断函数（Conditional Edge）
# =========================================================
def should_continue(state: JobState) -> str:
    """决定执行器的下一步"""
    if state.get("error"):
        print("[Router] 检测到错误，跳转到 END")
        return "error"

    if state["status"] == "finished":
        print("[Router] 所有步骤完成，进入面试节点")
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
