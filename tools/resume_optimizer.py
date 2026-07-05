# tools/resume_optimizer.py
# 简历优化工具：基于 JD 分析简历，给出具体优化建议

import os
import json
import re
from langchain_deepseek import ChatDeepSeek


def _get_llm(temperature: float = 0.3):
    """获取 DeepSeek LLM 实例"""
    return ChatDeepSeek(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        api_base="https://api.deepseek.com",
        temperature=temperature,
        max_tokens=4096,
    )


def optimize_resume(resume_text: str, job_description: str, job_title: str) -> str:
    """
    基于 JD 深度分析简历，给出具体可操作的优化建议。

    参数:
        resume_text: 候选人简历全文
        job_description: 目标岗位 JD 全文
        job_title: 目标岗位名称

    返回:
        Markdown 格式的简历优化报告
    """
    llm = _get_llm(temperature=0.3)

    prompt = f"""你是一位资深HR和技术招聘专家，专门帮助候选人针对特定JD优化简历。
请仔细对比以下【岗位JD】和【候选人简历】，给出具体可操作的优化建议。

=== 目标岗位 ===
{job_title}

=== 岗位JD ===
{job_description}

=== 候选人简历 ===
{resume_text}

=== 分析要求 ===
请从以下5个维度深入分析，每个维度都要给出"问题 + 具体修改建议"：

1. **关键词匹配度**
   - JD 中要求的核心技术栈/工具/方法论有哪些？
   - 简历中提到了哪些？遗漏了哪些致命的？
   - 遗漏的关键词应该自然地植入到简历的哪个位置？

2. **经验对标分析**
   - JD 要求的经验年限、项目类型、行业背景
   - 简历中的项目经验能否支撑？差距在哪里？
   - 如何用现有项目经验"靠拢"JD 要求？

3. **成果量化改造**
   - 找出简历中能用数据说话但没有量化的 bullet point
   - 给出"改写前 vs 改写后"的对比（至少2组）
   - 使用 STAR 原则（情境→任务→行动→结果）

4. **缺失项补全策略**
   - JD 中明确要求但简历完全没提的内容
   - 这些缺失项该如何在简历中补充（即使经验有限）？
   - 哪些是硬伤（必须补），哪些是加分项（有更好）？

5. **整体结构建议**
   - 简历的板块顺序是否合理？
   - 技能矩阵、项目经验、工作经历的重点是否突出？
   - 对 ATS（简历筛选系统）的友好度如何？

=== 输出格式 ===
用 Markdown 输出一份《简历优化报告》，语言专业、具体、可直接操作。
不要泛泛而谈，每个建议都要结合简历和JD的具体内容。"""

    response = llm.invoke(prompt)
    return response.content


def extract_skills_from_resume(resume_text: str) -> list:
    """
    从简历文本中提取技能列表（技术技能 + 软技能）。

    参数:
        resume_text: 候选人简历全文

    返回:
        技能名称的字符串列表，如 ["Python", "React", "TypeScript", "团队管理"]
    """
    llm = _get_llm(temperature=0.1)

    prompt = f"""从以下简历文本中，提取出候选人的所有技能（技术技能 + 软技能）。

简历文本：
{resume_text}

请直接输出一个 JSON 数组，不要包含任何其他解释性文字。
示例输出：["Python", "React", "TypeScript", "团队管理", "项目管理"]
只输出数组。"""

    response = llm.invoke(prompt)
    content = response.content.strip()

    # 尝试从 LLM 输出中提取 JSON 数组
    json_match = re.search(r'\[.*\]', content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return []
