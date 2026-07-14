# main.py
# 这是整个求职Agent的后端启动文件

import os
import json
import asyncio
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
from tools.jd_resume_analyzer import extract_match_score
from tools.pdf_parser import parse_pdf_to_text, get_pdf_metadata
from tools.jd_store import get_all_jds, delete_jd
from tools.vector_store import rematch_resume_against_jds, rebuild_index_from_history, get_index_stats
from tools.question_store import get_questions as get_history_questions, get_all_roles, get_stats as get_question_stats

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
    company: Optional[str] = None          # 公司名称
    role: Optional[str] = None             # 岗位名称
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

# ============================================================
# SSE 流式端点（新！支持逐 token 推送）
# ============================================================

# 节点名 → 中文描述映射
NODE_LABELS = {
    "planner": "分析需求",
    "executor": "执行任务",
    "fit_review": "契合度审查",
    "interviewer": "模拟面试",
    "aggregator": "生成报告",
}

async def _stream_agent(input_data: dict, is_resume: bool = False):
    """运行 agent.astream_events()，输出节点事件 + token 事件"""
    final_state = {}
    seen_interrupt = False

    try:
        if is_resume:
            agen = agent.astream_events(
                Command(resume=input_data["answer"]),
                config=config, version="v2",
            )
        else:
            agen = agent.astream_events(create_initial_state(
                user_input=input_data["message"],
                resume=input_data.get("resume"),
                job_description=input_data.get("job_description"),
                company=input_data.get("company"),
                role=input_data.get("role"),
            ), config=config, version="v2")

        async for event in agen:
            evt = event["event"]
            name = event.get("name", "")

            # ---- 节点开始/结束 ----
            if evt == "on_chain_start" and name in NODE_LABELS:
                yield {"event": "node_start", "data": json.dumps(
                    {"node": name, "label": NODE_LABELS[name]}, ensure_ascii=False)}
                continue

            if evt == "on_chain_end" and name in NODE_LABELS:
                yield {"event": "node_end", "data": json.dumps(
                    {"node": name}, ensure_ascii=False)}
                continue

            # ---- 逐 token 流（来自 aggregator 的 stream() 调用） ----
            if evt == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield {"event": "token", "data": json.dumps(
                        {"token": chunk.content}, ensure_ascii=False)}
                continue

            # ---- 状态更新（含 interrupt） ----
            if evt == "values" or evt == "on_chain_stream":
                vals = event.get("data", {})
                if isinstance(vals, dict):
                    # on_chain_stream 的 state 在 event["data"]["chunk"] 里！
                    if "chunk" in vals:
                        vals = vals["chunk"]
                    elif "values" in vals:
                        vals = vals["values"]
                    if isinstance(vals, dict):
                        final_state.update(vals)
                        il = vals.get("__interrupt__")
                    if il and not seen_interrupt:
                        seen_interrupt = True
                        for intr in il:
                            v = intr.value if hasattr(intr, "value") else intr
                            t = v.get("type", "")
                            if t == "fit_review":
                                yield {"event": "interrupt", "data": json.dumps({
                                    "type": "fit_review",
                                    "fit_analysis": v.get("fit_analysis", ""),
                                    "fit_scores": extract_match_score(v.get("fit_analysis", "")) if v.get("fit_analysis") else None,
                                    "similar_jds": v.get("similar_jds", []),
                                    "similar_questions": v.get("similar_questions", []),
                                    "question": v.get("question", "契合度分析已完成，是否继续进行模拟面试？"),
                                    "options": v.get("options", []),
                                }, ensure_ascii=False)}
                            elif t == "interview":
                                yield {"event": "interrupt", "data": json.dumps({
                                    "type": "interview",
                                    "question": v.get("question", ""),
                                    "question_num": v.get("question_num", 1),
                                    "total": v.get("total", 5),
                                }, ensure_ascii=False)}
                        return

        # ---- 完成 ----
        fa = final_state.get("jd_resume_analysis") or ""
        yield {"event": "done", "data": json.dumps({
            "status": "finished",
            "output": final_state.get("final_output") or "分析完成",
            "feedback": final_state.get("interview_feedback") or [],
            "fit_analysis": fa,
            "fit_scores": extract_match_score(fa) if fa else None,
            "similar_jds": final_state.get("similar_jds") or [],
            "similar_questions": final_state.get("similar_questions") or [],
            "token_usage": final_state.get("token_usage") or {},
        }, ensure_ascii=False)}

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[SSE Error] {e}\n{tb}")
        yield {"event": "error", "data": json.dumps({"error": str(e)}, ensure_ascii=False)}


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    SSE 流式聊天接口（手动格式化，不依赖 sse-starlette）。
    """
    is_resume = bool(request.answer)
    input_data = request.model_dump() if hasattr(request, "model_dump") else request.dict()

    async def event_stream():
        async for event in _stream_agent(input_data, is_resume=is_resume):
            yield f"event: {event['event']}\ndata: {event['data']}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ============================================================
# 原有同步接口（保留兼容）
# ============================================================

@app.post("/chat")
async def chat(request: ChatRequest):
    """
    核心聊天接口（同步版）
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
                company=request.company,
                role=request.role,
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
                similar = intr_value.get("similar_jds", [])
                similar_qs = intr_value.get("similar_questions", [])

                # 构建带 JD 简讯的提示消息
                question = intr_value.get("question", "契合度分析已完成，是否继续进行模拟面试？")
                if similar:
                    jd_lines = ["\n\n📚 **向量库匹配到的历史JD：**"]
                    for jd in similar[:3]:
                        company = jd.get("company", "?")
                        role = jd.get("role", "?")
                        score = jd.get("score", 0)
                        reason = jd.get("similarity_reason", "")
                        jd_lines.append(f"- **{company}** — {role}（相似度 {score}%）")
                        if reason:
                            jd_lines.append(f"  _{reason}_")
                    question = question + "\n".join(jd_lines)
                if similar_qs:
                    q_lines = ["\n\n🎯 **历史面试题（同岗位）：**"]
                    for q in similar_qs[:5]:
                        c = q.get("company", "")
                        tag = f" [{c}]" if c else ""
                        q_lines.append(f"-{tag} {q.get('question', '')}")
                    question = question + "\n".join(q_lines)

                resp = {
                    "status": "fit_review",
                    "fit_analysis": fit_text,
                    "fit_scores": extract_match_score(fit_text) if fit_text else None,
                    "similar_jds": similar,
                    "similar_questions": similar_qs,
                    "question": question,
                    "options": intr_value.get("options", []),
                    "output": ""
                }
                print(f"[Main] 返回 fit_review: 等待用户决定是否继续面试 (similar_jds={len(similar)}, similar_qs={len(similar_qs)})")
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

            # 获取 Token 消耗统计
            token_usage = final_state.get("token_usage") or {}

            resp = {
                "status": "finished",
                "output": final_state.get("final_output") or "分析完成",
                "feedback": final_state.get("interview_feedback") or [],
                "fit_analysis": fit_analysis_text,
                "fit_scores": fit_scores,
                "similar_jds": final_state.get("similar_jds") or [],
                "similar_questions": final_state.get("similar_questions") or [],
                "token_usage": token_usage,  # 面试考点：生产环境成本控制
            }
            print(f"[Main] 返回 finished: output 长度={len(resp['output'])}, "
                  f"fit_scores={fit_scores.get('total_score') if fit_scores else 'N/A'}")
            return JSONResponse(content=resp)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent执行出错: {str(e)}")


