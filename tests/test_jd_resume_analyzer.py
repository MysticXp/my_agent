# tests/test_jd_resume_analyzer.py
# JD-简历分析工具测试（纯文本解析，不依赖 LLM）
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.jd_resume_analyzer import extract_match_score


# ============================================================
# extract_match_score 测试
# ============================================================

FULL_REPORT = """
## 🔍 JD-简历契合度分析报告

### 📊 综合匹配度评分: **82/100** (等级：A)
> 等级说明：S(90-100)=高度匹配  A(75-89)=良好匹配

---

### 1. 核心技能匹配度 (权重30%) — **85/100**
**[已命中的技能]**
- React：5年经验 ✅

### 2. 经验年限对标 (权重20%) — **70/100**

### 3. 学历与资质匹配 (权重10%) — **90/100**

### 4. 岗位职责覆盖度 (权重20%) — **80/100**

### 5. 软技能与文化匹配 (权重10%) — **75/100**

### 6. 加分项与差异化 (权重10%) — **60/100**
"""

PARTIAL_REPORT = """
## 🔍 JD-简历契合度分析报告

### 📊 综合匹配度评分: **75/100** (等级：B)

---

### 1. 核心技能匹配度 (权重30%) — **80/100**

### 2. 经验年限对标 (权重20%) — **65/100**

### 4. 岗位职责覆盖度 (权重20%) — **70/100**
"""


class TestExtractMatchScore:

    def test_full_report(self):
        """标准报告文本，提取所有维度分数正确"""
        scores = extract_match_score(FULL_REPORT)
        assert scores["total_score"] == 82
        assert scores["grade"] == "A"
        assert scores["skill_score"] == 85
        assert scores["experience_score"] == 70
        assert scores["education_score"] == 90
        assert scores["responsibility_score"] == 80
        assert scores["soft_skill_score"] == 75
        assert scores["bonus_score"] == 60

    def test_partial_dimensions(self):
        """部分维度缺失时降级为 0"""
        scores = extract_match_score(PARTIAL_REPORT)
        assert scores["total_score"] == 75
        assert scores["grade"] == "B"
        assert scores["skill_score"] == 80
        assert scores["experience_score"] == 65
        # 缺失的维度
        assert scores["education_score"] == 0
        assert scores["bonus_score"] == 0

    def test_empty_text(self):
        """空文本返回全 0"""
        scores = extract_match_score("")
        assert scores["total_score"] == 0
        assert scores["grade"] == "N/A"
        assert scores["skill_score"] == 0
        assert scores["experience_score"] == 0

    def test_no_scores_found(self):
        """没有评分信息的文本"""
        scores = extract_match_score("这是一段没有评分的纯文本\n没有数字和分数")
        assert scores["total_score"] == 0
        assert scores["grade"] == "N/A"
        assert all(v == 0 for k, v in scores.items() if k != "grade")

    def test_grade_extraction(self):
        """等级字母提取（仅测试正则能匹配的格式）"""
        tests = [
            ("等级：S", "S"),
            ("等级： (A)", "A"),
            ("等级: B", "B"),
            ("等级：(C)", "C"),
            ("等级：D", "D"),
        ]
        for text, expected in tests:
            scores = extract_match_score(f"综合匹配度评分: 50/100\n{text}")
            assert scores["grade"] == expected, f"Failed for {text}"
