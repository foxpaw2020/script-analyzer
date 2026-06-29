"""Gunicorn 生产配置 — 剧本拆解大师"""
import os
import multiprocessing

# 绑定地址
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"

# Worker 配置
workers = int(os.environ.get('WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'gevent'  # 异步 worker，适合 SSE 长连接
worker_connections = 1000
timeout = 300  # AI 调用可能长达 120s，给足余量
graceful_timeout = 30

# 日志
accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('LOG_LEVEL', 'info')

# 安全
limit_request_line = 4096
limit_request_fields = 100
