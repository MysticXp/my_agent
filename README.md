# 🎯 My Agent — 求职 AI 助手

> 基于 LangGraph Multi-Agent 架构的智能求职系统，集 JD 匹配分析、简历优化、模拟面试于一体。

---

## ✨ 核心亮点

- **🧠 Multi-Agent 架构** — 5 个独立 Agent 节点：Planner → Executor → Fit Review (HITL) → Interviewer → Aggregator，每个 Agent 有独立的 LLM 实例与 temperature 配置
- **🔄 Human-in-the-Loop** — 使用 LangGraph `interrupt()` 机制，在契合度审查节点暂停流程，等待用户决策后再继续
- **🔍 RAG Pipeline** — 基于 BGE-small-zh-v1.5 的本地向量检索，自动匹配历史相似 JD 与面试题
- **💰 Token 成本追踪** — 全局 TokenTracker 记录每次 LLM 调用的消耗，按 Agent 分解成本
- **🛡️ 循环防护** — `max_steps=5` + 条件路由，防止死循环
- **📦 Checkpoint 持久化** — LangGraph MemorySaver 支持中断恢复

---

## 📁 目录结构

```
my_agent/
├── agent/                    # LangGraph Agent 核心
│   ├── agents/               # Multi-Agent 架构（2026-07 新增）
│   │   ├── base_agent.py     # Agent 基类（统一 LLM + Token 追踪）
│   │   ├── resume_analyzer.py    # 简历分析 Agent
│   │   ├── question_generator.py # 出题 Agent
│   │   └── interview_evaluator.py# 面试评估 Agent
│   ├── graph.py              # LangGraph 状态图定义与编译
│   ├── nodes.py              # 图节点函数（规划/执行/汇总/条件路由）
│   ├── state.py              # TypedDict 状态定义
│   ├── prompts.py            # 各节点 Prompt 模板
│   └── token_tracker.py      # Token 成本追踪系统
├── tools/                    # Agent 调用的工具集
│   ├── jd_resume_analyzer.py # JD-简历契合度分析
│   ├── interview.py          # 模拟面试题生成
│   ├── resume_optimizer.py   # 简历优化建议
│   ├── jd_retriever.py       # 历史 JD 检索
│   ├── jd_store.py           # JD 历史存储
│   ├── question_store.py     # 面试题历史存储
│   ├── vector_store.py       # BGE 向量索引
│   ├── pdf_parser.py         # PDF 简历解析
│   └── storage.py            # 通用持久化
├── frontend/                 # React 前端
│   ├── src/
│   │   ├── components/       # UI 组件
│   │   │   ├── ChatInput.js
│   │   │   ├── FitAnalysis.js
│   │   │   ├── FitReviewPanel.js
│   │   │   ├── InterviewPanel.js
│   │   │   ├── Report.js
│   │   │   └── StatusBadge.js
│   │   ├── api/client.js     # 后端 API 封装
│   │   └── App.js            # 主应用入口
│   └── package.json
├── data/                     # 运行时数据（JSON 存储 + 向量索引）
├── tests/                    # 单元测试
│   ├── test_token_tracker.py
│   └── test_interview_evaluator.py
├── main.py                   # FastAPI 后端入口
├── .env                      # 环境变量（API Key）
├── .env.example              # 环境变量模板
├── requirements_full.txt     # Python 依赖
└── setup.sh                  # 一键启动脚本
```

---

## 🚀 快速启动

### 前置条件

- Python 3.10+
- Node.js 18+
- DeepSeek API Key

### 后端

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 DEEPSEEK_API_KEY

# 2. 安装依赖
pip install -r requirements_full.txt

# 3. 启动后端（默认 8000 端口）
python main.py
# 或
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端

```bash
cd frontend
npm install
npm start
# 浏览器打开 http://localhost:3000
```

---

## 📡 API 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/chat` | 核心对话接口（首次启动/中断恢复） |
| `POST` | `/upload-resume` | PDF 简历上传解析 |
| `GET` | `/jd-history` | 历史 JD 列表 |
| `DELETE` | `/jd-history/{id}` | 删除指定历史 JD |
| `POST` | `/rematch` | 用新简历重新匹配所有历史 JD |
| `POST` | `/rebuild-index` | 从历史记录重建向量索引 |
| `GET` | `/vector-stats` | 向量库统计信息 |
| `GET` | `/question-history` | 历史面试题（按岗位/公司筛选） |
| `GET` | `/` | 服务健康检查 |

