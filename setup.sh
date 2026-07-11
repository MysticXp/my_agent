#!/bin/bash
# ============================================================
# 🎯 My Agent — 一键启动脚本
# 检查环境 → 安装依赖 → 启动后端 + 前端
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================="
echo "  🎯 My Agent — 求职 AI 助手"
echo "================================="

# ── 1. 检查 Python ──
echo ""
echo "[1/5] 检查 Python 环境..."
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo "❌ 未找到 Python，请安装 Python 3.10+"
    exit 1
fi

PY_VERSION=$($PYTHON --version 2>&1)
echo "   ✅ $PY_VERSION"

# ── 2. 检查 .env ──
echo ""
echo "[2/5] 检查环境变量..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "   ⚠️  未找到 .env 文件，正在从 .env.example 创建..."
        cp .env.example .env
        echo "   ❗ 请编辑 .env 文件填入你的 DEEPSEEK_API_KEY"
        echo "      编辑完成后重新运行此脚本"
        exit 1
    else
        echo "   ❌ 未找到 .env 和 .env.example"
        exit 1
    fi
fi
echo "   ✅ .env 文件存在"

# 检查 API Key 是否已填写
if grep -q "your_deepseek_api_key_here" .env 2>/dev/null; then
    echo "   ❗ .env 中的 DEEPSEEK_API_KEY 尚未填写，请先编辑 .env"
    exit 1
fi
echo "   ✅ API Key 已配置"

# ── 3. 安装 Python 依赖 ──
echo ""
echo "[3/5] 安装 Python 依赖..."
$PYTHON -m pip install -r requirements_full.txt -q
echo "   ✅ 依赖安装完成"

# ── 4. 启动后端 ──
echo ""
echo "[4/5] 启动后端 (uvicorn)..."
$PYTHON -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "   ✅ 后端已启动 (PID: $BACKEND_PID)"
echo "   📍 http://localhost:8000"
echo "   📍 API 文档: http://localhost:8000/docs"

# 等待后端就绪
sleep 3

# ── 5. 启动前端 ──
echo ""
echo "[5/5] 启动前端..."
if [ -d "frontend" ]; then
    cd frontend
    if [ ! -d "node_modules" ]; then
        echo "   📦 安装前端依赖..."
        npm install
    fi
    echo "   🚀 启动 React 开发服务器..."
    npm start &
    FRONTEND_PID=$!
    echo "   ✅ 前端已启动 (PID: $FRONTEND_PID)"
    echo "   📍 http://localhost:3000"
    cd "$SCRIPT_DIR"
else
    echo "   ⚠️  未找到 frontend 目录，跳过前端启动"
fi

echo ""
echo "================================="
echo "  ✅ 启动完成！"
echo "  后端: http://localhost:8000"
echo "  前端: http://localhost:3000"
echo "================================="
echo ""
echo "按 Ctrl+C 停止所有服务"

# 捕获退出信号，清理后台进程
trap "echo ''; echo '正在停止服务...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo '服务已停止'; exit 0" SIGINT SIGTERM

# 保持脚本运行
wait
