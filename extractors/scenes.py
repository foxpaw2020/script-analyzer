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
2. GPT-Image-2为主——每个场景生成提示词：全景版(GPT) + 多面板版(GPT)
3. 十层完整描述——不分级简化，每个场景都执行完整十层
4. 实拍电影质感——严禁3D渲染/CGI/游戏/卡通/动画
5. 仅中文输出

双模型提示词格式指引：
【GPT-Image-2版 — 全景版】五段式结构：场景描述/主体聚焦/重要细节/用途类型/约束条件。用视觉事实替换赞美词。每段内容必须从场景信息卡中提取对应数据——空间类型、材质、道具、光影方案、氛围等。
【GPT-Image-2版 — 多面板布局版】固定四段式结构，第一段格式严禁改动（仅替换...部分），如下模板：
多面板 {场景名称}内概念设计稿，{场所/环境}的多视角呈现，顶部为 {具体区域/角度}主广角全景，中间行为 {内景分区1}、{内景分区2}、{细节物件类别}细节的小缩略图，底部为{整体空间}纵览大图，附带{特写物件1}、{特写物件2}、{特写物件3}特写细节插图，{场景类型}环境设计，影视美术设计拆解，清晰的分镜排版

场景与物件
{十层数据中空间骨架 + 材质 + 陈设道具 + 标识 的自然语言整合，描述场景中所有物件的状态、材质、排列关系}

光影与色调
{光源位置+色温+实拍氛围+光影方案的完整自然语言描述}

画质与风格
超写实，超高细节，写实3D渲染，精细的环境细节，真实的材质纹理（{列出2-3种代表性材质}），8k，高分辨率，电影级构图，Artstation热门风格，大师级概念艺术，影视美术设计，物理基于渲染

场景信息卡（表格格式）包含场景的核心数据：空间类型、材质清单、陈设道具、光影方案、氛围基调、提取依据、微气候、实拍参数等。这些数据必须在生成全景版、俯视图版、多面板版提示词时作为原材料融入——不是简单拼接，而是在提示词的各段落中自然地体现信息卡中的具体细节。

输出格式必须是包裹在 {"scenes":[...]} 中的JSON对象，不能是裸数组：

{"scenes":[
  {"scene_number":1,"title":"场景名","episode":"第X集","time":"时间","location":"地点","scene_type":"内景/外景","characters":["角色"],"props":["道具"],"category":"S/A/B/C级","synopsis":"概要","dramatic_function":"戏剧功能","mood":"氛围","emotion_tags":"情绪标签","lighting_scheme":"N1-N9光照方案ID","estimated_duration":"时长","scene_info_card":"| 项目 | 内容 |\n|------|------|\n| 空间类型 | ... |\n| 材质清单 | ... |\n| 陈设道具 | ... |\n| 光影方案 | ... |\n| 氛围基调 | ... |\n| 提取依据 | ... |\n| 微气候 | ... |\n| 实拍参数 | ... |","extraction_basis":"提取依据（引用剧本原文）","wide_shot_gpt":"全景版 GPT-Image-2 完整提示词（已融入场景信息卡数据）","grid_nine_gpt":"九宫格剧情参考图 GPT-Image-2 完整提示词（已融入场景信息卡数据）","multi_panel_gpt":"多面板布局参考图 GPT-Image-2 完整提示词（已融入场景信息卡数据）","urban_microclimate":"城市微气候描述","general_params":"通用实拍主参数"}
],
"total_count":0,
"summary":"概述"}

