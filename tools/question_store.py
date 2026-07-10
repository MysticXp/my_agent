# tools/question_store.py
# 面试题历史存储：按岗位归类，公司作为辅助标签。纯 JSON 读写，零依赖。
#
# 存储结构 (data/question_history.json):
# {
#   "questions": {
#     "高级前端开发工程师": [
#       {"question": "请解释 React Fiber 架构...", "company": "字节跳动", "created_at": "2026-07-07"},
#       {"question": "字节的价值观是什么...", "company": "字节跳动", "created_at": "2026-07-07"}
#     ],
#     "Java开发工程师": [...]
#   }
# }

import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
STORE_PATH = DATA_DIR / "question_history.json"


def _ensure_store() -> dict:
    """读取或初始化题目历史"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not STORE_PATH.exists():
        init = {"questions": {}}
        STORE_PATH.write_text(json.dumps(init, ensure_ascii=False, indent=2), encoding="utf-8")
        return init
    try:
        return json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return {"questions": {}}


def save_questions(role: str, questions: list, company: str = ""):
    """
    保存一组面试题到历史库（按岗位归类，公司作为标签）。

    参数:
        role: 岗位名称（主 key）
        questions: 题目文本列表
        company: 公司名称（辅助标签）
    """
    if not questions or not role:
        return

    store = _ensure_store()
    role = role.strip()

    if role not in store["questions"]:
        store["questions"][role] = []

    today = datetime.now().isoformat()[:10]
    added = 0
    for q in questions:
        exists = any(
            e.get("question") == q and e.get("company") == company
            for e in store["questions"][role]
        )
        if not exists:
            store["questions"][role].append({
                "question": q,
                "company": company.strip() if company else "",
                "created_at": today,
            })
            added += 1

    STORE_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    total = len(store["questions"][role])
    print(f"[QuestionStore] 岗位={role}: 新增 {added}/{len(questions)} 道题 (总计 {total} 道)")


def get_questions(role: str = "", company: str = "") -> list:
    """
    获取历史题目。
    - 指定 role：只返回该岗位的题
    - 不指定 role：返回所有题
    - 指定 company：在结果中额外标记该公司相关的题

    返回: [{"question": "...", "company": "...", "created_at": "..."}, ...]
    """
    store = _ensure_store()

    if role:
        qs = store["questions"].get(role.strip(), [])
        if company:
            # 排序：该公司相关的题排前面
            c = company.strip()
            qs = sorted(qs, key=lambda x: 0 if x.get("company") == c else 1)
        return qs
    else:
        all_qs = []
        for r, qs in store["questions"].items():
            for q in qs:
                all_qs.append({"role": r, **q})
        all_qs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return all_qs


def build_avoid_context(role: str, company: str = "", existing: list = None,
                        max_history: int = 15) -> str:
    """
    构建"避重"上下文：列出历史题目让 LLM 知道哪些已经出过了。
    只会塞最近 max_history 道题进 context，避免 token 爆炸。
    如果指定了 company，该公司相关题目优先排在前面。

    参数:
        role: 岗位名
        company: 公司名（可选，用于优先排序）
        existing: 本轮已生成的题目列表（避免内部重复）
        max_history: 最多列多少道历史题（默认15）
    """
    history = get_questions(role, company)

    if not history and not existing:
        return ""

    lines = []
    total = len(history)

    if history:
        # 截断：最多取 max_history 道，优先公司匹配的、最近的
        shown = history[:max_history]
        omitted = total - len(shown)

        company_tag = f"（{company}）" if company else ""
        header = f"以下是为 **{role}{company_tag}** 出过的历史题目"
        if total > max_history:
            header += f"（共 {total} 道，仅列出最近 {max_history} 道）"
        else:
            header += f"（共 {total} 道）"
        header += "，请**不要重复**："
        lines.append(header)

        for i, q in enumerate(shown, 1):
            tag = f" [{q['company']}]" if q.get("company") and not company else ""
            lines.append(f"  {i}.{tag} {q['question']}")

        if omitted > 0:
            lines.append(f"  ...（另有 {omitted} 道历史题未列出，也请注意避开）")

    if existing:
        lines.append(f"\n本轮已生成的题目（同样避免重复）：")
        for i, q in enumerate(existing, 1):
            lines.append(f"  {i}. {q}")

    if company and history:
        lines.append(f"\n提示：如果历史题目中缺少关于 **{company}** 公司文化、业务特色相关的问题，可以考虑补充。")

    return "\n".join(lines)


def get_all_roles() -> list:
    """列出所有有题目的岗位"""
    store = _ensure_store()
    return [
        {"role": k, "count": len(v)}
        for k, v in store["questions"].items() if v
    ]


def get_stats() -> dict:
    """统计信息"""
    store = _ensure_store()
    total_qs = sum(len(v) for v in store["questions"].values())
    return {
        "total_questions": total_qs,
        "role_count": len(store["questions"]),
        "roles": get_all_roles(),
    }
