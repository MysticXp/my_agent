# agent/token_tracker.py
# Token 成本追踪系统（生产级）
#
# 面试话术：
# "我们在生产环境遇到了 token 成本失控的问题，所以我实现了这套追踪系统。
#  它让我能精确知道每次对话花了多少钱，哪类任务最贵，
#  也为后续的缓存策略和模型路由提供了数据支撑。"
#
# 面试考点：
# - 知道 token 计费模型（输入 vs 输出价格不同！这是常见坑）
# - 知道 DeepSeek 的价格（面试官可能会问"你们大概多少钱一次请求"）
# - Singleton 模式追踪全会话

import os
import json
import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from pathlib import Path

# ============================================================
# 定价表（元/1K tokens）
# 面试官可能问：为什么输入和输出价格不一样？
# 答：输出 tokens 的生成需要自回归计算，计算量远大于输入的前向传播
# ============================================================
MODEL_PRICING = {
    "deepseek-chat": {
        "input": 0.0005,   # ¥0.5 / 1M tokens → ¥0.0005 / 1K tokens
        "output": 0.002,   # ¥2.0 / 1M tokens → ¥0.002 / 1K tokens
    },
    "deepseek-reasoner": {
        "input": 0.0005,
        "output": 0.002,
    },
}


@dataclass
class UsageRecord:
    """单次 LLM 调用的用量记录"""
    agent: str = "unknown"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_cny: float = 0.0
    timestamp: str = ""
    model: str = "deepseek-chat"


class TokenTracker:
    """全局 Token 追踪器（Singleton）

    追踪整个 session 中所有 LLM 调用的 token 消耗和成本。
    提供实时统计，支持持久化到日志文件。

    用法:
        from agent.token_tracker import token_tracker

        # 在 LLM 调用后记录
        token_tracker.track(response, agent_name="ResumeAnalyzer")

        # 获取摘要
        print(token_tracker.summary())
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.records: List[UsageRecord] = []
        self.session_start = datetime.now().isoformat()

    # ---- 核心追踪方法 ----

    def track(
        self,
        response,
        agent_name: str = "unknown",
        model: str = "deepseek-chat",
    ) -> UsageRecord:
        """从 LangChain LLM 响应中提取 token 用量并记录

        参数:
            response: LangChain LLMResult / AIMessage（有 response_metadata）
            agent_name: 调用来源的 agent 名称
            model: 模型名称（用于定价）
        """
        # 从 response_metadata 中提取 token 用量
        metadata = getattr(response, "response_metadata", None) or {}
        usage = metadata.get("token_usage", {}) or {}

        prompt = int(usage.get("prompt_tokens", 0) or 0)
        completion = int(usage.get("completion_tokens", 0) or 0)

        # 兜底：某些 response 结构不同
        if prompt == 0 and completion == 0:
            # 尝试从 llm_output 提取 (langchain 的 LLMResult)
            llm_output = getattr(response, "llm_output", None) or {}
            usage = llm_output.get("token_usage", {}) or {}
            prompt = int(usage.get("prompt_tokens", 0) or 0)
            completion = int(usage.get("completion_tokens", 0) or 0)

        # 计算成本
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["deepseek-chat"])
        cost = (prompt / 1000 * pricing["input"]) + (completion / 1000 * pricing["output"])

        record = UsageRecord(
            agent=agent_name,
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
            cost_cny=round(cost, 6),
            timestamp=datetime.now().isoformat(),
            model=model,
        )

        self.records.append(record)
        return record

    def track_raw(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        agent_name: str = "unknown",
        model: str = "deepseek-chat",
    ) -> UsageRecord:
        """手动记录用量（当 response_metadata 不可用时）"""
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["deepseek-chat"])
        cost = (prompt_tokens / 1000 * pricing["input"]) + (completion_tokens / 1000 * pricing["output"])

        record = UsageRecord(
            agent=agent_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_cny=round(cost, 6),
            timestamp=datetime.now().isoformat(),
            model=model,
        )

        self.records.append(record)
        return record

    # ---- 统计方法 ----

    def summary(self) -> dict:
        """获取当前 session 的完整用量统计"""
        if not self.records:
            return {
                "total_calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_cny": 0.0,
                "agent_breakdown": {},
                "recent_calls": [],
            }

        # 按 agent 分组统计
        agent_breakdown: Dict[str, dict] = {}
        for r in self.records:
            if r.agent not in agent_breakdown:
                agent_breakdown[r.agent] = {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "cost_cny": 0.0,
                }
            b = agent_breakdown[r.agent]
            b["calls"] += 1
            b["input_tokens"] += r.prompt_tokens
            b["output_tokens"] += r.completion_tokens
            b["total_tokens"] += r.total_tokens
            b["cost_cny"] += r.cost_cny

        # 总统计
        total_input = sum(r.prompt_tokens for r in self.records)
        total_output = sum(r.completion_tokens for r in self.records)
        total_cost = sum(r.cost_cny for r in self.records)

        # 最近 10 次调用
        recent = [
            {
                "agent": r.agent,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "total_tokens": r.total_tokens,
                "cost_cny": round(r.cost_cny, 6),
                "timestamp": r.timestamp,
            }
            for r in self.records[-10:]
        ]

        # 四舍五入 agent breakdown 的 cost
        for agent, b in agent_breakdown.items():
            b["cost_cny"] = round(b["cost_cny"], 4)

        return {
            "total_calls": len(self.records),
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_tokens": total_input + total_output,
            "estimated_cost_cny": round(total_cost, 4),
            "agent_breakdown": agent_breakdown,
            "recent_calls": recent,
        }

    def get_formatted_summary(self) -> str:
        """生成人类可读的 token 消耗报告（用于加到回复末尾）"""
        s = self.summary()
        lines = [
            "---",
            "💰 **本次对话 Token 消耗统计**",
            f"- 总调用次数: {s['total_calls']} 次",
            f"- 输入 Tokens: {s['input_tokens']:,}",
            f"- 输出 Tokens: {s['output_tokens']:,}",
            f"- 总 Tokens: {s['total_tokens']:,}",
            f"- 预估成本: ¥{s['estimated_cost_cny']:.4f}",
        ]

        # Agent 明细
        if s["agent_breakdown"]:
            lines.append("")
            lines.append("**按 Agent 分解：**")
            for agent, b in sorted(s["agent_breakdown"].items()):
                pct = (b["cost_cny"] / s["estimated_cost_cny"] * 100) if s["estimated_cost_cny"] > 0 else 0
                lines.append(f"- {agent}: {b['calls']} 次调用, {b['total_tokens']:,} tokens, ¥{b['cost_cny']:.4f} ({pct:.0f}%)")

        return "\n".join(lines)

    def save_to_file(self, filepath: str = "data/token_usage.jsonl"):
        """追加写入日志文件（可用于成本分析仪表盘）"""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        entries = []
        for r in self.records:
            entries.append(json.dumps({
                "agent": r.agent,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "total_tokens": r.total_tokens,
                "cost_cny": r.cost_cny,
                "timestamp": r.timestamp,
                "model": r.model,
            }, ensure_ascii=False))

        path.write_text("\n".join(entries), encoding="utf-8")

    def clear(self):
        """清空当前 session 的记录"""
        self.records = []
        self.session_start = datetime.now().isoformat()


# ============================================================
# 全局单例（整个应用共享一个 tracker）
# ============================================================
token_tracker = TokenTracker()
