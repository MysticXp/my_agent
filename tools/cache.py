# tools/cache.py
# 语义缓存：对 LLM 调用结果做 embedding 相似度缓存

import os
import json
import hashlib
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
CACHE_FILE = CACHE_DIR / "semantic_cache.json"
SIMILARITY_THRESHOLD = 0.97  # 语义相似度阈值（0-1），越高越严格

def _get_embedding(text: str) -> np.ndarray:
    """复用项目的 BGE embedding 模型生成向量"""
    from tools.vector_store import _get_model, embed_text
    return embed_text(text)

class SemanticCache:
    """语义缓存：基于 embedding 相似度的 LLM 结果缓存

    用法:
        cache = SemanticCache()
        result = cache.lookup(jd_text, resume_text)
        if result is None:
            result = call_llm(...)
            cache.store(jd_text, resume_text, result, agent_name="JD分析")
    """

    def __init__(self, threshold: float = SIMILARITY_THRESHOLD):
        self.threshold = threshold
        self._entries = self._load()

    # ---- 持久化 ----

    def _load(self) -> list:
        """从磁盘加载缓存"""
        try:
            if CACHE_FILE.exists():
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("entries", [])
        except (json.JSONDecodeError, OSError) as e:
            print(f"[Cache] 加载失败（非致命）: {e}")
        return []

    def _save(self):
        """写入磁盘"""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"entries": self._entries, "updated_at": datetime.now().isoformat()},
                      f, ensure_ascii=False, indent=2)

    # ---- 核心操作 ----

    def lookup(self, jd_text: str, resume_text: str) -> Optional[dict]:
        """查询缓存。命中返回 {result, agent, cached_at}，未命中返回 None"""
        if not jd_text or not resume_text:
            return None

        query_vec = _get_embedding(jd_text + " [SEP] " + resume_text)
        best_score = 0.0
        best_entry = None

        for entry in self._entries:
            stored_vec = np.array(entry["embedding"])
            # 余弦相似度（向量已归一化）
            score = float(np.dot(query_vec, stored_vec))
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_entry and best_score >= self.threshold:
            # 命中缓存
            hit_info = {
                "result": best_entry["result"],
                "agent": best_entry.get("agent", "unknown"),
                "cached_at": best_entry.get("cached_at", ""),
                "similarity": round(best_score, 4),
            }
            print(f"[Cache] 命中! 相似度={best_score:.4f}, agent={best_entry.get('agent')}")
            return hit_info

        if best_entry:
            print(f"[Cache] 未命中 (最高相似度={best_score:.4f}, 阈值={self.threshold})")
        else:
            print(f"[Cache] 缓存为空")
        return None

    def store(self, jd_text: str, resume_text: str, result: str, agent: str = "unknown"):
        """存入缓存"""
        if not jd_text or not resume_text or not result:
            return

        embedding = _get_embedding(jd_text + " [SEP] " + resume_text)

        self._entries.append({
            "embedding": embedding.tolist(),
            "result": result,
            "agent": agent,
            "cached_at": datetime.now().isoformat(),
        })

        # 限制缓存大小（保留最近 200 条）
        if len(self._entries) > 200:
            self._entries = self._entries[-200:]

        self._save()
        print(f"[Cache] 已缓存 #{len(self._entries)} ({agent})")

    def clear(self):
        """清空缓存"""
        self._entries = []
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
        print("[Cache] 已清空")

    @property
    def stats(self) -> dict:
        """缓存统计"""
        return {
            "entries": len(self._entries),
            "threshold": self.threshold,
            "agents": list(set(e.get("agent", "?") for e in self._entries)),
        }

# 全局单例
_cache: Optional[SemanticCache] = None

def get_cache() -> SemanticCache:
    global _cache
    if _cache is None:
        _cache = SemanticCache()
    return _cache
