"""
分镜拆解 - Storyboard_Breakdown_Skills_v4.1
两轮提取：第一轮拆分镜框架，第二轮生成六模块详情
"""
# (C) foxpaw

import json
from .base import BaseExtractor

LIST_SYSTEM_BASE = """你是剧本动作链规划师。注意：后续分镜拆解时每个分镜需要3-5条动作链（每条约3-4s），整集不少于5个分镜 → 因此每集动作链总数不得低于18条（至少6镜×3条的余量，保证5镜稳稳成立），你规划的每场戏动作链加起来必须≥18。

输出格式（只输出JSON）：
{"scenes":[{"scene_title":"场景名","scene_number":1,"action_chain_count":8,"chain_summary":["@角色A 做动作1","@角色B 做动作2","@角色A 做动作3","@角色C 做动作4"]}],"total_scenes":0}

判断标准（根据剧情灵活判断，非固定）：
- 每个分镜容纳3-5条动作链，每集不少于5个分镜 → 每集动作链总数不得低于18条（5镜×3条的最低余量）。
- 动作链数量根据该场戏的剧情密度来定：平淡过场/简短对话→18-24条，中等情绪/多角色对话→24-30条，冲突爆发/动作追逐/复杂情绪→30条以上。
- 不要因为场景简单就只给几条——平静场景更需要通过细化眼神变化、呼吸节奏、微小动作来填充动作链，使情绪过渡自然。
- 每条动作链约3-4s，动作链总数 ÷ 3~5 = 该场景分镜数。整集各场戏的分镜加起来≥5个。
- 动作链的描述要体现合理的情绪过渡、说话语速节奏和动作呈现。"""

# LIST_SYSTEM 现在在 build_list_prompt 中动态构建

LIST_USER = "拆解所有场景的动作链数量规划。\n\n剧本：\n{script_text}\n角色：{character_context}\n场景：{scene_context}"

_STYLE_KB_CACHE = {}