重要：输出最外层是 {"scenes":[...],"total_count":N,"summary":"..."}，绝对不能是裸数组 [...]。
每个场景必须包含上述全部字段。
自检：每个场景是否都有完整提示词？全景版是否用五段式？多面板版是否用四段式结构？"""

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
    general = scene.get("general_params", "")
    time_of_day = scene.get("time", "白天")

    gpt_prompt = scene.get("wide_shot_gpt", "")
    obj_desc = ""
    light_desc = ""
    scene_desc_text = ""
    if gpt_prompt:
        import re
        m = re.search(r'【场景描述】(.*?)(?:【主体聚焦】)', gpt_prompt, re.DOTALL)
        if m:
            scene_desc_text = m.group(1).strip()
            light_parts = re.findall(r'[^。]*?(?:光线|光|阴影|色调|灯光|荧光|自然光|暗|亮|柔|氛围|色温)[^。]*。', scene_desc_text)
            if light_parts:
                light_desc = "。".join(light_parts[:4])
        m = re.search(r'【主体聚焦】(.*?)(?:【重要细节】|【用途类型】)', gpt_prompt, re.DOTALL)
        if m:
            obj_desc = m.group(1).strip()[:100]
        if not light_desc:
            m3 = re.search(r'【重要细节】(.*?)(?:【用途类型】)', gpt_prompt, re.DOTALL)
            if m3:
                detail = m3.group(1).strip()
                light_parts2 = re.findall(r'[^。]*?(?:光|影|反射|折射|闪烃|暗|亮)[^。]*。', detail)
                if light_parts2:
                    light_desc = "。".join(light_parts2[:3])

    if not obj_desc:
        obj_desc = f"{scene_type}空间，{location or title}，道具：{', '.join(props_list[:5]) if props_list else '实景环境'}"
    if not light_desc:
        light_desc = f"{lighting or '自然'}光影方案，{mood or '平静'}氛围"

    is_ext = scene_type in ("外景", "EXT.")
    is_narrow = scene_type in ("过渡", "走廊", "通道", "TRANSITION", "狭窄")
    env_type = "外景" if is_ext else "室内"
    env_tag = "室外环境" if is_ext else "室内空间"

    props_items = [p for p in props_list if isinstance(p, str) and p.strip()] if props_list else []
    items = props_items[:5] if props_items else ['实景环境细节', '材质纹理', '自然光影']
    while len(items) < 3:
        items.append('环境元素')

    if is_ext:
        first_seg = (
            f"多面板 {title}外景概念参考图，{location or title}的多视角拆解，"
            f"顶部展示 {title}航拍/广角大景，中间行排列 "
            f"{'局部区域细节' if not props_items else props_items[0]}、"
            f"{'环境特征' if len(props_items)<2 else (props_items[1] if len(props_items)>1 else '空间结构')}、"
            f"{items[-1]}的参考缩略图，底部为 {location or title}全景纵览，"
            f"辅以 {items[0]}、{items[1] if len(items)>1 else '材质纹理'}、{items[-1]}特写插画，"
            f"室外环境设计，实地勘景参考，美术概念拆解"
        )
    elif is_narrow:
        first_seg = (
            f"多面板 {title}过渡空间设计参考，{location or title}的多角度呈现，"
            f"顶部展示 {title}透视大图，中间排列 "
            f"{'中段空间细节' if not props_items else props_items[0]}、"
            f"{'转折点结构' if len(props_items)<2 else props_items[1]}、"
            f"{items[-1]}特写缩略图，底部为 {title}纵深纵览，"
            f"辅以 {items[0]}、{items[1] if len(items)>1 else '表面质感'}、{items[-1]}细部插图，"
            f"过渡空间环境设计，路径透视分析"
        )
    else:
        first_seg = (
            f"多面板 {title}内概念设计稿，{location or title}的多视角呈现，"
            f"顶部为 {title}主广角全景，中间行为 "
            f"{title}内景、"
            f"{props_items[1] if len(props_items)>1 else (props_items[0] if props_items else '关键区域')}细节的小缩略图，"
            f"底部为{title}纵览大图，附带{items[0]}、{items[1]}、{items[-1]}特写细节插图，"
            f"{env_tag}环境设计，影视美术设计拆解，清晰的分镜排版"
        )

    light_full = light_desc if light_desc else "{lighting or '自然'}光影，{mood or '平静'}氛围"
    materials_str = ', '.join(items[:3]) if items else '实拍材质'
    general_str = f"，{general}" if general else ""

    return (
        f"{first_seg}\n\n"
        f"场景与物件\n"
        f"{time_of_day}的{env_type} {title}，位于{location or '场景内'}，"
        f"{obj_desc}，{mood or '平静'}状态"
        f"\n\n光影与色调\n"
        f"{light_full}，{mood or '自然'}氛围，柔和空气纵深感，实拍质感"
        f"\n\n画质与风格\n"
        f"超写实，超高细节，写实3D渲染，精细的环境细节，"
        f"真实的材质纹理（{materials_str}），"
        f"8k，高分辨率，电影级构图，Artstation热门风格，"
        f"大师级概念艺术，影视美术设计，物理基于渲染{general_str}"
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


# ===== 第四轮：多面板布局参考图提示词（multi_panel_gpt）=====

MULTIPANEL_SYSTEM = """你是GPT-Image-2实拍电影场景多面板布局设计工程师。已有场景的基础信息、全景版和俯视图版提示词，现在需要从中提取关键信息，为每个场景设计一张【多面板布局参考图提示词】。

