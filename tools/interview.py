# tools/interview.py
# 模拟面试工具：根据 JD + 候选人背景生成定制面试题

import os
import re
from langchain_deepseek import ChatDeepSeek


def _get_llm(temperature: float = 0.7):
    """获取 DeepSeek LLM 实例"""
    return ChatDeepSeek(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        api_base="https://api.deepseek.com",
        temperature=temperature,
        max_tokens=4096,
    )


def generate_interview_questions(
    job_title: str,
    company: str,
    skills: list,
    jd_text: str = "",
    resume_text: str = "",
    avoid_context: str = ""
) -> list:
    """
    根据 JD 和候选人背景，生成定制化模拟面试题。

    参数:
        job_title: 目标岗位名称
        company: 目标公司
        skills: 候选人技能列表
        jd_text: 岗位描述全文（用于生成针对性问题）
        resume_text: 候选人简历（用于生成个性化问题）
        avoid_context: 历史题目避重上下文（列出已出过的题，要求LLM不要重复）

    返回:
        面试题字符串列表，共5道（2技术 + 1系统设计 + 2行为）
    """
    llm = _get_llm(temperature=0.7)

    # 如果提供了 JD，截取关键部分避免 prompt 过长
    jd_context = jd_text[:1500] if jd_text else f"岗位：{job_title}，公司：{company}"
    resume_context = resume_text[:800] if resume_text else "候选人未提供简历"

    skills_str = ", ".join(skills) if skills else "未提取到技能"

    # 避重上下文
    avoid_section = ""
    if avoid_context:
        avoid_section = f"\n=== 历史已出题目（请务必避开，不要重复！） ===\n{avoid_context}\n"

    prompt = f"""你是{company}的资深技术面试官，正在为候选人准备一场模拟面试。

=== 目标岗位 JD ===
{jd_context}

=== 候选人简历摘要 ===
{resume_context}

=== 候选人技能 ===
{skills_str}
{avoid_section}
=== 出题要求 ===
请生成5道面试题，并按下面格式严格输出。

**第1题 - 技术深度**
- 考察候选人最核心的技术栈（从JD中提取最关键的技术要求）
- 要求候选人深入解释原理，不能只停留在使用层面
- 追问方向：源码实现、性能优化、踩坑经验

**第2题 - 技术深度**
- 考察JD要求的第二核心技术
- 结合实际业务场景的技术选型和架构决策

**第3题 - 系统设计**
- 结合{company}的实际业务场景，设计一个系统
- 考察：架构思维、扩展性、高可用、数据一致性

**第4题 - 行为面试**
- 考察项目管理和团队协作能力
- 结合候选人简历中的项目经验提问

**第5题 - 行为面试**
- 考察职业规划和文化匹配度
- 结合{company}的行业特点

=== 输出格式（严格） ===
每道题一行，格式为：
1. [技术] 题目内容
2. [技术] 题目内容
3. [设计] 题目内容
4. [行为] 题目内容
5. [行为] 题目内容

只输出这5行，不要输出任何额外的解释、标签或 Markdown 格式。"""

    response = llm.invoke(prompt)
    content = response.content.strip()

    # 解析：按行提取，去掉编号前缀
    questions = []
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
        # 匹配 "1. " "1) " "1、 " 等编号格式
        cleaned = re.sub(r'^\d+[\.\、\)]\s*', '', line)
        # 去掉可能残留的标签前缀如 "[技术] "（LLM 可能不按格式输出）
        if cleaned and len(cleaned) > 5:
            questions.append(cleaned)

    # 确保至少有题可用
    if len(questions) < 3:
        # 如果解析失败，回退：按行直接取
        questions = [line.strip() for line in content.split('\n')
                     if line.strip() and len(line.strip()) > 10]

    return questions[:5]