# ============================================================
# 其他接口
# ============================================================

@app.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    """
    PDF 简历上传解析接口。
    接收一个 PDF 文件，提取文本内容并返回。
    """
    # 校验文件类型
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="仅支持 PDF 文件，请上传 .pdf 格式的简历"
        )

    # 校验文件大小 (10MB 上限)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="文件大小超过 10MB 限制，请压缩后重新上传"
        )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="文件内容为空")

    try:
        # 解析 PDF
        text = parse_pdf_to_text(content, file.filename)
        meta = get_pdf_metadata(content)

        print(f"[Upload] 解析成功: {file.filename}, {meta['pages']}页, {len(text)}字符")
        return JSONResponse(content={
            "status": "ok",
            "filename": file.filename,
            "pages": meta["pages"],
            "text": text,
            "char_count": len(text),
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[Upload] 解析失败: {e}")
        raise HTTPException(status_code=500, detail=f"PDF解析失败: {str(e)}")


@app.get("/jd-history")
async def list_jd_history():
    """获取所有历史 JD 列表（摘要，不含全文）"""
    try:
        jds = get_all_jds()
        return JSONResponse(content={"status": "ok", "count": len(jds), "jds": jds})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取JD历史失败: {str(e)}")


@app.delete("/jd-history/{jd_id}")
async def remove_jd(jd_id: str):
    """删除指定的历史 JD（同时清理向量索引）"""
    success = delete_jd(jd_id)
    if success:
        return JSONResponse(content={"status": "ok", "message": f"已删除 {jd_id}"})
    raise HTTPException(status_code=404, detail=f"未找到 JD: {jd_id}")


@app.post("/rematch")
async def rematch_resume(request: ChatRequest):
    """用简历文本与所有历史 JD 做向量相似度计算"""
    resume = request.resume or request.message
    if not resume or len(resume) < 20:
        raise HTTPException(status_code=400, detail="简历文本太短（至少20字符），请提供完整简历")

    try:
        results = rematch_resume_against_jds(resume, top_k=10)
        stats = get_index_stats()
        return JSONResponse(content={
            "status": "ok",
            "resume_length": len(resume),
            "total_jds_in_index": stats["jd_count"],
            "matches": results,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重新匹配失败: {str(e)}")


@app.post("/rebuild-index")
async def rebuild_index():
    """从 jd_history.json 重建向量索引"""
    try:
        rebuild_index_from_history()
        stats = get_index_stats()
        return JSONResponse(content={
            "status": "ok",
            "message": f"索引重建完成: {stats['jd_count']} 条 JD",
            **stats,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"索引重建失败: {str(e)}")


@app.get("/vector-stats")
async def vector_stats():
    """获取向量库统计信息"""
    try:
        stats = get_index_stats()
        return JSONResponse(content={"status": "ok", **stats})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")


@app.get("/question-history")
async def question_history(role: str = "", company: str = ""):
    """获取历史面试题（可按岗位/公司筛选）"""
    try:
        if role:
            questions = get_history_questions(role=role, company=company)
            return JSONResponse(content={
                "status": "ok",
                "role": role,
                "company": company,
                "count": len(questions),
                "questions": questions,
            })
        else:
            return JSONResponse(content={
                "status": "ok",
                **get_question_stats(),
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取面试题历史失败: {str(e)}")


@app.get("/")
async def root():
    return {"message": "求职AI助手已上线！请访问 /docs 查看接口文档"}


# --- 启动命令 ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