def _load_style_kb(style):
    """加载风格知识库，带缓存"""
    if style in _STYLE_KB_CACHE:
        return _STYLE_KB_CACHE[style]
    kb_map = {
        "female": "Female_Director_Shot_Breakdown.json",
        "male": "Male_Director_Shot_Breakdown.json",
        "normal": "Storyboard_Breakdown_Skills_v4.1.json",
    }
    filename = kb_map.get(style, "Storyboard_Breakdown_Skills_v4.1.json")
    if style in ("female", "male"):
        # 女频/男频 KB 直接加载 JSON 并用 _format_director_kb 格式化
        import json, os, sys
        if getattr(sys, 'frozen', False):
            kb_dir = os.path.join(sys._MEIPASS, 'knowledge_base')
        else:
            kb_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'knowledge_base')
        kb_path = os.path.join(kb_dir, filename)
        try:
            with open(kb_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            result = BaseExtractor._format_director_kb(raw_data)
        except Exception:
            result = ""
    else:
        result = BaseExtractor._load_knowledge_base("Storyboard_Breakdown_Skills_v4.1.json")
    _STYLE_KB_CACHE[style] = result
    return result

_MICRO_KB_CACHE = None

def _load_micro_kb():
    global _MICRO_KB_CACHE
    if _MICRO_KB_CACHE is not None:
        return _MICRO_KB_CACHE
    import json, os, sys
    if getattr(sys, 'frozen', False):
        kb_dir = os.path.join(sys._MEIPASS, 'knowledge_base')
    else:
        kb_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'knowledge_base')
    kb_path = os.path.join(kb_dir, 'Micro_Expression_Skills_v1.0.json')
    try:
        with open(kb_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        result = _format_micro_kb(data)
        _MICRO_KB_CACHE = result
        return result
    except Exception:
        return ""

def _format_micro_kb(data):
    parts = []
    meta = data.get('meta', {})
    name = meta.get('name', '')
    ver = meta.get('version', '')
    desc = meta.get('description', '')
    if name:
        parts.append(f'# {name} v{ver}')
    if desc:
        parts.append(desc)
    usage = data.get('usage_note', '')
    if usage:
        parts.append('')
        parts.append('## 使用说明')
        parts.append(usage)
    cats = data.get('emotion_categories', {})
    if cats:
        parts.append('')
        for emotion, details in cats.items():
            parts.append(f'### {emotion}')
            face = details.get('面部', [])
            if face:
                parts.append('面部微表情：')
                for item in face:
                    parts.append(f'- {item}')
            body = details.get('肢体', [])
            if body:
                parts.append('肢体微动作：')
                for item in body:
                    parts.append(f'- {item}')
            parts.append('')
    return '\n'.join(parts)

def build_list_prompt(script_text, context=None, style="normal"):
    cc, sc = "", ""
    if context:
        if "characters" in context:
            d=context["characters"]; lst=d.get("characters",[]) if isinstance(d,dict) else d
            names=[c.get("name","") for c in lst] if isinstance(lst,list) else []; cc=", ".join(names)
        if "scenes" in context:
            d=context["scenes"]; lst=d.get("scenes",[]) if isinstance(d,dict) else d
            titles=[s.get("title","") for s in lst] if isinstance(lst,list) else []; sc=", ".join(titles)
    kb = _load_style_kb(style)
    system = LIST_SYSTEM_BASE + "\n\n---\n\n" + kb if kb else LIST_SYSTEM_BASE
    return system, LIST_USER.format(script_text=script_text, character_context=cc, scene_context=sc if sc else "暂无")

def parse_list(raw_text):
    parsed = BaseExtractor._safe_json_parse_with_fallback(raw_text)
    if parsed is None:
        return {"scenes":[],"total_scenes":0}
    return parsed

DETAIL_SYSTEM = """你是竖屏AI短剧导演。你的任务是把剧本拆解为Seedance可执行的电影级分镜，用镜头语言讲述故事。

必须处理的场景规划（已在用户消息中提供）：先确定本集分镜数量（不少于5个，剧情越复杂分镜越多），再将动作链分配进去。每个分镜3-5条action。优先保证分镜数量——当动作链总数不足时每个分镜取最低3条，不可为凑3-5条而减少分镜数。

【硬约束 — 必须遵守】
- @标记名称必须与下方「已提取资产名称」列表完全一致，一字不差。assets字段仅输出@标签本身，严禁括号或描述文字。
- assets字段列出的每个@标记必须在timeline的action中实际出现，timeline中出现的@标记也必须全部列入assets，二者一一对应。
- camera字段：纯中文术语，逗号分隔，格式如「中近景，平视角度，推进」。禁止英文缩写、+号或|号。
- 禁止任何解剖学肌肉/骨骼名称，全部转为肉眼可见的视觉化描述。
- 禁止「切回」「切至」「切换到」等硬切描述。Seedance是连续视频生成，视角转换必须用连续运镜描述（如「镜头快速横摇甩向」「画面惯性转向」）。
- camera字段的景别/运镜必须与第一条action一致。
- 仅对当前时间区间画面中正在可见的角色/道具/场景加@标记，画外/未出场/已退场的元素不加@。

【导演思维 — 如何写好action】
每条action是一段流动的画面叙事，不是技术清单。自然地融入这些元素：

镜头运动 — 以口语化方式带出景别和运镜，让Seedance感受到摄影机的存在感和节奏。「镜头缓缓推近，越过@A的肩膀」「固定凝视@B的脸，等待她的反应」「快速横摇跟随@C冲出门外」

人物状态与空间锚点 — 每条action必须让Seedance知道谁在哪里、面朝何方、彼此距离多远。

首条action建立空间锚点：明确每个出场角色的画面位置（左/右/中/前景/背景/画外）和面向方向。「画面左侧，@A身体前倾双手撑桌——画面右侧，@B靠在椅背上，视线避开@A偏向画面左下方」。
后续action只在人物移动时才更新位置，否则沿用首条action的空间关系。

眼神必须带方向：不是「@A看着@B」，而是「@A从画面右侧逼近，俯视坐着的@B」「@B抬头迎上@A的俯视目光」「@C低头避开两人，视线落在自己紧握的双手上」。

移动物体标注轨迹方向：不是「一辆轿车驶过」，而是「一辆黑色轿车从画面右侧驶入，沿道路向左前方渐远，尾灯在画面左侧边缘消失」。
运镜和人物位移必须区分清楚：「镜头向右横摇」是摄影机动；「@A向画面右侧走」是人物动。

情感弧线 — 每条action都要推进情绪。平静到波动、克制到释放、期待到失落——让Seedance感受到戏剧张力在累积或释放。连续两条action之间必须有承接（上一段的末状态 → 本段的起始状态）

台词标注 — 如果本段有台词，在action开头写：@角色名 说出台词'英文原文'，然后描述语调特征和口型反应。如果一句台词跨越两条action，两条都要标注。禁止出现「有台词但看不出谁在说话」的情况。

action整体≥35字。禁止「做动作」「说话」「看向对方」等笼统描述。不要加「节奏舒缓」「情绪积累」等标签式前缀。

【台词规则】
- 保留英文台词原文不变，dialogue字段使用英文原文。
- 英文台词下方加中文翻译注释：(建议删除: 中文翻译)。
- 每镜台词不超过3句。

【分镜输出结构 — 每个分镜包含以下字段】
assets: 纯@标签列表（@角色。@场景。@道具。）
lighting: 光影方案描述
camera: 纯中文镜头描述
emotion: 情绪基调
intensity: 情绪烈度 1-5/5
timeline: [{"time_range":"X.Xs-Y.Ys","action":"画面叙事描述"}, ...]  共3-5条，累加≤15s
dialogue: 台词（@角色名: 英文原文\n(建议删除: 中文翻译)）
sfx: 音效描述
end_frame: 定格画面描述
constraints: 完整约束文本

景别推荐：中近景（主力）/中景/特写/大特写/远景/全景

【JSON模板 — 每集≥5个分镜，仅展示单个结构】
{"scenes":[{"scene_title":"场景名","scene_number":1,"shots":[{"shot_id":"第一集 EPISODE 1 分镜 1-1-1","shot_number":1,"total_duration":15.0,"action_chains":4,"assets":"@小红。@小明。@重逢街头","lighting":"柔和的黄昏逆光，暖金色调从画面右上方斜射入画","camera":"中近景，平视角度，推进","intensity":"3/5","emotion":"温暖期待","timeline":[{"time_range":"0.0s-6.0s","action":"中近景镜头缓推进入，@重逢街头背景在浅景深中虚化——画面深处，@小红从远处走来身影逐渐放大，画面中央偏右，@小明站定面朝画面深处，目光追随@小红的身影，眼神从平静转为期待——慢镜头节奏让重逢的情绪充分发酵"},{"time_range":"6.0s-11.0s","action":"@小红走至画面左侧站定，与画面右侧的@小明面对面——面部特写固定凝视，@小明眼神从柔和逐渐湿润，嘴唇微张想说话却又抿紧，克制的情绪在第11秒突破，@小红露出温暖灿烂的笑容眼角挤出细纹，@小明跟着笑出声"},{"time_range":"11.0s-15.0s","action":"镜头缓慢拉远至远景固定，画面中央两人并肩而立——@小红在左@小明在右，夕阳逆光从两人之间穿过形成剪影，画面两侧虚化的路人穿行而过——沉默的余韵留给观众消化重逢的情感重量"}}],"dialogue":"@小明: \"好久不见\"\n(建议删除: \"好久不见\")","sfx":"轻风拂过树叶沙沙声，远处车辆通行楼宇底噪","end_frame":"夕阳逆光下，两人并肩而立的全景剪影，气氛安静温暖","constraints":"必须保留对白语音，人物说话时嘴型同步。仅隐藏视觉字幕显示：字幕透明度0%，禁用自动字幕，不显示任何台词文字在画面上。对话音频正常生成。电影级实拍摄影质感，禁止3D渲染/CGI/卡通风格，镜头运动平滑连续，不出现任何生图拼贴。无Logo，无文字，无字幕，无水印，无UI元素，无标志，无书本文字。连续电影级画幅连贯性，画幅比例锁定，无网格拼贴，无CGI/渲染/3D动画感，仅实拍电影质感。台词结束后停顿0.5秒，不要有背景音乐BGM。"}]}],"total_scenes":1,"total_shots":1,"summary":"概述"}

⚠️ 最终确认：(1)assets不含括号，与timeline一一对应 (2)camera纯中文逗号分隔 (3)无解剖术语/无硬切描述。

只输出JSON。每个分镜constraints必须完整。
"""

# DETAIL_SYSTEM 现在在 build_detail_prompt 中动态构建

def _format_emotion_timeline(et_data):
    parts = []
    scenes = et_data.get("scenes", [])
    if not scenes:
        return ""
    for scene in scenes:
        sn = scene.get("scene_number", "")
        st = scene.get("scene_title", "")
        parts.append("### \u7b2c" + str(sn) + "\u573a: " + str(st))
        chars = scene.get("characters", {})
        for char_name, char_data in chars.items():
            parts.append("#### " + str(char_name))
            arc = char_data.get("emotion_arc", [])
            for step in arc:
                stage = step.get("stage", "")
                emotion = step.get("emotion", "")
                intensity = step.get("intensity", "")
                trigger = step.get("trigger", "")
                parts.append("- " + str(stage) + ": " + str(emotion) + " (\u70c8\u5ea6" + str(intensity) + ") | \u89e6\u53d1: " + str(trigger))
        parts.append("")
    return "\n".join(parts)

def build_detail_prompt(script_text, plan, context=None, style="normal", emotion_timeline=None):
    plan_json = json.dumps(plan.get("scenes",[]), ensure_ascii=False, indent=2)
    kb = _load_style_kb(style)
    system = DETAIL_SYSTEM
    if kb:
        system += "\n\n---\n\n" + kb
    # 强制 @标记 名称一致性规则
    system += "\n\n---\n\n## \u2620\ufe0f 强制规则：@标记名称必须与\u300c已提取资产名称\u300d完全一致\n\n"
    system += "下方用户消息中提供了已提取的角色名、道具名、场景名列表。\n"
    system += "你在输出 assets 字段、timeline[].action 中的 @标记、dialogue 中的 @角色名 时，\n"
    system += "**必须使用列表中的精确名称，一字不差**。\n"
    system += "例如：列表中是\u300c哈里森\u300d，则只能写 @哈里森，绝不能写 @Harrison、@哈里森\u00b7xxx 等变体。\n"
    system += "这是最高优先级规则，违反将导致下游 Seedance 无法匹配资产图片。"
    micro_kb = _load_micro_kb()
    if micro_kb:
        system += "\n\n---\n\n## 人物微表情动作参考（在动作链action字段中参考使用）\n\n" + micro_kb
    if emotion_timeline:
        et_text = _format_emotion_timeline(emotion_timeline)
        if et_text:
            system += "\n\n---\n\n## 角色情绪时间线（分镜编写时必须参考，每条action的微表情必须匹配当前时间段的情绪状态）\n\n" + et_text
    # 构建已提取资产名称列表
    asset_names_block = ""
    if context:
        char_names = []
        chars = context.get('characters', {})
        if isinstance(chars, dict):
            for c in chars.get('characters', []):
                n = c.get('name', '')
                if n:
                    char_names.append(n)
        prop_names = []
        props = context.get('props', {})
        if isinstance(props, dict):
            for p in props.get('props', []):
                n = p.get('name', '')
                if n:
                    prop_names.append(n)
        scene_names = []
        scs = context.get('scenes', {})
        if isinstance(scs, dict):
            for s in scs.get('scenes', []):
                n = s.get('title', '')
                if n:
                    scene_names.append(n)
        if char_names or prop_names or scene_names:
            asset_names_block = "\n\n已提取资产名称（@标记必须使用以下精确名称）：\n"
            if char_names:
                asset_names_block += "角色: " + ", ".join(char_names) + "\n"
            if prop_names:
                asset_names_block += "道具: " + ", ".join(prop_names) + "\n"
            if scene_names:
                asset_names_block += "场景: " + ", ".join(scene_names) + "\n"
    return system, f"剧本：\n{script_text}\n\n动作链规划（必须按此数量分配到各分镜，每个分镜3-5条动作链，整集≥5个分镜，具体根据剧情而定）：\n{plan_json}{asset_names_block}\n\n只输出JSON。每个分镜constraints必须完整。"

def parse_result(raw_text):
    parsed = BaseExtractor._safe_json_parse_with_fallback(raw_text)
    if parsed is None or not isinstance(parsed, dict):
        return {"scenes":[],"total_scenes":0,"total_shots":0,"summary":"解析失败","raw":raw_text[:500] if isinstance(raw_text, str) else "EMPTY"}
    s = parsed.get("scenes") or parsed.get("storyboard") or []
    if isinstance(s,dict): s = list(s.values())
    if not isinstance(s,list): s = []
    ts = parsed.get("total_shots")
    if ts is None: ts = sum(len(x.get("shots",[])) for x in s)
    tsc = parsed.get("total_scenes")
    return {"scenes":s,"total_scenes":tsc if tsc is not None else len(s),"total_shots":ts,"summary":parsed.get("summary") or "","directing_notes":parsed.get("directing_notes",""),"raw":"(保留原始返回待调试)"}