多面板概念：在一张画布上通过多视角排版展示同一个场景的空间结构、材质细节和氛围方案，类似影视美术的"概念设计拆解板"。

## 核心规则
1. 严格空镜——不含任何人物/人体/服装/动物
2. 从已有的全景版和俯视图版提示词中提取关键视觉信息，按多面板排版逻辑重新编排
3. 根据场景类型（内景/外景/过渡/特殊）选择合适的模板变体
4. 实拍电影质感，禁止3D渲染/CGI/游戏/卡通
5. 仅中文输出，完整的四段式结构

## 四段式结构

### 第一段：排版布局（根据场景类型选择模板）
根据 scene_type 和 地点 选择以下模板之一：

内景使用：
多面板 {场景名称}内概念设计稿，{场所/环境}的多视角呈现，顶部为 {具体区域}主广角全景，中间行为 {内景分区A}、{内景分区B}、{细节物件类别}细节的小缩略图，底部为{整体空间}纵览大图，附带{特写物件1}、{特写物件2}、{特写物件3}特写细节插图，{场景类型}环境设计，影视美术设计拆解，清晰的分镜排版

外景使用：
多面板 {场景名称}外景概念参考图，{地点/环境}的多视角拆解，顶部展示 {远景视野}航拍/广角大景，中间行排列 {中景区域A}、{中景区域B}、{局部细节特征}的参考缩略图，底部为 {整体地形/建筑群}全景纵览，辅以 {自然元素1}、{材质纹理2}、{结构细节3}特写插画，{环境类型}室外环境设计，实地勘景参考，美术概念拆解

过渡/通道空间使用：
多面板 {场景名称}过渡空间设计参考，{通道/过渡区域}的多角度呈现，顶部展示 {入口/起点}视角透视大图，中间排列 {中段空间A}、{转折点/关键结构}、{材质细节特征}特写缩略图，底部为 {出口/终点}纵深纵览，辅以 {表面材质1}、{结构接缝2}、{环境光照3}细部插图，过渡空间环境设计，路径透视分析，清晰的分镜排版

### 第二段：场景与物件
描述空间骨架、材质、陈设与排列关系的完整自然语言段落

### 第三段：光影与色调
基于 lighting_scheme 和 mood 展开，描述光源位置、色温、实拍氛围、光影反差

### 第四段：画质与风格
- 超写实，超高细节，写实3D渲染，精细的环境细节，真实的材质纹理（列出2-3种代表性材质）
- 8k，高分辨率，电影级构图
- **必须完整包含通用实拍参数（general_params）**

输出格式：
{"scenes":[
  {"scene_number":1,"multi_panel_gpt":"四段式完整提示词"}
]}

