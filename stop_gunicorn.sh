#!/bin/bash

PID_FILE="/tmp/gunicorn_gop.pid"

# 方法1：通过 PID 文件停止（优先）
if [ -f "$PID_FILE" ]; then
  PID=$(cat "$PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    echo "🛑 正在停止 Gunicorn 主进程（PID: $PID）..."
    kill -SIGTERM "$PID"
    sleep 3

    if kill -0 "$PID" 2>/dev/null; then
      echo "⚠️ 进程未响应 SIGTERM，强制终止..."
      kill -SIGKILL "$PID"
    fi

    # 清理子进程
    pkill -f "gunicorn.*app:app" 2>/dev/null
    rm -f "$PID_FILE"
    echo "✅ Gunicorn 已成功停止。"
    exit 0
  else
    echo "⚠️ PID 文件存在但进程已不存在，清理 PID 文件..."
    rm -f "$PID_FILE"
  fi
fi

# 方法2：PID 文件不存在，通过 ps 查找（使用 ww 避免命令行截断）
APP_NAME="app:app"
PID=$(ps auxww | grep "[g]unicorn.*$APP_NAME" | awk '{print $2}')

if [ -z "$PID" ]; then
  echo "⚠️ 没有找到正在运行的 Gunicorn 实例（匹配 '$APP_NAME'）。"
  exit 0
fi

echo "🛑 正在停止 Gunicorn 进程（PID: $PID）..."
kill -SIGTERM $PID
sleep 3

REMAINING_PID=$(ps auxww | grep "[g]unicorn.*$APP_NAME" | awk '{print $2}')
if [ ! -z "$REMAINING_PID" ]; then
  echo "⚠️ 检测到仍有残留进程（PID: $REMAINING_PID），尝试强制终止..."
  kill -SIGKILL $REMAINING_PID
fi

echo "✅ Gunicorn 已成功停止。"
