# tools/vector_store.py
# 向量存储引擎：embedding 生成 + 向量持久化 + 余弦相似度检索
#
# 技术选型：
#   - Embedding 模型: BAAI/bge-small-zh-v1.5（中文优化，24MB，CPU友好）
#   - 向量存储: numpy 数组 + JSON 元数据（轻量，无需数据库服务）
#   - 相似度: 余弦相似度
#
# 存储结构：
#   data/vectors/
#     jd_vectors.npy      # shape (N, 512) — JD 向量矩阵
#     jd_metadata.json    # [{"id": "jd_xxx", "created_at": ..., "company": ..., "role": ..., ...}, ...]
#     resume_vectors.npy  # shape (M, 512) — 简历向量矩阵
#     resume_metadata.json

import os
import json
import numpy as np
from pathlib import Path
from typing import Optional
from datetime import datetime
from sentence_transformers import SentenceTransformer

# 存储目录
VECTOR_DIR = Path(__file__).parent.parent / "data" / "vectors"

# 本地模型存放路径（把你的模型文件夹放这里）
LOCAL_MODEL_DIR = Path(__file__).parent.parent / "data" / "models" / "bge-small-zh-v1.5"

# 全局 embedding 模型（延迟加载，全局复用）
_embedding_model: Optional[SentenceTransformer] = None


def _get_model() -> SentenceTransformer:
    """
    加载 embedding 模型，按以下优先级尝试：

    1. 本地路径: data/models/bge-small-zh-v1.5/
       预先下载模型文件夹放到这里即可离线使用

    2. ModelScope（国内可访问）:
       modelscope.cn 上的镜像，不需要翻墙

    3. HF Mirror（国内可访问）:
       hf-mirror.com，设置环境变量即可

    4. HuggingFace 官方:
       最后的回退选项
    """
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model

    model_id = "BAAI/bge-small-zh-v1.5"
    sources = []

    # --- 优先级 1: 本地路径 ---
    if LOCAL_MODEL_DIR.exists() and (LOCAL_MODEL_DIR / "config.json").exists():
        sources.append(("本地", str(LOCAL_MODEL_DIR)))

    # --- 优先级 2: 设置 HF_ENDPOINT 到镜像 ---
    if "HF_ENDPOINT" in os.environ:
        sources.append(("HF镜像", os.environ["HF_ENDPOINT"]))

    # --- 优先级 3: ModelScope ---
    sources.append(("ModelScope", "BAAI/bge-small-zh-v1.5"))

    # --- 优先级 4: HF 官方 ---
    sources.append(("HuggingFace官方", model_id))

    last_error = None
    for label, source in sources:
        try:
            print(f"[VectorStore] 尝试从 {label} 加载模型: {source}")
            if label == "ModelScope":
                # ModelScope 需要通过 modelscope SDK 或设置镜像
                _embedding_model = SentenceTransformer(
                    source,
                    trust_remote_code=True,
                )
            elif label == "HF镜像":
                # 已经通过 HF_ENDPOINT 设置了镜像
                _embedding_model = SentenceTransformer(
                    model_id,
                    trust_remote_code=True,
                )
            else:
                _embedding_model = SentenceTransformer(
                    source,
                    trust_remote_code=True,
                )

            dim = _embedding_model.get_sentence_embedding_dimension()
            print(f"[VectorStore] 模型加载成功 ({label})，维度={dim}")
            return _embedding_model

        except Exception as e:
            last_error = e
            print(f"[VectorStore] {label} 加载失败: {e}")
            continue

    raise RuntimeError(
        f"无法加载 embedding 模型，所有来源均失败。\n"
        f"最后一个错误: {last_error}\n\n"
        f"解决方案（任选一种）：\n"
        f"  1. 本地下载（推荐）: 下载 https://hf-mirror.com/{model_id}\n"
        f"     将所有文件放到: {LOCAL_MODEL_DIR}\n"
        f"  2. 设置HF镜像: set HF_ENDPOINT=https://hf-mirror.com\n"
        f"  3. ModelScope: pip install modelscope && python -c \"from modelscope import snapshot_download; snapshot_download('{model_id}')\""
    )


def _ensure_dir():
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)


def embed_text(text: str) -> np.ndarray:
    """将文本转为 embedding 向量 (512维)"""
    model = _get_model()
    # BGE 模型推荐对 query 加前缀以获得更好的检索效果
    embedding = model.encode(text, normalize_embeddings=True, show_progress_bar=False)
    return embedding


