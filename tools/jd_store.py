# tools/jd_store.py
# JD 历史存储工具：结构化提取 + 本地 JSON 持久化 + 相似检索
#
# 设计思路：
#   求职场景 JD 数量有限（几十条），不做 Milvus/FAISS 向量库，
#   而是用 LLM 提取结构化元数据 + LLM 语义匹配实现 "轻量 RAG"。
#   优点是零额外依赖、匹配更精准（LLM 理解 JD 语义而非纯 embedding 相似度）。

import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from langchain_deepseek import ChatDeepSeek

# 存储路径
DATA_DIR = Path(__file__).parent.parent / "data"
STORE_PATH = DATA_DIR / "jd_history.json"


def _get_llm(temperature: float = 0.1):
    return ChatDeepSeek(
        model="deepseek-chat",
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        api_base="https://api.deepseek.com",
        temperature=temperature,
        max_tokens=2048,
    )


def _ensure_store() -> dict:
    """读取或初始化 JD 历史存储"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not STORE_PATH.exists():
        STORE_PATH.write_text(json.dumps({"jds": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"jds": []}
    try:
        return json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return {"jds": []}


def _extract_jd_meta(jd_text: str) -> dict:
    """用 LLM 从 JD 文本中提取结构化元数据（用于存储和检索）"""
    llm = _get_llm(temperature=0.1)

    prompt = f"""从以下岗位描述(JD)中提取关键结构化信息。只输出一个 JSON 对象，不要任何其他文字。

=== JD 文本 ===
{jd_text[:3000]}

=== 输出格式 ===
{{
    "company": "公司名称（中文）",
    "role": "岗位名称",
    "level": "级别（初级/中级/高级/资深/专家/Leader/总监）",
    "location": "工作地点",
    "tech_stack": ["技术栈关键词列表"],
    "required_years": "要求年限（数字，如 5）",
    "industry": "行业方向",
    "keywords": ["最能描述该JD的5-8个关键词"],
    "one_line_summary": "一句话概括该JD的核心要求"
}}"""

    try:
        response = llm.invoke(prompt)
        content = response.content.strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        print(f"[JDStore] 元数据提取失败: {e}")

    # 回退：返回基础元数据
    return {
        "company": "",
        "role": "",
        "level": "",
        "location": "",
        "tech_stack": [],
        "required_years": "",
        "industry": "",
        "keywords": [],
        "one_line_summary": jd_text[:200],
    }


def save_jd(jd_text: str, resume_text: str = "", fit_score: int = 0,
            company: str = "", role: str = "") -> dict:
    """
    保存一份 JD 到历史库（带自动元数据提取）。

    参数:
        jd_text: JD 全文
        resume_text: 当时的简历（用于记录上下文）
        fit_score: 契合度评分（如有）
        company: 用户输入的公司名（覆盖LLM提取值）
        role: 用户输入的岗位名（覆盖LLM提取值）

    返回:
        保存的记录（含 id、meta、时间戳）
    """
    store = _ensure_store()

    meta = _extract_jd_meta(jd_text)

    # 用户手动输入的值优先级更高
    if company:
        meta["company"] = company
    if role:
        meta["role"] = role

    record = {
        "id": f"jd_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
        "created_at": datetime.now().isoformat(),
        "jd_text": jd_text[:5000],          # 保留全文（上限5000字符）
        "resume_snapshot": resume_text[:500] if resume_text else "",
        "fit_score": fit_score,
        "meta": meta,
    }

    store["jds"].append(record)
    STORE_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")

    # 同步索引到向量库
    try:
        from tools.vector_store import add_jd_vector
        add_jd_vector(record["id"], jd_text, {
            "created_at": record["created_at"],
            "company": meta.get("company", ""),
            "role": meta.get("role", ""),
            "level": meta.get("level", ""),
            "tech_stack": meta.get("tech_stack", []),
            "fit_score": fit_score,
            "one_line": meta.get("one_line_summary", ""),
        })
    except Exception as e:
        print(f"[JDStore] 向量索引失败（非致命）: {e}")

    print(f"[JDStore] 已保存 JD: {meta.get('company', '?')} - {meta.get('role', '?')} (id={record['id']})")
    return record


def get_all_jds() -> list:
    """获取所有历史 JD 的摘要列表（用于展示，不含全文）"""
    store = _ensure_store()
    summaries = []
    for jd in reversed(store["jds"]):  # 最新的在前
        meta = jd.get("meta", {})
        summaries.append({
            "id": jd["id"],
            "created_at": jd["created_at"][:10],
            "company": meta.get("company", "未知"),
            "role": meta.get("role", "未知"),
            "level": meta.get("level", ""),
            "location": meta.get("location", ""),
            "tech_stack": meta.get("tech_stack", []),
            "fit_score": jd.get("fit_score", 0),
            "one_line": meta.get("one_line_summary", ""),
        })
    return summaries


def delete_jd(jd_id: str) -> bool:
    """删除指定 JD"""
    store = _ensure_store()
    before = len(store["jds"])
    store["jds"] = [jd for jd in store["jds"] if jd["id"] != jd_id]
    if len(store["jds"]) < before:
        STORE_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
        # 同步删除向量
        try:
            from tools.vector_store import remove_jd_vector
            remove_jd_vector(jd_id)
        except Exception as e:
            print(f"[JDStore] 向量删除失败（非致命）: {e}")
        print(f"[JDStore] 已删除 {jd_id}")
        return True
    return False


def get_jd_by_id(jd_id: str) -> Optional[dict]:
    """按 ID 获取完整 JD 记录"""
    store = _ensure_store()
    for jd in store["jds"]:
        if jd["id"] == jd_id:
            return jd
    return None