重要：外层必须是 {"scenes":[...]}，不能是裸数组。
为下方列出的每一个场景生成 multi_panel_gpt，一个不能少。"""


def _fix_lighting_in_mp(mp_text):
    """修复多面板提示词中第二段的光影描述：如果过于概括，插入更具体的光影描述"""
    if not mp_text:
        return mp_text
    # 检查第二段是否过于简略（少于10个字）
    import re
    parts = re.split(r'\n\s*\n', mp_text)
    if len(parts) >= 3:
        # 暂时不做自动修复，仅确保格式完整
        pass
    return mp_text


def build_multipanel_prompt(script_text, existing_result, context=None, temp_kb=None):
    """第四轮：生成多面板布局参考图提示词（传入完整场景数据，含通用实拍参数等）"""
    scenes = existing_result.get('scenes', [])
    if not scenes:
        return MULTIPANEL_SYSTEM, '无场景数据'
    
    scene_summaries = []
    for s in scenes:
        sn = s.get('scene_number', '?')
        title = s.get('title', '')
        location = s.get('location', '')
        scene_type = s.get('scene_type', '')
        mood = s.get('mood', '')
        lighting = s.get('lighting_scheme', '')
        props_list = s.get('props', [])
        props = ', '.join(props_list[:8])
        chars = ', '.join(s.get('characters', [])[:3])
        info_card = s.get('scene_info_card', '')[:200]
        general = s.get('general_params', '')[:200]
        extraction = s.get('extraction_basis', '')[:150]
        wide = (s.get('wide_shot_gpt', '') or '')[:200]
        grid_nine = (s.get('grid_nine_gpt', '') or '')[:200]
        parts = [
            '[场景{0}] {1}'.format(sn, title),
            '  类型: {0} | 地点: {1}'.format(scene_type, location),
            '  光源: {0} | 氛围: {1} | 角色: {2}'.format(lighting, mood, chars),
            '  道具: ' + props,
            '  实拍参数: ' + general,
            '  提取依据: ' + extraction,
            '  信息卡: ' + info_card,
            '  全景版摘要: ' + wide,
            '  九宫格版摘要: ' + grid_nine,
        ]
        scene_summaries.append('\n'.join(parts))
    
    summary_text = '\n'.join(scene_summaries)
    user_prompt = (
        '剧本原文：\n' + script_text + '\n\n'
        '已有完整场景数据（含实拍参数、角色、道具、全景版提示词摘要等）：\n'
        + summary_text + '\n\n'
        '为以上每个场景生成【多面板布局参考图提示词】（multi_panel_gpt）。\n'
        '要求：\n'
        '1. 使用固定四段式结构，第一段根据场景类型选择合适模板\n'
        '2. 必须将通用实拍参数（general_params）加入画质与风格部分\n'
        '3. 全景版已有完整的场景描述，多面板版在此基础上做多视角排版设计\n'
        '4. 纯中文输出，实拍电影质感'
    )
    
    return MULTIPANEL_SYSTEM, user_prompt


def parse_multipanel_result(raw_text, existing_result):
    """解析第四轮结果，合并到现有场景数据中"""
    parsed = BaseExtractor._safe_json_parse_with_fallback(raw_text)
    if parsed is None or not isinstance(parsed, dict):
        return existing_result
    
    new_scenes = parsed.get('scenes', [])
    if not isinstance(new_scenes, list):
        return existing_result
    
    # 建立 scene_number → multi_panel_gpt 映射
    mp_map = {}
    for s in new_scenes:
        if isinstance(s, dict):
            sn = s.get('scene_number')
            mp = s.get('multi_panel_gpt', '')
            if sn and mp:
                mp_map[sn] = mp
    
    # 合并到现有结果
    result = dict(existing_result)
    merged_scenes = []
    for s in result.get('scenes', []):
        s = dict(s)
        sn = s.get('scene_number')
        if sn in mp_map:
            s['multi_panel_gpt'] = mp_map[sn]
        else:
            # 兜底：AI未输出时自动生成
            s['multi_panel_gpt'] = _generate_multi_panel(s)
            s['multi_panel_gpt'] = _fix_lighting_in_mp(s.get('multi_panel_gpt', ''))
        merged_scenes.append(s)
    result['scenes'] = merged_scenes
    return result


# ===== 九宫格剧情参考图（grid_nine_gpt）=====

GRID_NINE_SYSTEM = """你是GPT-Image-2实拍电影九宫格剧情板设计工程师。已有场景的分镜数据（含完整action描述、角色站位、台词、情绪），需要为每个场景设计九宫格剧情参考图提示词。

⚠️ 九宫格是剧情板（storyboard），不是场景设计板。每格画面展示的是「角色在演什么戏」，而非「场景长什么样」。场景只是背景，人物和剧情才是主体。

核心规则：
1. 9个格子必须按剧情时间顺序排列：1-1（开场）→ 1-2 → 1-3 → 2-1 → ... → 3-3（收尾）
2. 所有格子使用正常拍摄视角（平视/中近景），不使用俯视或鸟瞰
3. 【硬性要求】每格画面中至少有一个角色，必须有明确的动作或表情——禁止出现纯空镜/纯场景的格子
4. 角色站位必须和下方提供的分镜提示词保持一致——左侧就是左侧、右侧就是右侧
5. 每格画面描述要融入：景别 + 角色站位方向 + 谁在做什么动作/什么表情 + @标记，把这一格的剧情张力写出来
6. 提示词必须有assets字段（@标记），且与每格画面中的@标记一一对应
7. 纯中文输出，实拍电影质感

四段式提示词结构：
第一段（九宫格排版描述）：
九宫格剧情板，{场景名称}，3×3网格从左到右从上到下按时间排列：左上格-{时刻1}...右上格-{时刻3}，中左格-{时刻4}...中右格-{时刻6}，下左格-{时刻7}...下右格-{时刻9}，{场景类型}实拍电影，清晰分镜排版，画面以人物为主体

第二段（每格画面描述）：
逐格描述——每格必须包含：角色是谁、在什么位置、做什么动作/什么表情、面向谁。场景作为角色身后的背景交代，不是主体。