def embed_batch(texts: list) -> np.ndarray:
    """批量生成 embedding 向量"""
    model = _get_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings


# ============================================================
# JD 向量存储
# ============================================================

def _load_jd_vectors() -> tuple:
    """加载 JD 向量矩阵和元数据"""
    _ensure_dir()
    vec_path = VECTOR_DIR / "jd_vectors.npy"
    meta_path = VECTOR_DIR / "jd_metadata.json"

    if vec_path.exists() and meta_path.exists():
        vectors = np.load(vec_path)
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        return vectors, metadata
    return np.empty((0, 512)), []


def _save_jd_vectors(vectors: np.ndarray, metadata: list):
    """保存 JD 向量矩阵和元数据"""
    _ensure_dir()
    np.save(VECTOR_DIR / "jd_vectors.npy", vectors)
    (VECTOR_DIR / "jd_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def add_jd_vector(jd_id: str, jd_text: str, meta: dict):
    """索引一条 JD 到向量库"""
    vectors, metadata = _load_jd_vectors()

    # 生成 embedding
    embedding = embed_text(jd_text)

    # 追加
    if vectors.size == 0:
        vectors = embedding.reshape(1, -1)
    else:
        vectors = np.vstack([vectors, embedding.reshape(1, -1)])

    metadata.append({
        "id": jd_id,
        "indexed_at": datetime.now().isoformat(),
        **meta,
    })

    _save_jd_vectors(vectors, metadata)
    print(f"[VectorStore] JD已索引: {jd_id} (总数={len(metadata)})")


def remove_jd_vector(jd_id: str):
    """从向量库中删除指定 JD"""
    vectors, metadata = _load_jd_vectors()
    idx = next((i for i, m in enumerate(metadata) if m.get("id") == jd_id), None)
    if idx is not None:
        vectors = np.delete(vectors, idx, axis=0)
        metadata.pop(idx)
        _save_jd_vectors(vectors, metadata)
        print(f"[VectorStore] JD已移除: {jd_id} (剩余={len(metadata)})")


def search_similar_jds(query_text: str, top_k: int = 3, min_score: float = 0.3) -> list:
    """
    向量相似度检索：找与 query 最相似的 top_k 条 JD。

    返回:
        [{"id": "...", "score": 0.92, "company": "...", ...}, ...]
        按相似度降序排列
    """
    vectors, metadata = _load_jd_vectors()

    if vectors.size == 0:
        print("[VectorStore] 向量库为空，返回空结果")
        return []

    # 生成 query embedding 并计算余弦相似度
    query_vec = embed_text(query_text)
    # vectors 已 normalize，直接点积 = 余弦相似度
    scores = np.dot(vectors, query_vec)

    # 按分数降序排序，取 top_k
    if len(scores) <= top_k:
        top_indices = np.argsort(scores)[::-1]
    else:
        top_indices = np.argpartition(scores, -top_k)[-top_k:]
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]

    results = []
    seen_ids = set()
    for idx in top_indices:
        score = float(scores[idx])
        if score < min_score:
            continue
        meta = metadata[idx]
        if meta.get("id") in seen_ids:
            continue
        seen_ids.add(meta.get("id"))
        results.append({
            **meta,
            "score": round(score * 100, 1),  # 转为百分制
        })

    # 为每条结果生成一个人类可读的相似原因
    for r in results:
        r["similarity_reason"] = _generate_similarity_reason(query_text, r)

    print(f"[VectorStore] 检索完成: {len(results)}/{len(metadata)} 条 (top_k={top_k})")
    for r in results:
        print(f"  - {r.get('company', '?')} {r.get('role', '?')} | 相似度={r['score']}%")

    return results


def _generate_similarity_reason(query_text: str, result: dict) -> str:
    """生成简单的相似原因描述"""
    reasons = []
    company = result.get("company", "")
    role = result.get("role", "")
    score = result.get("score", 0)

    if score >= 85:
        reasons.append("高度匹配")
    elif score >= 70:
        reasons.append("良好匹配")
    elif score >= 50:
        reasons.append("部分匹配")

    if company:
        reasons.append(f"同公司" if "同公司" not in reasons else "")
    if role:
        reasons.append(f"岗位相似")

    # 使用 LLM 生成更精准的原因（对 top 结果）
    if score >= 50:
        return _llm_similarity_reason(query_text, result)

    return "、".join([r for r in reasons if r]) or "岗位相似"


