"""
AI API 调用服务 - 支持 Ollama 和 OpenAI 兼容接口（策略模式）
"""
# (C) foxpaw


import os
import json
import time
import re
from abc import ABC, abstractmethod

import requests

import config


# ============================================================
# Provider 抽象基类 & 具体实现
# ============================================================

class AIProvider(ABC):
    """AI 提供商抽象基类"""

    @abstractmethod
    def build_request(self, model, base_url, system_prompt, user_prompt, api_config):
        """构建请求：返回 (url, payload, headers)"""
        pass

    @abstractmethod
    def extract_content(self, response_data):
        """从响应中提取文本内容"""
        pass

    def get_default_model(self):
        return None

    def get_default_url(self):
        return None

    @property
    def name(self):
        """提供商显示名，用于错误消息"""
        return self.__class__.__name__.replace("Provider", "")


class OllamaProvider(AIProvider):
    def get_default_model(self):
        return config.OLLAMA_MODEL

    def get_default_url(self):
        return config.OLLAMA_BASE_URL

    @property
    def name(self):
        return "Ollama"

    def build_request(self, model, base_url, system_prompt, user_prompt, api_config):
        url = f"{base_url.rstrip('/')}/api/chat"
        temperature = float(api_config.get('temperature', 0))
        max_tok = int(api_config.get('max_tokens', config.MAX_TOKENS))
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tok
            }
        }
        return url, payload, {}

    def extract_content(self, response_data):
        return response_data.get("message", {}).get("content", "")


class OpenAICompatibleProvider(AIProvider):
    def get_default_model(self):
        return config.DEEPSEEK_MODEL

    def get_default_url(self):
        return config.DEEPSEEK_API_URL

    @property
    def name(self):
        return "API"

    def build_request(self, model, base_url, system_prompt, user_prompt, api_config):
        api_key = api_config.get("api_key", "")
        url = f"{base_url.rstrip('/')}/v1/chat/completions"
        temperature = float(api_config.get('temperature', 0))
        top_p = float(api_config.get('top_p', 0.95)) if api_config.get('top_p', '') != '' else None
        freq_pen = float(api_config.get('frequency_penalty', 0.0)) if api_config.get('frequency_penalty', '') != '' else None
        pres_pen = float(api_config.get('presence_penalty', 0)) if api_config.get('presence_penalty', '') != '' else None
        max_tok = int(api_config.get('max_tokens', config.MAX_TOKENS))
        thinking = api_config.get('thinking', '0') == '1'
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tok,
            "seed": config.SEED,
            "stream": False
        }
        if top_p is not None:
            payload["top_p"] = top_p
        if freq_pen is not None:
            payload["frequency_penalty"] = freq_pen
        if pres_pen is not None:
            payload["presence_penalty"] = pres_pen
        if thinking and 'v4-flash' in model:
            payload["thinking"] = {"type": "enabled"}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        return url, payload, headers

    def extract_content(self, response_data):
        msg = response_data.get("choices", [{}])[0].get("message", {})
        return msg.get("content", "") or msg.get("reasoning_content", "")


# ============================================================
# Provider 注册表 — 添加新提供商只需在这里注册
# ============================================================

PROVIDER_REGISTRY = {
    "ollama": OllamaProvider(),
    "openai": OpenAICompatibleProvider(),
    "deepseek": OpenAICompatibleProvider(),
    # 未来扩展: "claude": ClaudeProvider(), "zhipu": ZhipuProvider(), "gpt": OpenAICompatibleProvider(),
}


# ============================================================
# call_ai() — 统一调用入口（策略模式驱动）
# ============================================================

def call_ai(system_prompt, user_prompt, api_config):
    """调用 AI API（支持 Ollama 和 OpenAI 兼容接口）"""
    provider_name = api_config.get("provider", "ollama")
    api_key = api_config.get("api_key", "")
    model = api_config.get("model", "")
    base_url = api_config.get("base_url", "")

    provider = PROVIDER_REGISTRY.get(provider_name)
    if provider is None:
        raise RuntimeError(f"不支持的 AI 提供商: {provider_name}")

    if not model:
        model = provider.get_default_model() or ""
    if not base_url:
        base_url = provider.get_default_url() or ""

    try:
        url, payload, headers = provider.build_request(model, base_url, system_prompt, user_prompt, api_config)
    except (ValueError, TypeError) as e:
        raise RuntimeError(f"AI 参数配置错误: {str(e)}")

    # 如果 provider 未设置 Authorization 且提供了 api_key，自动补充
    if "Authorization" not in headers and api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    last_error = None
    for retry in range(3):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
            return provider.extract_content(resp.json())
        except (ValueError, TypeError) as e:
            raise RuntimeError(f"AI 参数配置错误: {str(e)}")
        except requests.exceptions.ConnectionError as e:
            last_error = e
            if retry < 2:
                time.sleep(2 ** retry)
                continue
        except requests.exceptions.Timeout as e:
            last_error = e
            if retry < 2:
                time.sleep(2 ** retry)
                continue
        except requests.exceptions.HTTPError as e:
            # 仅服务端错误（5xx）重试，客户端错误（401/429 等）不重试
            if e.response is not None and 500 <= e.response.status_code < 600:
                last_error = e
                if retry < 2:
                    time.sleep(2 ** retry)
                    continue
                raise RuntimeError(
                    f"{provider.name} API 错误（已重试 3 次）: "
                    f"{e.response.status_code} - {e.response.text[:200]}"
                )
            status = e.response.status_code if e.response is not None else "?"
            if status == 401:
                raise RuntimeError("API Key 无效，请检查配置")
            elif status == 429:
                raise RuntimeError("API 请求过于频繁，请稍后重试")
            else:
                raise RuntimeError(
                    f"{provider.name} API 错误: {e.response.status_code} - {e.response.text[:200]}"
                )
        except Exception as e:
            raise RuntimeError(f"AI 调用失败: {str(e)}")

    # 所有重试耗尽 → 抛出最终错误（保留原有错误消息以兼容测试）
    if isinstance(last_error, requests.exceptions.ConnectionError):
        if provider_name == "ollama":
            raise ConnectionError(
                f"无法连接到 Ollama ({base_url})，请确认 Ollama 已启动（已重试 3 次）"
            )
        else:
            raise ConnectionError(f"无法连接到 API ({base_url})（已重试 3 次）")
    elif isinstance(last_error, requests.exceptions.Timeout):
        raise TimeoutError("AI 请求超时，请检查网络或降低模型复杂度（已重试 3 次）")
    else:
        raise RuntimeError(f"AI 调用失败（已重试 3 次）: {str(last_error)}")
