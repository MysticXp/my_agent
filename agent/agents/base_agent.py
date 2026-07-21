# agent/agents/base_agent.py
# 所有专用 Agent 的基类
#

import os
from abc import ABC, abstractmethod
from typing import Any, Optional

from langchain_deepseek import ChatDeepSeek

from agent.state import JobState
from agent.token_tracker import token_tracker

class BaseAgent(ABC):
    """Agent 基类：提供标准化的 LLM 调用 + 自动 Token 追踪

    所有专用 Agent 继承此类，只需实现 run() 方法。
    _call_llm() 自动记录 token 消耗，子类无需关心追踪逻辑。

    Example:
        class MyAgent(BaseAgent):
            def __init__(self):
                super().__init__(name="MyAgent", temperature=0.3)

            def run(self, state, **kwargs):
                response = self._call_llm("你的 prompt")
                state["result"] = response.content
                return state
    """

    def __init__(self, name: str, temperature: float = 0.3):
        """
        参数:
            name: Agent 名称（用于追踪和日志）
            temperature: LLM 温度参数（每个 Agent 可不同）
        """
        self.name = name
        self.temperature = temperature
        self._llm: Optional[ChatDeepSeek] = None

    # ---- LLM 管理 ----

    def _get_llm(self) -> ChatDeepSeek:
        """懒加载 LLM 实例"""
        if self._llm is None:
            self._llm = ChatDeepSeek(
                model="deepseek-chat",
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                api_base="https://api.deepseek.com",
                temperature=self.temperature,
                max_tokens=4096,
            )
        return self._llm

    def _call_llm(self, prompt: str) -> Any:
        """调用 LLM 并自动追踪 token 消耗

        所有子类都应该通过此方法调用 LLM，而非直接调 self._llm.invoke()
        """
        llm = self._get_llm()
        response = llm.invoke(prompt)
        token_tracker.track(response, agent_name=self.name)
        return response

    # ---- 子类必须实现的接口 ----

    @abstractmethod
    def run(self, state: JobState, **kwargs) -> Any:
        """执行 Agent 的核心任务

        参数:
            state: 当前工作流状态
            **kwargs: 可选额外参数

        返回:
            处理结果（通常直接更新 state）
        """
        pass
