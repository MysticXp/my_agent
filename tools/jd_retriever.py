# tools/jd_retriever.py
# JD 相似检索器：向量语义匹配（BGE embedding + 余弦相似度）
#
# 升级说明：
#   原先用 LLM 做候选匹配，改为用 BGE-small-zh-v1.5 embedding 做向量检索。
#   好处：精确、可复现、支持"换份简历重新匹配所有JD"的场景。

from tools.vector_store import search_similar_jds as _vector_search
from tools.jd_store import _ensure_store


def search_similar_jds(query_text: str, top_k: int = 3) -> list:
    """
    向量相似度检索：找与 query 最相似的 top_k 条历史 JD。

    参数:
        query_text: 待匹配的 JD 全文（或简历文本）
        top_k: 返回条数

    返回:
        [{"id": "...", "score": 85.2, "company": "...", "role": "...",
          "similarity_reason": "...", "jd_text": "...", ...}, ...]
    """
    # 从向量库检索
    vec_results = _vector_search(query_text, top_k=top_k, min_score=0.3)

    if not vec_results:
        return []

    # 补充 JD 全文（向量库只存元数据，全文在 jd_history.json）
    store = _ensure_store()
    id_to_jd = {jd["id"]: jd for jd in store.get("jds", [])}

    results = []
    for vr in vec_results:
        jd_id = vr.get("id", "")
        full = id_to_jd.get(jd_id, {})
        results.append({
            "id": jd_id,
            "company": vr.get("company", ""),
            "role": vr.get("role", ""),
            "level": vr.get("level", ""),
            "tech_stack": vr.get("tech_stack", []),
            "created_at": vr.get("created_at", "")[:10],
            "fit_score": vr.get("fit_score", 0),
            "score": vr.get("score", 0),
            "jd_text": full.get("jd_text", ""),
            "similarity_reason": vr.get("similarity_reason", "岗位相似"),
        })

    return results


def build_rag_context(similar_jds: list) -> str:
    """
    将相似 JD 列表构建成可注入 Prompt 的 RAG 上下文文本。
    """
    if not similar_jds:
        return "（无历史JD记录，这是首次分析）"

    lines = ["以下是你过往分析过的相似岗位（向量检索结果），可供参考：\n"]
    for i, jd in enumerate(similar_jds, 1):
        similarity = jd.get("score", jd.get("fit_score", "?"))
        lines.append(
            f"**{i}. {jd['company']} — {jd['role']}** "
            f"（{jd['created_at']}，向量相似度{similarity}%）\n"
            f"   相似原因：{jd['similarity_reason']}\n"
        )
        jd_text = jd.get("jd_text", "")
        if jd_text:
            lines.append(f"   JD摘要：{jd_text[:200]}...\n")

    return "\n".join(lines)
