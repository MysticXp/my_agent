# tools/jd_resume_analyzer.py
# JD-简历契合度分析工具：深度对比JD与简历，给出匹配度评分和改进建议

import os
import json
import re
from langchain_deepseek import ChatDeepSeek


def _get_llm(temperature: float = 0.2):
    """获取 DeepSeek LLM 实例"""
    return ChatDeepSeek(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        api_base="https://api.deepseek.com",
        temperature=temperature,
        max_tokens=4096,
    )


def analyze_jd_resume_fit(job_description: str, resume_text: str) -> str:
    """
    深度对比JD与候选人简历，输出契合度分析报告。

    参数:
        job_description: 目标岗位 JD 全文
        resume_text: 候选人简历全文

    返回:
        Markdown 格式的契合度分析报告，包含：
        - 综合匹配度评分
        - 各维度匹配分析
        - 技能雷达对比
        - 差距与弥补策略
    """
    llm = _get_llm(temperature=0.2)

    # 截取长度避免 prompt 过长（保留足够信息量）
    jd_section = job_description[:3000] if len(job_description) > 3000 else job_description
    resume_section = resume_text[:3000] if len(resume_text) > 3000 else resume_text

    prompt = f"""你是一位资深猎头和人才评估专家，专门为候选人分析其简历与目标岗位的契合度。

请仔细对比以下【岗位JD】和【候选人简历】，输出一份详细的契合度分析报告。

=== 目标岗位JD ===
{jd_section}

=== 候选人简历 ===
{resume_section}

=== 分析要求 ===
请从以下6个维度深入分析，最后给出综合评分：

**1. 核心技能匹配度 (权重30%)**
   - JD要求的核心技术栈/工具/框架有哪些？
   - 候选人已掌握哪些？掌握程度如何？
   - 列出"已命中"和"缺失"的关键技能清单
   - 本维度评分（满分100）

**2. 经验年限对标 (权重20%)**
   - JD要求的工作年限 vs 候选人实际年限
   - 项目复杂度和规模的对比
   - 行业背景是否匹配
   - 本维度评分（满分100）

**3. 学历与资质匹配 (权重10%)**
   - JD要求的学历/专业 vs 候选人学历
   - 相关证书/资质是否满足
   - 本维度评分（满分100）

**4. 岗位职责覆盖度 (权重20%)**
   - JD列出的每一项核心职责，候选人的经历能否支撑？
   - 哪些职责可以完全胜任？哪些需要学习？
   - 本维度评分（满分100）

**5. 软技能与文化匹配 (权重10%)**
   - 根据JD推断的团队文化和工作方式
   - 候选人简历中体现的软技能和协作风格
   - 本维度评分（满分100）

**6. 加分项与差异化 (权重10%)**
   - JD中的"优先"/"加分"条件，候选人满足多少？
   - 候选人有哪些JD没要求但可能加分的独特优势？
   - 本维度评分（满分100）

=== 输出格式 ===
请严格按照以下 Markdown 格式输出：

## 🔍 JD-简历契合度分析报告

### 📊 综合匹配度评分: **XX/100** (等级：S/A/B/C/D)
> 等级说明：S(90-100)=高度匹配  A(75-89)=良好匹配  B(60-74)=基本匹配  C(40-59)=偏低  D(<40)=不匹配

---

### 1. 核心技能匹配度 (权重30%) — **XX/100**
**[已命中的技能]**
- 技能X：JD要求XXX，简历体现XXX ✅
- ...

**[缺失的关键技能]**
- 技能Y：JD要求XXX，简历未体现 ❌
- ...

### 2. 经验年限对标 (权重20%) — **XX/100**
- JD要求：X年经验 / 候选人：Y年
- 项目经验对比：...

### 3. 学历与资质匹配 (权重10%) — **XX/100**
- JD要求：XX学历 / 候选人：XX学历
- ...

### 4. 岗位职责覆盖度 (权重20%) — **XX/100**
| 岗位职责 | 覆盖状态 | 说明 |
|---------|---------|------|
| 职责A | ✅/⚠️/❌ | ... |

### 5. 软技能与文化匹配 (权重10%) — **XX/100**
- ...

### 6. 加分项与差异化 (权重10%) — **XX/100**
- ...

---

### 🎯 总体结论与建议

**核心优势（3条）:**
1. ...
2. ...
3. ...

**关键短板（3条）:**
1. ...
2. ...
3. ...

**投递策略建议:**
- 是否建议投递：是 / 可尝试 / 暂不建议
- 如果投递，简历应重点突出的3个方向
- 面试中应主动规避或准备的3个问题

请确保每个维度的评分真实反映对比结果，不要虚高评分。
如果简历中的某项信息缺失，请明确指出"简历中未体现"而不是猜测。"""

    response = llm.invoke(prompt)
    return response.content


def extract_match_score(analysis_text: str) -> dict:
    """
    从分析报告文本中提取综合评分和关键指标。
    用于前端展示分数卡片。

    返回:
        {
            "total_score": 82,
            "grade": "A",
            "skill_score": 85,
            "experience_score": 70,
            "education_score": 90,
            "responsibility_score": 80,
            "soft_skill_score": 75,
            "bonus_score": 60
        }
    """
    scores = {
        "total_score": 0,
        "grade": "N/A",
        "skill_score": 0,
        "experience_score": 0,
        "education_score": 0,
        "responsibility_score": 0,
        "soft_skill_score": 0,
        "bonus_score": 0,
    }

    # 提取综合评分
    total_match = re.search(r'综合匹配度评分.*?\*{0,2}(\d{2,3})\s*/\s*100', analysis_text)
    if total_match:
        scores["total_score"] = int(total_match.group(1))

    # 提取等级
    grade_match = re.search(r'等级[：:]\s*[（(]?([SABCD])[）)]?', analysis_text)
    if grade_match:
        scores["grade"] = grade_match.group(1)

    # 提取各维度评分
    dim_patterns = [
        ("skill_score", r'核心技能匹配度.*?\*{0,2}(\d{2,3})\s*/\s*100'),
        ("experience_score", r'经验年限对标.*?\*{0,2}(\d{2,3})\s*/\s*100'),
        ("education_score", r'学历与资质匹配.*?\*{0,2}(\d{2,3})\s*/\s*100'),
        ("responsibility_score", r'岗位职责覆盖度.*?\*{0,2}(\d{2,3})\s*/\s*100'),
        ("soft_skill_score", r'软技能与文化匹配.*?\*{0,2}(\d{2,3})\s*/\s*100'),
        ("bonus_score", r'加分项与差异化.*?\*{0,2}(\d{2,3})\s*/\s*100'),
    ]

    for key, pattern in dim_patterns:
        match = re.search(pattern, analysis_text)
        if match:
            scores[key] = int(match.group(1))

    return scores
