"""
道具提取 - 两轮提取：第一轮列清单，第二轮生成细节
"""
# (C) foxpaw, 2026-07-15

from .base import BaseExtractor

_KB_CONTENT = BaseExtractor._load_knowledge_base('Prop_Extraction_Skills_v3.0.json')
# _KB_LITE 已废弃 - 第一轮不需要知识库注入

LIST_SYSTEM = """你是剧本道具分析师。从剧本第一行到最后一行，逐场扫描，统计每个物品出现次数。

强制步骤：
1. 先遍历所有场景，统计每个物品出现场次
2. 筛选出符合要求的物品
3. 逐一列出这些道具名
4. 确认数量

包括：手持物品、武器、手机、包、家具、车辆、工具、关键情节道具等。

输出纯JSON：
{"props":["道具1","道具2","道具3"],"total":数量}"""

# 第一轮不做知识库注入（知识库内容为道具详情提取规则，与名单罗列任务无关，会干扰AI输出）

def build_list_prompt(script_text, context=None, min_appearances=2):
    if min_appearances <= 1:
        rule = "列出剧本中所有道具名称（单集无最低出现次数限制），不得遗漏。"
    else:
        rule = f"列出剧本中所有出现>={min_appearances}场的道具名称，不得遗漏。"
    return LIST_SYSTEM, f"{rule}\n\n剧本：\n{script_text}"

def parse_list(raw_text):
    parsed = BaseExtractor._safe_json_parse_with_fallback(raw_text)
    if parsed is None or not isinstance(parsed, dict):
        return []
    p = parsed.get("props") or parsed.get("prop") or parsed.get("items") or parsed.get("names") or []
    if isinstance(p, list): return [n for n in p if isinstance(n, str) and n.strip()]
    return []

DETAIL_SYSTEM = """你是好莱坞工业级道具资产提取与提示词工程师。

必须处理的道具名单（在用户消息中提供）：你只能处理这些道具，不得增减。每个道具都必须生成完整信息卡和提示词。

提示词必须严格遵循下方知识库规范中定义的视觉结构、画质标准、平台风格、一致性要求和反向提示词，不得省略任何要素。

输出JSON（必须包含列表中所有道具）：
{"props":[{"name":"道具名","category":"A/B/C/D类","importance":"重要性","episodes":"第X集","description":"描述","usage":"用途","quantity":2,"frequency":3,"material":"材质","color":"颜色","period_era":"年代","condition":"状态","text_signage":"文字标识","associated_characters":["角色"],"info_card":"道具信息卡","prompt":"连续纯文本提示词"}],"total_count":0,"platform":"Netflix","summary":"全量道具提取"}"""

DETAIL_SYSTEM = (DETAIL_SYSTEM + "\n\n---\n\n" + _KB_CONTENT) if _KB_CONTENT else DETAIL_SYSTEM

def build_detail_prompt(script_text, names, context=None, temp_kb=None):
    nl = "\n".join(f"- {n}" for n in names)
    cc = ""
    if context and "characters" in context:
        cd = context["characters"]; cl = cd.get("characters",[]) if isinstance(cd,dict) else cd
        cnames = [c.get("name","") for c in cl] if isinstance(cl,list) else []
        cc = ", ".join(cnames)
    # 注入故事大纲世界观
    world_context = ""
    if temp_kb and temp_kb.get("world"):
        world_context = BaseExtractor._format_temp_world(temp_kb["world"])
    system = DETAIL_SYSTEM + world_context if world_context else DETAIL_SYSTEM
    return system, f"剧本：\n{script_text}\n\n已知角色：{cc}\n\n以下道具名单必须全部处理({len(names)}个)，一个不能少：\n{nl}\n\n只输出JSON。"

def parse_result(raw_text):
    parsed = BaseExtractor._safe_json_parse_with_fallback(raw_text)
    if parsed is None or not isinstance(parsed, dict):
        return {"props":[],"total_count":0,"summary":"解析失败","raw":raw_text[:500] if isinstance(raw_text, str) else "EMPTY"}
    p = parsed.get("props") or parsed.get("prop") or parsed.get("items") or []
    if isinstance(p,dict): p = list(p.values())
    if not isinstance(p,list): p = []
    tc = parsed.get("total_count")
    return {"props":p,"total_count":tc if tc is not None else len(p),"platform":parsed.get("platform","Netflix"),"summary":parsed.get("summary") or "","raw":"(保留原始返回待调试)"}
