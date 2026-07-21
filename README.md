# 🎯 CareerCopilot — 求职 AI 助手

> 基于 LangGraph Multi-Agent 架构的智能求职系统，集 JD 匹配分析、简历优化、模拟面试于一体。

---

## 系统架构

```
用户输入 (简历 + JD)
       │
       ▼
┌─────────────┐
│   Planner   │  → 解析需求，生成执行计划
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Executor   │  → 调用专用 Agent 执行各步骤
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────────┐
│ Fit Review  │────→│   Interviewer    │  HITL 中断，等待用户决策
│  (HITL)     │     └────────┬─────────┘
└──────┬──────┘              │
       │                     ▼
       │              ┌─────────────┐
       └─────────────→│  Aggregator │  → 汇总结果，生成报告
                      └─────────────┘
```

### 核心工作流

1. **Planner** — 解析用户需求 + RAG 检索相似历史 JD，生成结构化执行计划
2. **Executor** — 按计划调用各专用 Agent 执行分析
3. **Fit Review** — 展示契合度分析结果，中断等待用户决策（是否继续面试）
4. **Interviewer** — 逐题模拟面试，评估回答质量，给出反馈
5. **Aggregator** — 汇总所有结果，生成最终求职报告

### Multi-Agent 架构

系统拆分为 3 个专用 Agent，每个有独立的 LLM 实例和 temperature 配置：

| Agent | Temperature | 职责 |
|-------|------------|------|
| ResumeAnalyzer | 0.2 | JD-简历契合度分析（低温度保证一致性） |
| QuestionGenerator | 0.7 | 面试题生成（高温度保证多样性） |
| InterviewEvaluator | 0.4 | 回答评估与评分 |

---

## 技术栈

| 技术 | 用途 |
|------|------|
| **LangGraph** 1.x | Agent 编排，支持 StateGraph + interrupt() + Checkpoint |
| **DeepSeek** | LLM 推理，OpenAI 兼容 API |
| **FastAPI** | 后端框架 + SSE 流式推送 |
| **React 18** | 前端界面 |
| **BGE-small-zh-v1.5** | 本地向量嵌入（零外部依赖） |
| **sse-starlette** | SSE 服务端推送 |

---

## 功能特性

### SSE 流式响应
- 后端 `agent.astream_events()` + 前端 `ReadableStream` 逐 token 推送
- 节点进度实时展示，首 token 延迟 < 2s

### 语义缓存
- BGE embedding 计算 (JD+简历) 语义相似度
- 命中率约 40-60%，直接返回缓存结果，不重复调 LLM

### Token 成本追踪
- 全局 TokenTracker 记录每次 LLM 调用的 token 消耗
- 按 Agent 分解成本，JSONL 持久化
- 支持 DeepSeek 定价模型

### RAG 控制
- 用户提供 JD 时不触发向量检索（以用户输入为准）
- 仅当无 JD 时检索历史相似岗位
- 写入前去重，避免重复索引

### Human-in-the-Loop
- LangGraph `interrupt()` 在契合度审查节点暂停
- 用户决策通过 `Command(resume=...)` 从断点恢复

### 循环防护
- `max_steps=5` 硬限制
- 条件路由检测状态机状态提前终止
- 每个 LLM 调用独立 timeout

---

## 快速启动

```bash
# 后端
pip install -r requirements_full.txt
cp .env.example .env  # 填入 DEEPSEEK_API_KEY
python main.py

# 前端
cd frontend
npm install
npm start
```

---

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/chat/stream` | SSE 流式聊天 |
| `POST` | `/chat` | 同步聊天（兼容） |
| `POST` | `/upload-resume` | PDF 简历上传解析 |
| `GET` | `/jd-history` | 历史 JD 列表 |
| `POST` | `/rematch` | 简历重新匹配历史 JD |
| `GET` | `/vector-stats` | 向量库统计 |

---

## 测试

```bash
pytest tests/ -v  # 69 个测试
```

*Built with LangGraph, DeepSeek, FastAPI & React*