第三段（光影与色调）：
统一的光影方案，保证9格视觉一致性

第四段（画质与风格）：
超写实，超高细节，实拍电影质感，真实的材质纹理，8k，高分辨率，电影级构图

输出格式：
{"scenes":[
  {"scene_number":1,"assets":"@角色A。@角色B。@场景名","cells":[
    {"pos":"1-1","moment":"开场对峙","action":"中近景，画面左侧@A双手撑桌身体前倾怒视，画面右侧@B背靠门框双臂交叉冷冷回看——对峙张力拉满"},
    ...9格...
  ],
  "grid_prompt":"九宫格剧情板，{场景名}，..."}
]}

重要：外层必须是 {"scenes":[...]}，不能是裸数组。为下方列出的每一个场景生成 grid_nine_gpt，一个不能少。"""


def build_grid_nine_prompt(script_text, shots_data, scenes_data, context=None, temp_kb=None):
    """构建九宫格提示词：从分镜数据中提取关键镜头信息"""
    import json
    
    scene_summaries = []
    # 从分镜数据中提取每个场景的关键镜头
    shots_scenes = shots_data.get('scenes', [])
    
    for scene in shots_scenes:
        sn = scene.get('scene_number', '?')
        title = scene.get('scene_title', '')
        shot_list = scene.get('shots', [])
        
        parts = [f'[场景{sn}] {title}']
        
        # 提取分镜中的关键信息：完整action描述、角色站位、台词、情绪
        for shot in shot_list[:9]:  # 最多取前9镜
            sid = shot.get('shot_id', '?')
            assets = shot.get('assets', '')
            emotion = shot.get('emotion', '')
            intensity = shot.get('intensity', '')
            dialogue = shot.get('dialogue', '')
            camera = shot.get('camera', '')
            # 拼接完整timeline摘要
            timeline = shot.get('timeline', [])
            action_summary = []
            for t in timeline:
                if isinstance(t, dict):
                    tr = t.get('time_range', '')
                    act = t.get('action', '')
                    if act:
                        action_summary.append(f'{tr}: {act[:150]}')
            parts.append(f'  分镜{sid}: assets={assets} | 情绪={emotion}({intensity}) | 镜头={camera}')
            if dialogue:
                parts.append(f'    台词: {dialogue[:100]}')
            for a in action_summary:
                parts.append(f'    {a}')
        
        # 补充场景信息卡
        for s in (scenes_data.get('scenes', []) or []):
            if s.get('scene_number') == sn:
                parts.append(f'  场景信息: {s.get("scene_info_card", "")[:200]}')
                parts.append(f'  光影方案: {s.get("lighting_scheme", "")}')
                break
        
        scene_summaries.append('\n'.join(parts))
    
    summary_text = '\n'.join(scene_summaries)
    
    # 构建角色列表
    char_names = []
    if context:
        chars = context.get('characters', {})
        if isinstance(chars, dict):
            for c in chars.get('characters', []):
                n = c.get('name', '')
                if n:
                    char_names.append(n)
    
    user_prompt = (
        '剧本原文：\n' + script_text + '\n\n'
        '分镜数据（从中提取关键剧情时刻和角色站位）：\n'
        + summary_text + '\n\n'
        '出场角色：' + '、'.join(char_names) + '\n\n'
        '为以上每个场景生成【九宫格剧情参考图提示词】（grid_nine_gpt）。\n'
        '要求：\n'
        '1. 从分镜数据中提取9个关键剧情时刻，按时序排列\n'
        '2. 角色站位必须和分镜action中的描述保持一致\n'
        '3. assets字段列出所有@角色和@场景，与每格画面中的@标记一一对应\n'
        '4. 使用正常拍摄视角，纯中文输出，实拍电影质感'
    )
    
    return GRID_NINE_SYSTEM, user_prompt


def parse_grid_nine_result(raw_text):
    """解析九宫格结果"""
    parsed = BaseExtractor._safe_json_parse_with_fallback(raw_text)
    if parsed is None or not isinstance(parsed, dict):
        return {}
    
    grid_map = {}
    new_scenes = parsed.get('scenes', [])
    if isinstance(new_scenes, list):
        for s in new_scenes:
            if isinstance(s, dict):
                sn = s.get('scene_number')
                if sn:
                    grid_map[sn] = {
                        'assets': s.get('assets', ''),
                        'cells': s.get('cells', []),
                        'grid_prompt': s.get('grid_prompt', ''),
                    }
    return grid_map
