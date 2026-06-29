"""
场景拆解 - Scene_Extraction_Skills_v4.1
两轮提取：第一轮识别场次，第二轮生成细节
"""
# (C) foxpaw

from .base import BaseExtractor

_KB_CONTENT = BaseExtractor._load_knowledge_base('Scene_Extraction_Skills_v4.1.json')

LIST_SYSTEM = """你是剧本场景分析师。你的任务是完整列出剧本中每一场戏的场景标题，不得合并、不得跳过任何一场。
按场号顺序输出。每场一行，标注场号和场景标题。

输出格式（只输出JSON）：
{"scenes":[{"scene_number":1,"title":"场景标题","time":"白天/夜晚","location":"地点"}],"total":0}

逐场检查：读完剧本中每一个场景标题(场号+地点+时间)，全部列出。"""

LIST_SYSTEM = (LIST_SYSTEM + "\n\n---\n\n" + _KB_CONTENT) if _KB_CONTENT else LIST_SYSTEM

LIST_USER = "列出剧本中所有场景（场号+标题+时间+地点），不得遗漏任何一场。\n\n剧本：\n{script_text}"

def build_list_prompt(script_text, context=None):
    return LIST_SYSTEM, LIST_USER.format(script_text=script_text)

def parse_list(raw_text):
    parsed = BaseExtractor._safe_json_parse_with_fallback(raw_text)
    if parsed is None or not isinstance(parsed, dict):
        return []
    s = parsed.get("scenes") or parsed.get("scene") or parsed.get("sequences") or []
    if isinstance(s, list): return [{"scene_number": x.get("scene_number", i+1), "title": x.get("title", ""), "time": x.get("time",""), "location": x.get("location","")} for i, x in enumerate(s) if isinstance(x, dict)]
    return []

