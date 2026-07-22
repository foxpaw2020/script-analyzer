#!/bin/bash
# 剧本拆解大师 启动脚本
# 使用 screen 守护启动，避免进程随终端退出而挂掉

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
SCREEN_NAME="script-analyzer"
PORT=5006

# 如果已有 screen 会话在运行，先关掉
if screen -ls 2>/dev/null | grep -q "$SCREEN_NAME"; then
    echo "检测到已有运行中的服务，正在重启..."
    screen -S "$SCREEN_NAME" -X quit
    sleep 1
fi

# 启动服务
cd "$APP_DIR"
source venv/bin/activate
screen -dmS "$SCREEN_NAME" bash -c "PORT=$PORT python3 app.py"
sleep 3

# 验证
if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$PORT/" | grep -q 200; then
    echo "✅ 剧本拆解大师 v2.52 已启动: http://127.0.0.1:$PORT"
else
    echo "❌ 启动失败，查看日志: screen -r $SCREEN_NAME"
fi