---

## 🏗️ 技术栈选型

| 技术 | 用途 | 选型理由 |
|------|------|----------|
| **LangGraph** 1.2 | Agent 编排 | 原生支持 StateGraph + interrupt() + Checkpoint，比 LangChain Agent 更灵活 |
| **DeepSeek** | LLM | 性价比高（¥0.5/M 输入 tokens），中文能力强，兼容 OpenAI API |
| **FastAPI** | 后端框架 | 原生异步支持，自动生成 OpenAPI 文档，Pydantic 校验 |
| **React 18** | 前端 | 组件化 UI，配合 axios 与后端交互 |
| **BGE-small-zh-v1.5** | 向量嵌入 | 本地运行零成本，中文语义匹配效果好 |
| **MemorySaver** | 状态持久化 | LangGraph 内置，支持中断恢复与多轮对话 |

---

## ❓ 面试知识点问答

### 为什么选 LangGraph 而不是 LangChain Agent？

LangChain Agent 是"工具调用 + ReAct 循环"的封装，适合简单的单 Agent 场景。而我们的系统需要多阶段状态流转（规划 → 执行 → 审查 → 面试 → 汇总），中间还有 HITL 中断。LangGraph 的 StateGraph 允许你精确控制每个节点的输入输出和路由条件，`interrupt()` 更是其他框架没有的原生能力。

### 怎么防止死循环？

三个层面：① `max_steps=5` 硬限制，超过自动终止；② 条件路由（`should_continue`）检测状态机状态，finished/error 状态直接结束；③ 每个 LLM 调用有独立的 timeout。

### RAG 是怎么做的？

使用 BGE-small-zh-v1.5 将 JD 文本转为向量，存入本地 FAISS 索引。每次用户提交新 JD 时，做向量相似度检索，召回 top-k 条历史 JD，将结果注入 Planner 和 Fit Review 的上下文中。所有历史数据存储在 `data/` 目录，无外部依赖。

### 多轮对话状态怎么管理？

LangGraph 的 `MemorySaver` 作为 checkpointer，每次 `agent.invoke()` 自动保存状态。中断后通过 `Command(resume=...)` 恢复，从断点继续执行。每个 session 对应一个 `thread_id`，实现用户隔离。

### Multi-Agent 比单 Agent 好在哪？

单 Agent 的 prompt 是"大杂烩"——既要分析又要出题还要评分，prompt 越长注意力越分散。拆成独立 Agent 后：① 每个 Agent prompt 短而精（50 行以内）；② 可独立测试（给分析 Agent 扔 10 个 JD 看准确率）；③ 错误隔离（出题 Agent 崩了不影响分析 Agent）；④ 易扩展（加新 Agent 不碰主流程）。

---

## 💰 Token 成本参考

每次完整对话（分析 + 优化 + 出题 + 评估）约消耗 8K-15K tokens，成本约 ¥0.01-¥0.03。
按 Agent 分解：

| Agent | 平均 tokens/次 | 温度 |
|-------|---------------|------|
| ResumeAnalyzer | ~3K-5K | 0.2 |
| QuestionGenerator | ~2K-4K | 0.7 |
| InterviewEvaluator | ~1K-2K | 0.4 |
| Planner | ~1K-2K | 0.1 |
| Aggregator | ~1K-2K | 0.5 |

---

## 📝 开发笔记

- **2026-07 Multi-Agent 重构**：从单 Agent 多阶段节点升级为 Multi-Agent 架构，每个专用 Agent 拥有独立的 LLM 实例和 temperature 配置
- **2026-07 Token 追踪**：新增全局 TokenTracker，提供会话级成本统计与 JSONL 日志持久化
- **2026-07 面试评估升级**：InterviewEvaluatorAgent 支持 4 维评分（技术准确性 35% + 逻辑结构 25% + 深度见解 25% + 改进建议 15%）
- **2026-06 初始化**：基于 LangGraph + DeepSeek + React 搭建求职 AI 助手原型

---

*Built with LangGraph, DeepSeek, FastAPI & React*
