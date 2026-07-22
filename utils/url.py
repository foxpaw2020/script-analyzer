"""URL validation utilities to prevent SSRF and other URL-based attacks."""
from urllib.parse import urlparse

import config


# Known provider hosts used when ALLOWED_BASE_URLS is not configured.
KNOWN_PROVIDER_HOSTS = {
    "ollama": {"localhost", "127.0.0.1"},
    "deepseek": {"api.deepseek.com"},
    "openai": {"api.openai.com"},
}

# Default Ollama listen addresses (with standard port).
OLLAMA_LOCAL_NETLOCS = {"localhost:11434", "127.0.0.1:11434"}


def validate_api_base_url(base_url, provider_name=None):
    """Validate a user-supplied AI base URL to prevent SSRF.

    Args:
        base_url: The URL to validate.
        provider_name: Optional provider key (e.g. "ollama", "deepseek").

    Raises:
        ValueError: If the URL is not allowed.
    """
    if not base_url:
        return

    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"不支持的 URL scheme: {parsed.scheme}")

    netloc = parsed.netloc.lower()
    if not netloc:
        raise ValueError(f"无效的 API 地址: {base_url}")

    # 1. Explicit whitelist from environment takes precedence.
    if config.ALLOWED_BASE_URLS:
        allowed = {h.lower() for h in config.ALLOWED_BASE_URLS}
        if netloc in allowed:
            return
        raise ValueError(f"不允许的 API 地址: {base_url}")

    # 2. Known provider hosts (default secure behavior).
    if provider_name in KNOWN_PROVIDER_HOSTS:
        if netloc in {h.lower() for h in KNOWN_PROVIDER_HOSTS[provider_name]}:
            return

    # 3. Ollama local addresses are allowed by default.
    if provider_name == "ollama" and netloc in OLLAMA_LOCAL_NETLOCS:
        return

    raise ValueError(f"不允许的 API 地址: {base_url}")
