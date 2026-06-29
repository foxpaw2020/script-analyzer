"""
情绪时间线预分析器
在角色提取和场景提取完成后、分镜拆解之前运行
轻量推理：为每个角色的每场戏生成情绪变化轨迹
"""
from .base import BaseExtractor

SYSTEM_PROMPT = """你是剧本情绪分析师。你的任务是为剧本中每个角色的每场戏，标注情绪变化轨迹。

规则：
1. 每场戏每个出场角色必须标注情绪轨迹，至少包含2个阶段（开场→收尾），复杂情绪戏可分3-4个阶段。
2. 情绪名称从以下标准库中选择：紧张焦虑、愤怒敌意、悲伤绝望、恐惧惊骇、喜悦幸福、惊讶震惊、厌恶排斥、轻蔑鄙夷、羞耻愧疚、爱慕心动、嫉妒眼红、孤独落寞、坚定决心、犹豫纠结、疲惫倦怠、沉迷沉醉、轻浮调情、暗黑冷酷、崩溃失控、隐忍克制。如角色情绪不在库中，可在库中选择最接近的。
3. intensity 为1-5级烈度，1=隐约可感，3=明显显现，5=极端强烈。
4. trigger 字段必须引用剧本原文中的触发事件——一句台词、一个动作、一个场景变化。
5. 子文本识别：当角色台词与真实情绪不一致时（如嘴上说「没事」实际在隐忍克制），emotion 标注真实情绪，trigger 中注明「潜台词：嘴上说XX但内心XX」。
6. 输出纯JSON，不输出任何其他文字。

JSON模板：
{"scenes":[{"scene_number":1,"scene_title":"场景名","characters":{"角色名":{"emotion_arc":[{"stage":"开场","emotion":"情绪名","intensity":"3/5","trigger":"触发事件描述"},{"stage":"中段","emotion":"情绪名","intensity":"4/5","trigger":"触发事件描述"},{"stage":"收尾","emotion":"情绪名","intensity":"2/5","trigger":"触发事件描述"}]}}}]}"""


def build_prompt(script_text, character_names, scene_list):
    """构建情绪分析 prompt"""
    char_str = "、".join(character_names)
    scene_str = "\n".join(f"- 第{s['scene_number']}场: {s['title']} ({s.get('time','')} {s.get('location','')})" 
                          for s in scene_list)
    user = f"""剧本全文：
{script_text}

出场角色：{char_str}

场景列表（每场只需分析其中出场的角色）：
{scene_str}

请为每场戏的每个出场角色生成情绪时间线。只输出JSON。"""
    return SYSTEM_PROMPT, user


def parse_result(raw_text):
    """解析情绪时间线 JSON"""
    parsed = BaseExtractor._safe_json_parse_with_fallback(raw_text)
    if parsed is None or not isinstance(parsed, dict):
        return {"scenes": [], "error": "解析失败", "raw": raw_text[:500] if isinstance(raw_text, str) else ""}
    return parsed
