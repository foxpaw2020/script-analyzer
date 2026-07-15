"""
场景拆解 - Scene_Extraction_Skills_v5.2
两轮提取：第一轮识别场次，第二轮生成细节
"""
# (C) foxpaw, 2026-07-15

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

提示词必须严格遵循下方知识库规范中定义的十层描述法、光影方案、画质标准和输出模板，不得省略任何要素。

输出格式必须是包裹在 {"scenes":[...]} 中的JSON对象，不能是裸数组：

{"scenes":[
  {"scene_number":1,"title":"场景名","episode":"第X集","time":"时间","location":"地点","scene_type":"内景/外景","characters":["角色"],"props":["道具"],"category":"S/A/B/C级","synopsis":"概要","dramatic_function":"戏剧功能","mood":"氛围","emotion_tags":"情绪标签","lighting_scheme":"N1-N9光照方案ID","estimated_duration":"时长","scene_info_card":"| 项目 | 内容 |\n|------|------|\n| 空间类型 | ... |\n| 材质清单 | ... |\n| 陈设道具 | ... |\n| 光影方案 | ... |\n| 氛围基调 | ... |\n| 提取依据 | ... |\n| 微气候 | ... |\n| 实拍参数 | ... |","extraction_basis":"提取依据（引用剧本原文）","wide_shot_gpt":"全景版 GPT-Image-2 完整提示词（已融入场景信息卡数据）","topdown_gpt":"俯视图版 GPT-Image-2 完整提示词（已融入场景信息卡数据）","multi_panel_gpt":"多面板布局参考图 GPT-Image-2 完整提示词（已融入场景信息卡数据）"}
],
"total_count":0,
"summary":"概述"}

重要：输出最外层是 {"scenes":[...],"total_count":N,"summary":"..."}，绝对不能是裸数组 [...]。
每个场景必须包含上述全部字段。"""

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
        topdown = (s.get('topdown_gpt', '') or '')[:200]
        parts = [
            '[场景{0}] {1}'.format(sn, title),
            '  类型: {0} | 地点: {1}'.format(scene_type, location),
            '  光源: {0} | 氛围: {1} | 角色: {2}'.format(lighting, mood, chars),
            '  道具: ' + props,
            '  实拍参数: ' + general,
            '  提取依据: ' + extraction,
            '  信息卡: ' + info_card,
            '  全景版摘要: ' + wide,
            '  俯视图版摘要: ' + topdown,
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


# ===== 俯视图版（topdown_gpt）=====

TOPDOWN_SYSTEM = """你是GPT-Image-2实拍电影场景俯视图设计师。已有场景的全景版提示词和场景信息卡，需要为每个场景设计一张【俯视平面布局图提示词】。

核心规则：
1. 严格空镜——不含任何人物/人体/服装/动物
2. 上帝视角——正上方俯拍，展示完整的空间平面布局
3. 从已有的全景版提示词和场景信息卡中提取空间结构信息
4. 实拍电影质感，禁止3D渲染/CGI/游戏/卡通
5. 仅中文输出

提示词格式（连续文本）：
俯视图，{场景名称}，{空间类型}的上帝视角平面布局，显示所有关键区域的空间关系和尺寸比例，{主要房间/区域}在画面的{位置}，{家具/道具}的摆放位置和相对尺度，清晰的动线示意，{光影方案}从上方均匀投射，{材质}的地面和墙面纹理可见，超写实，超高细节，真实的材质纹理（列出2-3种代表性材质），8k，高分辨率，建筑表现图风格，电影级构图。

输出格式：为下方列出的每一个场景生成 topdown_gpt，一个不能少。
{scenes:[{scene_number:1,topdown_gpt:俯视图提示词},...]}"""


def build_topdown_prompt(script_text, scenes_data, context=None, temp_kb=None):
    """构建俯视图提示词：从场景数据中提取空间结构信息"""
    scene_summaries = []
    
    for scene in (scenes_data.get('scenes', []) or []):
        sn = scene.get('scene_number', '?')
        title = scene.get('title', '')
        info = scene.get('scene_info_card', '')[:400]
        wide = scene.get('wide_shot_gpt', '')[:300]
        lighting = scene.get('lighting_scheme', '')
        scene_type = scene.get('scene_type', '')
        props = ', '.join(scene.get('props', [])[:8])
        
        scene_summaries.append(
            '[场景{}] {} | {}\n'
            '  全景摘要: {}\n'
            '  场景信息卡: {}\n'
            '  光影方案: {}\n'
            '  道具: {}'.format(sn, title, scene_type, wide, info, lighting, props)
        )
    
    summary_text = '\n'.join(scene_summaries)
    
    user_prompt = (
        '剧本原文：\n' + script_text + '\n\n'
        '场景数据（从中提取空间结构信息）：\n'
        + summary_text + '\n\n'
        '为以上每个场景生成【俯视图提示词】（topdown_gpt）。\n'
        '要求：\n'
        '1. 从场景信息卡和全景版提示词中提取空间骨架、材质、道具摆放\n'
        '2. 描述各区域的相对位置和尺度关系\n'
        '3. 纯中文输出，实拍电影质感，禁止3D渲染/CGI\n'
        '4. 严格空镜，不出现人物'
    )
    
    return TOPDOWN_SYSTEM, user_prompt


def parse_topdown_result(raw_text):
    """解析俯视图结果"""
    parsed = BaseExtractor._safe_json_parse_with_fallback(raw_text)
    if parsed is None or not isinstance(parsed, dict):
        return {}
    td_map = {}
    new_scenes = parsed.get('scenes', [])
    if isinstance(new_scenes, list):
        for s in new_scenes:
            if isinstance(s, dict):
                sn = s.get('scene_number')
                if sn:
                    td_map[sn] = s.get('topdown_gpt', '')
    return td_map

