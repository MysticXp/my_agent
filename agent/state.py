# agent/state.py
# 求职Agent的"数据大脑" —— 定义所有状态结构

from typing import List, Dict, Optional, Any, TypedDict
from datetime import datetime

# =====================================================
# 1. 核心状态定义（LangGraph 的状态容器）
# =====================================================
class JobState(TypedDict):
    """
    求职Agent的完整状态对象。
    LangGraph 会基于这个类型定义来管理整个工作流的数据流转。
    """
    
    # ---------- 用户输入 ----------
    user_input: str
    """用户当前发送的原始消息，如 '帮我找前端工作' """
    
    resume_text: Optional[str]
    """用户上传的简历文本，可能为空"""
    
    job_description: Optional[str]
    """用户直接粘贴的职位描述（JD），优先级最高"""
    
    user_skills: List[str]
    """从简历中提取的技能列表，如 ['React', 'Python', '项目管理']"""
    
    target_role: str
    """用户期望的岗位，如 '前端开发工程师'"""
    
    target_location: str
    """用户期望的工作地点，如 '上海' 或 '远程'"""
    
    # ---------- 规划阶段 ----------
    plan: List[Dict[str, Any]]
    """
    执行计划列表，每一项是一个步骤：
    [
        {
            "step_id": 1,
            "action": "search_jobs",
            "params": {"role": "前端", "location": "上海"},
            "description": "搜索前端岗位"
        },
        ...
    ]
    """
    
    current_step: int
    """当前执行到第几步（从0开始计数）"""
    
    max_steps: int
    """最大允许执行步数，防止死循环（面试常问！）"""
    
    # ---------- 执行结果 ----------
    jd_resume_analysis: Optional[str]
    """JD与简历契合度分析报告（由 analyze_jd_resume_fit 工具生成）"""

    resume_advice: Optional[str]
    """简历优化建议文本（由 optimize_resume 工具生成）"""
    
    interview_questions: List[str]
    """生成的面试题列表"""
    
    # ---------- 多轮面试专用字段 ----------
    current_q_index: int                # 当前问到第几题（从0开始）
    interview_feedback: List[str]       # 每道题的反馈记录
    interview_complete: bool            # 是否所有题目都问完了
    pending_question: Optional[str]     # 当前正在等待回答的问题
    
    # ---------- 控制流 ----------
    status: str
    """
    当前状态机的状态：
    - "planning": 规划阶段
    - "executing": 执行阶段
    - "finished": 已完成所有步骤
    - "error": 发生错误
    """
    
    error: Optional[str]
    """错误信息，如果 status == "error" 时填充"""
    
    final_output: str
    """最终输出给用户的报告内容（由 aggregator_node 生成）"""
    
    # ---------- 记忆系统 ----------
    conversation_history: List[Dict]
    """
    多轮对话历史，用于上下文理解：
    [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    """
    
    user_preferences: Dict[str, Any]
    """
    用户偏好存储，如：
    {
        "preferred_companies": ["Google", "Meta"],
        "avoid_industries": ["金融"],
        "min_salary": 80000
    }
    """


# =====================================================
# 2. 状态初始化工具函数
# =====================================================
def create_initial_state(
    user_input: str, 
    resume: Optional[str] = None,
    job_description: Optional[str] = None
) -> JobState:
    """
    创建一个干净的初始状态，用于每次新对话的开始。
    
    参数:
        user_input: 用户发送的消息
        resume: 用户可选粘贴的简历文本
    
    返回:
        一个完整的 JobState 对象，所有字段都已初始化
    """
    return JobState(
        # 用户输入
        user_input=user_input,
        resume_text=resume,
        job_description=job_description,
        user_skills=[],
        target_role="",
        target_location="",
        
        # 规划相关
        plan=[],
        current_step=0,
        max_steps=5,  # 最多执行5步，防止死循环
        
        # 结果存储
        jd_resume_analysis=None,
        resume_advice=None,
        interview_questions=[],
        current_q_index=0,
        interview_feedback=[],
        interview_complete=False,
        pending_question=None,
        
        # 控制流
        status="planning",   # 初始状态为 planning
        error=None,
        final_output="",
        
        # 记忆
        conversation_history=[
            {"role": "user", "content": user_input}
        ],
        user_preferences={}
    )


def update_state_with_preferences(
    state: JobState, 
    preferences: Dict[str, Any]
) -> JobState:
    """
    更新用户偏好（长期记忆），返回新的状态。
    注意：TypedDict 是不可变的，所以我们需要返回一个新对象。
    但在 LangGraph 中可以直接修改字典，这里仅做演示。
    """
    state["user_preferences"].update(preferences)
    return state


# =====================================================
# 3. 辅助函数（用于调试和展示）
# =====================================================
def state_summary(state: JobState) -> str:
    """生成状态摘要，方便调试时打印"""
    return f"""
    ===== Agent 状态摘要 =====
    用户需求: {state['user_input'][:50]}...
    当前步骤: {state['current_step']}/{len(state['plan'])}
    状态: {state['status']}
    已生成面试题: {len(state['interview_questions'])}
    简历优化建议: {'有' if state['resume_advice'] else '无'}
    ==========================
    """


# =====================================================
# 4. 面试知识点（写在代码注释里方便你背）
# =====================================================
"""
【面试官常问】为什么用 TypedDict 而不是 Pydantic 或普通 Class？
答：
1. TypedDict 是原生 Python 类型，LangGraph 原生支持，序列化更轻量。
2. Pydantic 虽然校验更强，但在状态图频繁读写时会有性能开销。
3. TypedDict 配合 MyPy 可以做静态类型检查，适合大型项目。

【面试官常问】max_steps 怎么确定？设多少合适？
答：
根据任务复杂度动态调整。求职场景通常 3-5 步足够（搜索→优化→面试→薪资）。
如果超过 5 步还未完成，大概率 Agent 陷入循环或逻辑错误，
此时应该抛出异常并记录日志，而不是无限等待。

【面试官常问】如何防止状态污染？
答：
每次新对话调用 create_initial_state() 创建全新状态，
历史记忆通过 user_preferences 和 conversation_history 显式控制，
避免不同用户的请求相互影响。
"""