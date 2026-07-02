"""
场景拆解 - Scene_Extraction_Skills_v5.2
两轮提取：第一轮识别场次，第二轮生成细节
"""
# (C) foxpaw

import re

from .base import BaseExtractor

_KB_CONTENT = BaseExtractor._load_knowledge_base('Scene_Extraction_Skills_v5.2.json')

LIST_SYSTEM = """你是剧本场景分析师。你的任务是完整列出剧本中每一场戏的场景标题，不得合并、不得跳过任何一场。
按场号顺序输出。每场一行，标注场号和场景标题。

输出格式（只输出JSON）：
{"scenes":[{"scene_number":1,"title":"场景标题","time":"白天/夜晚","location":"地点"}],"total":0}

逐场检查：读完剧本中每一个场景标题(场号+地点+时间)，全部列出。"""

# 第一轮不做知识库注入（知识库内容为图片生成规则，与场次罗列任务无关，会干扰AI输出）

LIST_USER = "列出剧本中所有场景（场号+标题+时间+地点），不得遗漏任何一场。\n\n剧本：\n{script_text}"

def build_list_prompt(script_text, context=None):
    return LIST_SYSTEM, LIST_USER.format(script_text=script_text)

def parse_list(raw_text):
    parsed = BaseExtractor._safe_json_parse_with_fallback(raw_text)
    if parsed is None or not isinstance(parsed, dict):
        return []
    # 如果AI返回的是裸数组而非 {"scenes":[...]}，自动包裹
    if isinstance(parsed, list):
        s = parsed
    else:
        s = parsed.get("scenes") or parsed.get("scene") or parsed.get("sequences") or []
    if isinstance(s, list): return [{"scene_number": x.get("scene_number", i+1), "title": x.get("title", ""), "time": x.get("time",""), "location": x.get("location","")} for i, x in enumerate(s) if isinstance(x, dict)]
    return []

DETAIL_SYSTEM = """你是Nano Banana 2 Pro + GPT-Image-2双模型实拍空镜提示词工程师。

必须处理的场景名单（已在下方用户消息中提供）：你只能处理这些场景，不得增减。

核心规则：
1. 严格空镜——不含任何人物/人体/服装/动物
2. GPT-Image-2为主——每个场景生成3组提示词：全景版(GPT) + 俯视图版(GPT) + 多面板版(GPT)
3. 十层完整描述——不分级简化，每个场景都执行完整十层
4. 实拍电影质感——严禁3D渲染/CGI/游戏/卡通/动画
5. 仅中文输出

双模型提示词格式指引：
【GPT-Image-2版】五段式结构：场景描述/主体聚焦/重要细节/用途类型/约束条件。用视觉事实替换赞美词。
【多面板布局版(GPT-Image-2专用)】固定四段式结构，第一段格式严禁改动（仅替换...部分），如下模板：
多面板 {场景名称}内概念设计稿，{场所/环境}的多视角呈现，顶部为 {具体区域/角度}主广角全景，中间行为 {内景分区1}、{内景分区2}、{细节物件类别}细节的小缩略图，底部为{整体空间}纵览大图，附带{特写物件1}、{特写物件2}、{特写物件3}特写细节插图，{场景类型}环境设计，影视美术设计拆解，清晰的分镜排版

场景与物件
{十层数据中空间骨架 + 材质 + 陈设道具 + 标识 的自然语言整合，描述场景中所有物件的状态、材质、排列关系}

光影与色调
{光源位置+色温+实拍氛围+光影方案的完整自然语言描述}

画质与风格
超写实，超高细节，写实3D渲染，精细的环境细节，真实的材质纹理（{列出2-3种代表性材质}），8k，高分辨率，电影级构图，Artstation热门风格，大师级概念艺术，影视美术设计，物理基于渲染

场景信息卡新增字段：
- extraction_basis: 提取依据（引用剧本原文场景描述）
- urban_microclimate: 城市微气候与外部渗透描述
- general_params: 通用实拍主参数

输出格式必须是包裹在 {"scenes":[...]} 中的JSON对象，不能是裸数组：

{"scenes":[
  {"scene_number":1,"title":"场景名","episode":"第X集","time":"时间","location":"地点","scene_type":"内景/外景","characters":["角色"],"props":["道具"],"category":"S/A/B/C级","synopsis":"概要","dramatic_function":"戏剧功能","mood":"氛围","emotion_tags":"情绪标签","lighting_scheme":"N1-N9光照方案ID","estimated_duration":"时长","scene_info_card":"场景信息卡（表格格式）","extraction_basis":"提取依据（引用剧本原文）","wide_shot_gpt":"全景版 GPT-Image-2 完整提示词","topdown_gpt":"俯视图版 GPT-Image-2 完整提示词","multi_panel_gpt":"多面板布局参考图 GPT-Image-2 完整提示词","urban_microclimate":"城市微气候描述","general_params":"通用实拍主参数"}
],
"total_count":0,
"summary":"概述"}

重要：输出最外层是 {"scenes":[...],"total_count":N,"summary":"..."}，绝对不能是裸数组 [...]。
每个场景必须包含上述全部字段。
自检：每个场景是否都有3组完整提示词？GPT版是否用五段式？多面板版是否用四段式结构？"""

