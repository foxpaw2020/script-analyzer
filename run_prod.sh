#!/bin/bash
# 剧本拆解大师 - 生产启动脚本
# 用法: ./run_prod.sh

# 设置环境变量（生产环境应从外部注入）
export SECRET_KEY="${SECRET_KEY:-$(python -c 'import os; print(os.urandom(24).hex())')}"
export PORT="${PORT:-5000}"
export WORKERS="${WORKERS:-4}"
export LOG_LEVEL="${LOG_LEVEL:-info}"

echo "剧本拆解大师 生产模式启动..."
echo "端口: $PORT | Workers: $WORKERS"

# 使用 gevent worker（支持 SSE 长连接）
gunicorn app:app -c gunicorn.conf.py
