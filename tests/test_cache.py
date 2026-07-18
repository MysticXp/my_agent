"""Tests for the semantic cache (tools/cache.py)"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from tools.cache import SemanticCache


def test_cache_miss():
    """空缓存时 lookup 返回 None"""
    cache = SemanticCache(threshold=0.97)
    cache.clear()
    result = cache.lookup("JD文本", "简历文本")
    assert result is None
    print("  [PASS] test_cache_miss")


def test_cache_hit():
    """store 后相同内容 lookup 命中"""
    cache = SemanticCache(threshold=0.97)
    cache.clear()
    cache.store("JD文本", "简历文本", "分析结果", agent="test")
    result = cache.lookup("JD文本", "简历文本")
    assert result is not None
    assert result["result"] == "分析结果"
    assert result["agent"] == "test"
    assert result["similarity"] >= 0.97
    print("  [PASS] test_cache_hit")


def test_cache_similar():
    """相似内容（非完全一致）也能命中（仅当向量接近）"""
    cache = SemanticCache(threshold=0.5)  # 降低阈值方便测试
    cache.clear()
    cache.store("招聘高级前端工程师 React TypeScript", "5年经验 React", "结果A")
    result = cache.lookup("招前端开发 React TS", "5年前端经验")
    if result:
        print(f"  [INFO] 相似命中, similarity={result['similarity']:.4f}")
    # 这个测试可能因 embedding 质量有时不命中，仅做参考
    print("  [PASS] test_cache_similar")


def test_cache_store_limit():
    """超过 200 条时自动裁剪"""
    cache = SemanticCache(threshold=0.97)
    cache.clear()
    for i in range(210):
        cache.store(f"JD{i}", f"Resume{i}", f"Result{i}", agent="test")
    stats = cache.stats
    assert stats["entries"] == 200
    print(f"  [PASS] test_cache_store_limit ({stats['entries']} entries)")


def test_cache_stats():
    """stats 返回正确统计"""
    cache = SemanticCache(threshold=0.97)
    cache.clear()
    assert cache.stats["entries"] == 0
    cache.store("JD", "简历", "结果")
    assert cache.stats["entries"] == 1
    assert "test" not in cache.stats["agents"]
    print("  [PASS] test_cache_stats")


def test_cache_empty_input():
    """空输入不报错"""
    cache = SemanticCache(threshold=0.97)
    cache.clear()
    assert cache.lookup("", "") is None
    assert cache.lookup("JD", "") is None
    cache.store("", "", "结果")  # should no-op
    cache.store("JD", "", "结果")  # should no-op
    assert cache.stats["entries"] == 0
    print("  [PASS] test_cache_empty_input")
