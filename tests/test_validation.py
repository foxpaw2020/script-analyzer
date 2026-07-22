"""Tests for input validation utilities."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))

from utils.validation import sanitize_api_config


def test_sanitize_clamps_temperature():
    cfg = {"temperature": "99", "max_tokens": "1000"}
    out = sanitize_api_config(cfg)
    assert out["temperature"] == 2.0


def test_sanitize_invalid_temperature_uses_default():
    cfg = {"temperature": "abc"}
    out = sanitize_api_config(cfg)
    assert out["temperature"] == 0.7


def test_sanitize_clamps_max_tokens():
    cfg = {"max_tokens": "999999"}
    out = sanitize_api_config(cfg)
    assert out["max_tokens"] <= 100000


def test_sanitize_clamps_top_p():
    cfg = {"top_p": "1.5"}
    out = sanitize_api_config(cfg)
    assert out["top_p"] == 1.0


def test_sanitize_clamps_penalties():
    cfg = {"frequency_penalty": "-5", "presence_penalty": "5"}
    out = sanitize_api_config(cfg)
    assert out["frequency_penalty"] == -2.0
    assert out["presence_penalty"] == 2.0


def test_sanitize_preserves_provider_and_key():
    cfg = {"provider": "ollama", "api_key": "sk-test", "model": "ornith:latest"}
    out = sanitize_api_config(cfg)
    assert out["provider"] == "ollama"
    assert out["api_key"] == "sk-test"
    assert out["model"] == "ornith:latest"
