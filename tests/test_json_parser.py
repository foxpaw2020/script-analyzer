"""测试 JSON 解析器的括号深度匹配和修复功能"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from extractors.base import BaseExtractor
import json


def test_extract_braces_in_strings():
    """JSON 字符串值内含有 {} 时，不应干扰外层匹配"""
    t = '{"prompt":"dont show } CGI { or }"}'
    r = BaseExtractor._extract_json(t)
    assert r == t, f"Got: {r}"


def test_extract_markdown_nested():
    """markdown 包裹 + 嵌套对象中的字符串含 {}"""
    t = '```json\n{"scenes":[{"p":"x } y { z"}]}\n```'
    r = BaseExtractor._extract_json(t)
    assert r == '{"scenes":[{"p":"x } y { z"}]}', f"Got: {r}"


def test_repair_newlines():
    """修复 JSON 字符串内的裸换行符"""
    t = '{"key":"line1\nline2"}'
    r = BaseExtractor._repair_json(t)
    p = json.loads(r)
    assert p["key"] == "line1\nline2", f"Got: {repr(p['key'])}"


def test_fallback_with_braces():
    """完整的回退解析：包含字符串内 {} 的 props JSON"""
    t = '{"props":[{"name":"train","prompt":"text with } inside"}],"total_count":1}'
    p = BaseExtractor._safe_json_parse_with_fallback(t)
    assert p is not None and p["total_count"] == 1, f"Got: {p}"


def test_fallback_with_escaped_quotes():
    """已正确转义的反斜杠引号"""
    t = '{"key":"he said \\"hello\\""}'
    p = BaseExtractor._safe_json_parse_with_fallback(t)
    assert p is not None and p["key"] == 'he said "hello"', f"Got: {p}"
