#!/bin/bash

# 设置你的项目名称或关键字（用于筛选正确的 Gunicorn 进程）
APP_NAME="app:app"

# 查找所有正在运行的 Gunicorn 主进程（排除 grep 自身）
PID=$(ps aux | grep "[g]unicorn.*$APP_NAME" | awk '{print $2}')

if [ -z "$PID" ]; then
  echo "⚠️ 没有找到正在运行的 Gunicorn 实例（匹配 '$APP_NAME'）。"
  exit 0
fi

echo "🛑 正在停止 Gunicorn 进程（PID: $PID）..."

# 发送 SIGTERM 信号，优雅关闭
kill -SIGTERM $PID

# 等待几秒，确保进程已退出
sleep 3

# 检查是否还有残留进程
REMAINING_PID=$(ps aux | grep "[g]unicorn.*$APP_NAME" | awk '{print $2}')

if [ ! -z "$REMAINING_PID" ]; then
  echo "⚠️ 检测到仍有残留进程（PID: $REMAINING_PID），尝试强制终止..."
  kill -SIGKILL $REMAINING_PID
fi

echo "✅ Gunicorn 已成功停止。"
