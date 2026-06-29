"""
SSE (Server-Sent Events) 工具
"""

import json


def json_sse(event, data):
    """生成 SSE 格式的 JSON 消息"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