DETAIL_SYSTEM = (DETAIL_SYSTEM + "\n\n---\n\n" + _KB_CONTENT) if _KB_CONTENT else DETAIL_SYSTEM

def build_detail_prompt(script_text, scenes, context=None, temp_kb=None):
    sl = "\n".join(f"- 场景{s['scene_number']}: {s['title']}" for s in scenes)
    cc, pc = "", ""
    if context:
        if "characters" in context:
            cd=context["characters"]; lst=cd.get("characters",[]) if isinstance(cd,dict) else cd
            names=[c.get("name","") for c in lst] if isinstance(lst,list) else []; cc=", ".join(names)
        if "props" in context:
            pd=context["props"]; lst=pd.get("props",[]) if isinstance(pd,dict) else pd
            names=[p.get("name","") for p in lst] if isinstance(lst,list) else []; pc=", ".join(names)
    # 注入故事大纲世界观（场景外在风格优先取剧本，模糊时参考大纲）
    world_context = ""
    if temp_kb and temp_kb.get("world"):
        world_context = BaseExtractor._format_temp_world(temp_kb["world"]) + "\n\n注意：场景外在风格、环境描述优先从剧本中提取；剧本中设定模糊时，参考以上故事大纲信息补充。"
    system = DETAIL_SYSTEM + world_context if world_context else DETAIL_SYSTEM
    return system, f"剧本：\n{script_text}\n\n角色：{cc}\n道具：{pc}\n\n以下场景必须全部处理({len(scenes)}场)：\n{sl}\n\n只输出JSON。"


