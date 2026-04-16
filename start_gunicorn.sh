#!/bin/bash

# 配置区（按你的实际环境修改）
PROJECT_DIR="/app/gop"
VENV_DIR="$PROJECT_DIR/myenv"
LOG_DIR="/applog/gop/logs"
PORT=5000
WORKERS=10
TIMEOUT=598

# 日志文件
ACCESS_LOG="$LOG_DIR/access.log"
ERROR_LOG="$LOG_DIR/error.log"

# 检查目录
mkdir -p "$LOG_DIR"
if [ ! -d "$PROJECT_DIR" ]; then
    echo "错误：项目目录不存在 $PROJECT_DIR"
    exit 1
fi

# 激活虚拟环境
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "错误：虚拟环境不存在 $VENV_DIR"
    exit 1
fi
source "$VENV_DIR/bin/activate"

# 进入项目目录
cd "$PROJECT_DIR" || { echo "无法进入项目目录: $PROJECT_DIR"; exit 1; }

# 启动 Gunicorn
echo "启动 Gunicorn: 0.0.0.0:$PORT"
gunicorn \
    -w "$WORKERS" \
    -b "0.0.0.0:$PORT" \
    --timeout "$TIMEOUT" \
    --access-logfile "$ACCESS_LOG" \
    --error-logfile "$ERROR_LOG" \
    --daemon \
    app:app

# 退出虚拟环境（可选）
deactivate

echo "Gunicorn 已后台启动，日志：$LOG_DIR"