def _llm_similarity_reason(query_text: str, result: dict) -> str:
    """给 top 结果用 LLM 生成精准的相似原因（单行，15字以内）"""
    try:
        from langchain_deepseek import ChatDeepSeek
        llm = ChatDeepSeek(
            model="deepseek-chat",
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            api_base="https://api.deepseek.com",
            temperature=0.1,
            max_tokens=64,
        )

        jd_summary = (
            f"公司={result.get('company', '?')}, "
            f"岗位={result.get('role', '?')}, "
            f"技术栈={result.get('tech_stack', [])}, "
            f"级别={result.get('level', '')}"
        )
        prompt = f"这两个岗位为什么相似？用一句话（15字以内）回答。\n\n目标JD: {query_text[:300]}\n历史JD: {jd_summary}"
        response = llm.invoke(prompt)
        return response.content.strip()[:30]
    except Exception:
        return "岗位相似"


# ============================================================
# 简历向量存储（用于重新匹配）
# ============================================================

def _load_resume_vectors() -> tuple:
    """加载简历向量矩阵和元数据"""
    _ensure_dir()
    vec_path = VECTOR_DIR / "resume_vectors.npy"
    meta_path = VECTOR_DIR / "resume_metadata.json"

    if vec_path.exists() and meta_path.exists():
        vectors = np.load(vec_path)
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        return vectors, metadata
    return np.empty((0, 512)), []


def _save_resume_vectors(vectors: np.ndarray, metadata: list):
    _ensure_dir()
    np.save(VECTOR_DIR / "resume_vectors.npy", vectors)
    (VECTOR_DIR / "resume_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def add_resume_vector(resume_id: str, resume_text: str, label: str = ""):
    """索引一份简历到向量库"""
    vectors, metadata = _load_resume_vectors()
    embedding = embed_text(resume_text)

    if vectors.size == 0:
        vectors = embedding.reshape(1, -1)
    else:
        vectors = np.vstack([vectors, embedding.reshape(1, -1)])

    metadata.append({
        "id": resume_id,
        "label": label,
        "indexed_at": datetime.now().isoformat(),
    })

    _save_resume_vectors(vectors, metadata)
    print(f"[VectorStore] 简历已索引: {resume_id} (总数={len(metadata)})")


def rematch_resume_against_jds(resume_text: str, top_k: int = 5) -> list:
    """
    用一份简历重新匹配所有已存储的 JD，返回契合度排序。
    这是"简历更新后重新匹配"的核心功能。
    """
    return search_similar_jds(resume_text, top_k=top_k, min_score=0.2)


def rebuild_index_from_history():
    """
    从 data/jd_history.json 重建向量索引。
    用于数据迁移或在索引损坏时重建。
    """
    from tools.jd_store import _ensure_store
    store = _ensure_store()
    jds = store.get("jds", [])

    if not jds:
        print("[VectorStore] 历史库为空，跳过重建")
        return

    texts = []
    metas = []
    for jd in jds:
        jd_text = jd.get("jd_text", "")
        if jd_text:
            texts.append(jd_text)
            meta = jd.get("meta", {})
            metas.append({
                "id": jd["id"],
                "created_at": jd.get("created_at", ""),
                "company": meta.get("company", ""),
                "role": meta.get("role", ""),
                "level": meta.get("level", ""),
                "tech_stack": meta.get("tech_stack", []),
                "fit_score": jd.get("fit_score", 0),
                "one_line": meta.get("one_line_summary", ""),
            })

    if texts:
        print(f"[VectorStore] 正在重建索引: {len(texts)} 条 JD...")
        embeddings = embed_batch(texts)
        vectors = np.array(embeddings)
        _save_jd_vectors(vectors, metas)
        print(f"[VectorStore] 索引重建完成: {len(metas)} 条")


def get_index_stats() -> dict:
    """获取向量库统计信息"""
    jd_vectors, jd_metadata = _load_jd_vectors()
    resume_vectors, resume_metadata = _load_resume_vectors()

    return {
        "jd_count": len(jd_metadata),
        "resume_count": len(resume_metadata),
        "vector_dim": 512,
        "model": "BAAI/bge-small-zh-v1.5",
    }