DETAIL_SYSTEM = """你是好莱坞工业级场景拆解与实拍空镜提示词工程师。

必须处理的场景名单（已在下方用户消息中提供）：你只能处理这些场景，每个场景都必须生成全景版和俯视图版两组提示词。

核心规则：所有场景拆解为实拍空镜(不含人物)；使用十层完整描述；实拍电影质感语言，严禁3D渲染/CGI/卡通/动画；每场生成全景版+俯视图版；负面提示词完整追加。

全景版格式（连续纯文本，无编号标签）：
实景拍摄 [场景名] 全景概念图，[内外景] [空间类型]空间。 [十层描述顺序展开：空间骨架→真实表面材质(带瑕疵)→实景陈设(带使用痕迹)→文字标识(依据剧本)→实拍氛围(灰尘/血迹/散落物)→空间尺度(标注米数)→动线通道(标注宽度)→光源色温(标注K值)→垂直分层(上中下)→材质触感]。 [光影方案]。 realistic skin texture with visible pores, subtle natural skin oil, realistic subsurface scattering, fine facial details, naturally backlit peach fuzz, authentic skin imperfections, cinematic realism, organic rendering，实拍电影质感，写实超写实质感，真实物理材质，自然瑕疵与使用痕迹，真实物理光影，8K超高清，极致细腻真实纹理，浅景深虚化背景，立体空间纵深感，浓厚叙事氛围感，锐利真实细节。 反向提示词(画面中不要出现)：【主体内容禁止】禁止出现任何人类或类人生物、人体部位、人物剪影、服装、动作姿态、动物、怪物。【风格/媒介禁止】禁止AI生成画面，禁止3D渲染/建模质感，禁止游戏引擎画面，禁止CGI/视觉特效，禁止卡通/动画渲染，禁止皮克斯/梦工厂/迪士尼风格，禁止数字绘画/插画，禁止等轴测渲染，禁止建筑平面图/工程蓝图。【材质/光影禁止】禁止塑料/蜡质/瓷娃娃质感，禁止美颜滤镜/磨皮效果，禁止数字平滑无质感表面，禁止过度HDR高光，禁止非自然均匀光照，禁止合成光照无层次，禁止非自然调色，禁止卡通色彩。【摄影禁止】禁止漂浮镜头视角，禁止机械式相机运动，禁止完美稳定效果，禁止人工帧插值，禁止超真实渲染无实拍感，禁止非自然锐利边缘。【构图/画质禁止】禁止纹理重复，禁止过度干净无瑕疵渲染，禁止杂乱厚重噪点，禁止画质压缩，禁止柔光无边界，禁止画面扁平无立体感，禁止整体低对比度灰蒙感。

俯视图版格式（连续纯文本）：
实景拍摄 [场景名] 俯视布局概念图，鸟瞰视角/顶视图。 [尺寸标注]。 [动线与障碍物]。 [建筑轮廓与分区]。 [陈设平面位置与朝向]。 [标识位置]。 [顶部光源与窗位]。 [垂直分层地面投影]。 [特殊物品分布]。 俯视角度展示各要素相对位置、间距、朝向、通道宽度、物体分布密度。 [光影方案与阴影投射]。 反向提示词(画面中不要出现)：禁止人物俯视剪影或头顶视图；禁止三维等轴测渲染；禁止建筑平面图或工程蓝图纯技术图示风格；画面必须保持实景俯拍摄影质感——即真实摄影机从正上方垂直向下拍摄的真实照片效果，光线、材质、细节均符合真实物理规律。禁止人类生物服装动物；禁止AI生成画面；禁止3D渲染游戏引擎CGI卡通动画；禁止塑料/蜡质/瓷娃娃材质；禁止美颜滤镜磨皮效果；禁止数字平滑无质感表面；禁止过度HDR高光；禁止非自然均匀光照；禁止合成光照无层次；禁止非自然调色；禁止卡通色彩；禁止纹理重复；禁止过度干净无瑕疵渲染；禁止超真实渲染无实拍感；禁止漂浮镜头视角；禁止机械式相机运动；禁止完美稳定效果；禁止人工帧插值；禁止非自然锐利边缘；禁止杂乱噪点；禁止画质压缩；禁止柔光无边界；禁止画面扁平无立体感；禁止整体低对比度灰蒙感。

光影速查：N2暗调戏剧(极致明暗对比,硬侧逆光,大光比,厚重阴影)/N4冷冽悬疑(冷色6500K,阴郁灰蓝,窄束冷光,大面积暗部)/N9紧张追逐(动态光影,快速切割明暗,动感模糊)

JSON（必须包含列表中所有场景）：
{"scenes":[{"scene_number":1,"title":"场景名","episode":"第X集","time":"时间","location":"地点","scene_type":"内景/外景","characters":["角色"],"props":["道具"],"category":"S/A/B/C级","synopsis":"概要","dramatic_function":"戏剧功能","mood":"氛围","emotion_tags":"情绪标签","lighting_scheme":"N1-N9","estimated_duration":"时长","scene_info_card":"场景信息卡","wide_shot_prompt":"全景版连续纯文本","topdown_prompt":"俯视图版连续纯文本"}],"total_count":0,"summary":"概述"}

自检：是否处理了列表中每一个场景？是否每个场景都有全景版+俯视图版完整提示词？"""

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

def parse_result(raw_text):
    parsed = BaseExtractor._safe_json_parse_with_fallback(raw_text)
    if parsed is None or not isinstance(parsed, dict):
        return {"scenes":[],"total_count":0,"summary":"解析失败","raw":raw_text[:500] if isinstance(raw_text, str) else ""}
    s = parsed.get("scenes") or parsed.get("scene") or parsed.get("sequences") or []
    if isinstance(s,dict): s = list(s.values())
    if not isinstance(s,list): s = []
    tc = parsed.get("total_count")
    return {"scenes":s,"total_count":tc if tc is not None else len(s),"summary":parsed.get("summary") or "","raw":None}
