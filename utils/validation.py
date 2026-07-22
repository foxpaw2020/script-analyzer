"""Validation utilities for API configuration and user inputs."""
import config
from utils.text import safe_float, safe_int


def sanitize_api_config(api_config):
    """Clamp and validate AI API parameters to safe ranges.

    Args:
        api_config: dict-like object with raw user-provided parameters.

    Returns:
        dict: sanitized parameters.
    """
    out = dict(api_config)

    temp = safe_float(out.get("temperature"), 0.7)
    out["temperature"] = max(0.0, min(2.0, temp))

    top_p = out.get("top_p")
    if top_p is not None and str(top_p).strip():
        top_p = safe_float(top_p, None)
        if top_p is not None:
            out["top_p"] = max(0.0, min(1.0, top_p))

    max_tok = safe_int(out.get("max_tokens"), config.MAX_TOKENS)
    # Cap to a reasonable upper bound regardless of default.
    out["max_tokens"] = min(max_tok, 100000)

    freq = out.get("frequency_penalty")
    if freq is not None and str(freq).strip():
        freq = safe_float(freq, None)
        if freq is not None:
            out["frequency_penalty"] = max(-2.0, min(2.0, freq))

    pres = out.get("presence_penalty")
    if pres is not None and str(pres).strip():
        pres = safe_float(pres, None)
        if pres is not None:
            out["presence_penalty"] = max(-2.0, min(2.0, pres))

    return out
