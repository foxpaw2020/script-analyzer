"""
文本工具 - 剧集检测、剧本按集拆分等
"""

import re

# 集标记正则（detect_episode 用，不锚定行首/行尾，灵活匹配）
_EPISODE_PATTERN = (
    r'第\s*\d+\s*集'
    r'|第\s*[一二三四五六七八九十百千零]+\s*集'
    r'|Episode\s*\d+'
    r'|EP\s*\d+'
)


def detect_episode(script_text):
    """从剧本中检测第几集"""
    chinese_num = {
        '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '零': 0,
    }
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
        val = 0
        unit = 1
        for c in reversed(num):
            if c in chinese_num:
                val += chinese_num[c] * unit
            elif c == '十':
                unit = 10
            elif c == '百':
                unit = 100
            elif c == '千':
                unit = 1000
        return {'current': max(val, 1), 'total': None}
    return None


def split_script_by_episodes(script_text):
    """按集拆分剧本。

    返回 [(集号, 文本), ...] 或 None（拆分失败/不足2集）。

    使用 finditer + 位置切分替代 re.split，更可靠地处理各种集标记格式。
    兼容：第1集、EPISODE 1、Episode 1、EP 1（大小写不敏感）。
    """
    pattern = r'(^|\n)\s*(第\s*\d+\s*集|第\s*[一二三四五六七八九十百千零]+\s*集|EPISODE\s*\d+|Episode\s*\d+|EP\s*\d+)\b'
    matches = list(re.finditer(pattern, script_text, re.IGNORECASE | re.MULTILINE))
    if len(matches) < 2:
        return None

    episodes = []
    # 第一个集标记之前的内容 → 前言
    preamble = script_text[:matches[0].start(2)].strip()
    if preamble and len(preamble) > 5:
        episodes.append((0, preamble))
    
    for i, m in enumerate(matches):
        start = m.start(2)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(script_text)
        content = script_text[start:end].strip()
        if content:
            episodes.append((i + 1, content))
    
    return episodes if len(episodes) >= 2 else None
