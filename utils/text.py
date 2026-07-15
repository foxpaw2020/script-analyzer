"""
文本工具 - 剧集检测、剧本按集拆分等
"""

import re


# 中文数字 → 整数解析（共享，避免 detect_episode 与 _parse_episode_number 重复）
_DIGITS = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
           '六': 6, '七': 7, '八': 8, '九': 9, '零': 0}
_UNITS = {'十': 10, '百': 100, '千': 1000}

def _parse_chinese_num(s):
    """将中文数字字符串转为整数，如 '二十一' → 21, '一百零一' → 101"""
    val = 0
    temp = 0
    for c in s:
        if c in _DIGITS:
            temp = _DIGITS[c]
        elif c in _UNITS:
            temp = max(temp, 1)
            val += temp * _UNITS[c]
            temp = 0
    val += temp
    return val

# 集标记正则（detect_episode 用，不锚定行首/行尾，灵活匹配）
_EPISODE_PATTERN = (
    r'第\s*\d+\s*集'
    r'|第\s*[一二三四五六七八九十百千零]+\s*集'
    r'|Episode\s*\d+'
    r'|EP\s*\d+'
)


def detect_episode(script_text):
    """从剧本中检测第几集"""
    m = re.search(_EPISODE_PATTERN, script_text, re.IGNORECASE)
    if not m:
        return None
    num_str = m.group(0)
    # 英文标记：Episode 5 → 提取 5
    em = re.search(r'(?:^Episode\s*|^EP\s*)(\d+)', num_str, re.IGNORECASE)
    if em:
        return {'current': int(em.group(1)), 'total': None}
    # 阿拉伯数字中文标记：第5集 → 提取 5
    dm = re.search(r'第\s*(\d+)\s*集', num_str)
    if dm:
        return {'current': int(dm.group(1)), 'total': None}
    # 中文数字标记：第五集 → 转换
    cm = re.search(r'第\s*([一二三四五六七八九十百千零]+)\s*集', num_str)
    if cm:
        num = cm.group(1)
        val = _parse_chinese_num(num)
        return {'current': max(val, 1), 'total': None}
    return None


def _parse_episode_number(marker_text):
    """从集标记文本中提取实际集号，如 'EPISODE 5' → 5, '第三集' → 3"""
    # EPISODE 5 / Episode 5 / EP 5
    m = re.search(r'(?:EPISODE|Episode|EP)\s*(\d+)', marker_text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # 第5集
    m = re.search(r'第\s*(\d+)\s*集', marker_text)
    if m:
        return int(m.group(1))
    # 第五集
    m = re.search(r'第\s*([一二三四五六七八九十百千零]+)\s*集', marker_text)
    if m:
        num = m.group(1)
        val = _parse_chinese_num(num)
        return max(val, 1)
    return 0


def split_script_by_episodes(script_text):
    """按集拆分剧本。

    返回 [(集号, 文本), ...] 或 None（拆分失败/不足2集）。
    集号从剧本标记中真实提取（EPISODE 5 → 5, 第3集 → 3）。
    兼容：第1集、EPISODE 1、Episode 1、EP 1（大小写不敏感）。
    """
    pattern = r'(^|\n)\s*(第\s*\d+\s*集|第\s*[一二三四五六七八九十百千零]+\s*集|EPISODE\s*\d+|Episode\s*\d+|EP\s*\d+)\b'
    matches = list(re.finditer(pattern, script_text, re.IGNORECASE | re.MULTILINE))
    if len(matches) < 2:
        return None

    episodes = []
    # 第一个集标记之前的内容 → 前言
    preamble = script_text[:matches[0].start(2)].strip()
    if preamble and len(preamble) >= 8:  # 至少8字符才算有效前言
        episodes.append((0, preamble))
    
    for i, m in enumerate(matches):
        marker = m.group(2).strip()
        ep_num = _parse_episode_number(marker)
        start = m.start(2)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(script_text)
        content = script_text[start:end].strip()
        if content:
            episodes.append((ep_num, content))
    
    return episodes if len(episodes) >= 2 else None


# ============================================================
# 通用安全类型转换（供 ai_service 等模块使用）
# ============================================================

def safe_float(val, default=0.7):
    """Safe float conversion: empty/None/invalid -> default"""
    if val is None:
        return default
    s = str(val).strip()
    if not s:
        return default
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=None):
    """Safe int conversion: empty/None/invalid -> default"""
    if val is None:
        return default
    s = str(val).strip()
    if not s:
        return default
    try:
        return int(s)
    except (ValueError, TypeError):
        return default
