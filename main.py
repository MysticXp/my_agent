# main.py
# 这是整个求职Agent的后端启动文件

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
from tools.jd_resume_analyzer import extract_match_score

# 从你的agent文件夹导入我们之前写好的核心函数
from agent.graph import build_job_agent
from agent.state import create_initial_state
from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command


load_dotenv()
# 初始化FastAPI应用
app = FastAPI(title="求职AI助手")

# 解决前端跨域问题（你的HTML页面才能访问这个后端）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有来源
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局配置（用于记忆）
config = {"configurable": {"thread_id": "1"}}
# --- 定义请求和响应的数据格式（Pydantic模型）---
class ChatRequest(BaseModel):
    message: str = ""                      # 首次请求必填，后续回答可选
    resume: Optional[str] = None           # 简历文本
    job_description: Optional[str] = None  # 岗位描述 (JD)
    answer: Optional[str] = None           # 面试回答（恢复中断用）
    user_id: Optional[str] = "default"

class ChatResponse(BaseModel):
    output: str
    status: str
    steps: List[dict] = []

# --- 创建全局Agent实例（只编译一次，提高性能）---
# 注意：这里会读取你.env中的DEEPSEEK_API_KEY
print("[Main] 正在启动求职Agent，初始化LangGraph...")
agent = build_job_agent()
print("[Main] Agent初始化完成！")

# --- 定义API接口 ---
@app.post("/chat")
async def chat(request: ChatRequest):
    """
    核心聊天接口
    接收用户消息和可选简历，返回Agent生成的求职报告
    """
    try:
        # 1. 首次启动 vs 恢复中断
        if request.answer:
            # 恢复中断：用户回答了上一道面试题
            final_state = agent.invoke(
                Command(resume=request.answer),
                config=config
            )
        else:
            # 首次启动：创建初始状态并运行
            state = create_initial_state(
                user_input=request.message,
                resume=request.resume,
                job_description=request.job_description,
            )
            final_state = agent.invoke(state, config=config)

        # 2. 检查是否有中断（契度审查 or 模拟面试等待回答）
        interrupt_list = final_state.get("__interrupt__")
        if interrupt_list:
            interrupt_obj = interrupt_list[0]
            intr_value = interrupt_obj.value
            intr_type = intr_value.get("type", "")

            if intr_type == "fit_review":
                # 契合度审查暂停：返回分析结果 + 评分，等待用户决定是否继续面试
                fit_text = intr_value.get("fit_analysis", "")
                resp = {
                    "status": "fit_review",
                    "fit_analysis": fit_text,
                    "fit_scores": extract_match_score(fit_text) if fit_text else None,
                    "question": intr_value.get("question", ""),
                    "options": intr_value.get("options", []),
                    "output": ""
                }
                print(f"[Main] 返回 fit_review: 等待用户决定是否继续面试")
                return JSONResponse(content=resp)
            else:
                # 面试进行中：从 __interrupt__ 中提取题目信息
                resp = {
                    "status": "interviewing",
                    "question": intr_value["question"],
                    "question_num": intr_value["question_num"],
                    "total": intr_value["total"],
                    "output": ""
                }
                print(f"[Main] 返回 interviewing: question_num={resp['question_num']}, total={resp['total']}")
                return JSONResponse(content=resp)
        else:
            # 面试结束或无需面试
            # 提取契合度评分数据
            fit_analysis_text = final_state.get("jd_resume_analysis") or ""
            fit_scores = extract_match_score(fit_analysis_text) if fit_analysis_text else None

            resp = {
                "status": "finished",
                "output": final_state.get("final_output") or "分析完成",
                "feedback": final_state.get("interview_feedback") or [],
                "fit_analysis": fit_analysis_text,
                "fit_scores": fit_scores
            }
            print(f"[Main] 返回 finished: output 长度={len(resp['output'])}, "
                  f"fit_scores={fit_scores.get('total_score') if fit_scores else 'N/A'}")
            return JSONResponse(content=resp)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent执行出错: {str(e)}")

@app.get("/")
async def root():
    return {"message": "求职AI助手已上线！请访问 /docs 查看接口文档"}

# --- 启动命令（仅供本地调试，实际运行建议用uvicorn命令）---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)