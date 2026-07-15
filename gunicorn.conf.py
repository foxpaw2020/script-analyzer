"""gunicorn 生产配置 — 剧本拆解大师 v2.52"""
import os
import multiprocessing

# 绑定地址
bind = f"{os.environ.get('BIND_HOST', '127.0.0.1')}:{os.environ.get('PORT', '5000')}"

# Worker 配置
workers = int(os.environ.get('WORKERS', min(4, multiprocessing.cpu_count())))
worker_class = 'gevent'  # 支持 SSE 长连接
worker_connections = 100
timeout = 600  # AI 调用可能较慢
graceful_timeout = 30

# 日志
loglevel = os.environ.get('LOG_LEVEL', 'info')
accesslog = '-'
errorlog = '-'

# 进程命名
proc_name = 'script-analyzer'

# 安全：降权后运行（如设置了用户）
user = os.environ.get('GUNICORN_USER', None)
group = os.environ.get('GUNICORN_GROUP', None)