def _generate_multi_panel(scene):
    """AI未输出multi_panel_gpt时，从已有数据自动生成多面板布局提示词"""
    title = scene.get("title", "场景")
    location = scene.get("location", "")
    scene_type = scene.get("scene_type", "内景")
    mood = scene.get("mood", "")
    lighting = scene.get("lighting_scheme", "")
    props_list = scene.get("props", [])
    
    # 从全景GPT提示词中提取信息
    gpt_prompt = scene.get("wide_shot_gpt", "")
    obj_desc = ""
    light_desc = ""
    scene_desc_text = ""
    if gpt_prompt:
        m = re.search(r'【场景描述】(.*?)(?:【主体聚焦】)', gpt_prompt, re.DOTALL)
        if m:
            scene_desc_text = m.group(1).strip()
            light_parts = re.findall(r'[^。]*?(?:光线|光|阴影|色调|灯光|荧光|自然光|暗|亮|柔|氛围|色温)[^。]*。', scene_desc_text)
            if light_parts:
                light_desc = "。".join(light_parts[:4])
        m = re.search(r'【主体聚焦】(.*?)(?:【重要细节】|【用途类型】)', gpt_prompt, re.DOTALL)
        if m:
            obj_desc = m.group(1).strip()
        if not light_desc:
            m3 = re.search(r'【重要细节】(.*?)(?:【用途类型】)', gpt_prompt, re.DOTALL)
            if m3:
                detail = m3.group(1).strip()
                light_parts2 = re.findall(r'[^。]*?(?:光|影|反射|折射|闪烁|暗|亮)[^。]*。', detail)
                if light_parts2:
                    light_desc = "。".join(light_parts2[:3])
    
    if not obj_desc:
        obj_desc = f"{scene_type}空间，位于{location or '场景内'}，主要道具：{', '.join(props_list) if props_list else '无特定道具'}"
    if not light_desc:
        light_desc = f"{lighting}光影方案，{mood}氛围"
    
    # 确定环境类型标签
    is_ext = scene_type in ("外景", "EXT.")
    env_type = "外景" if is_ext else "室内"
    area_desc = location if location else title
    
    # 道具作为特写物件
    detail_items = props_list[:3] if props_list else ["场景细节"]
    while len(detail_items) < 3:
        detail_items.append("空间质感")
    detail_items = detail_items[:3]
    
    # 场景物件描述
    obj_full = obj_desc if obj_desc else f"{is_ext and '外景' or '内景'}空间，{location or title}，{', '.join(props_list) if props_list else '实景环境'}"
    # 光影描述
    light_full = light_desc if light_desc else f"{lighting or '自然光'}，{mood or '平静'}"
    # 材质（至少5种）
    materials = props_list[:] if props_list else ['实拍质感', '环境纹理']
    if not materials:
        materials = ['实拍质感', '环境纹理']
    while len(materials) < 5:
        materials.append('环境细节')
    materials = materials[:5]
    # 散落物品（至少5件）
    items = props_list[:] if props_list else ['日常物品']
    while len(items) < 5:
        items.append('环境元素')
    items = items[:5]
    obj_full = obj_desc if obj_desc else f"{is_ext and '外景' or '内景'}空间，{location or title}，{', '.join(props_list) if props_list else '实景环境'}"
    # 光影描述
    light_full = light_desc if light_desc else f"{lighting or '自然光'}，{mood or '平静'}"
    # 材质
    materials = props_list[:5] if props_list else ['实拍质感', '自然磨损', '环境纹理']
    while len(materials) < 5:
        materials.append('环境细节')
    materials = materials[:5]
    # 散落物品
    items = props_list[:5] if props_list else ['日常物品']
    while len(items) < 5:
        items.append('环境元素')
    items = items[:5]
    
    return (
        f"多面板 {title}内概念设计稿，{area_desc}的多视角呈现，\n"
        f"顶部为 {title}主广角全景，中间行为 {title}内景、"
        f"{props_list[1] if len(props_list)>1 else props_list[0] if props_list else '关键区域'}细节的小缩略图，\n"
        f"底部为{title}纵览大图，附带{items[0]}、{items[1]}、{items[2]}特写细节插图，\n"
        f"{env_type}环境设计，影视美术设计拆解，清晰的分镜排版\n\n"
        f"场景与物件\n"
        f"完好{'' if is_ext else '的'} {scene.get('time','日常')} {env_type} {title}，"
        f"{obj_full}，\n"
        f"完全空置，无人物，{mood or '平静'}状态\n\n"
        f"光影与色调\n"
        f"{light_full}，{scene.get('emotion_tags',mood) or '自然'}氛围，\n"
        f"柔和空气纵深感，实拍质感\n\n"
        f"画质与风格\n"
        f"超写实，超高细节，写实3D渲染，精细的环境细节，\n"
        f"真实的材质纹理（{materials[0]}、{materials[1]}、{materials[2]}、{materials[3]}、{materials[4]}），\n"
        f"8k，高分辨率，电影级构图，Artstation热门风格，\n"
        f"大师级概念艺术，影视美术设计，物理基于渲染"
    )

def parse_result(raw_text):
    parsed = BaseExtractor._safe_json_parse_with_fallback(raw_text)
    if parsed is None or not isinstance(parsed, dict):
        return {"scenes":[],"total_count":0,"summary":"解析失败","raw":raw_text[:500] if isinstance(raw_text, str) else ""}
    # 如果AI返回的是裸数组而非 {"scenes":[...]}，自动包裹
    if isinstance(parsed, list):
        s = parsed
    else:
        s = parsed.get("scenes") or parsed.get("scene") or parsed.get("sequences") or []
    if isinstance(s,dict): s = list(s.values())
    if not isinstance(s,list): s = []
    # 兼容旧字段名：wide_shot_prompt → wide_shot_nano, topdown_prompt → topdown_nano
    for scene in s:
        if isinstance(scene, dict):
            # 兼容旧字段名
            if scene.get("wide_shot_prompt") and not scene.get("wide_shot_gpt"):
                scene["wide_shot_gpt"] = scene.pop("wide_shot_prompt")
            if scene.get("topdown_prompt") and not scene.get("topdown_gpt"):
                scene["topdown_gpt"] = scene.pop("topdown_prompt")
            # 兜底：AI未输出 multi_panel_gpt 时自动生成
            if not scene.get("multi_panel_gpt"):
                scene["multi_panel_gpt"] = _generate_multi_panel(scene)
    tc = parsed.get("total_count")
    return {"scenes":s,"total_count":tc if tc is not None else len(s),"summary":parsed.get("summary") or "","raw":None}
