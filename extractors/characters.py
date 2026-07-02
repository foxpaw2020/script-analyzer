"""
角色提取 - 两轮提取：第一轮列清单，第二轮生成细节
"""
# (C) foxpaw

from .base import BaseExtractor

_KB_CONTENT = BaseExtractor._load_knowledge_base('Character_Extraction_Skills_v4.0.json')

LIST_SYSTEM = """你是剧本角色分析师。从剧本第一行到最后一行，逐行扫描，找出每一个有名字或台词的角色。

强制步骤：
1. 先数一数总共多少个角色
2. 逐一列出每个角色的名字
3. 确认列出的数量等于数的数量

包括：主角、配角、群众演员、路人、服务员、司机等所有**实际出场**的角色。去重合并同名不同称呼。

注意：画外音(VO/OS)、旁白、电话里的声音等**未实际出场**的声音角色不计入名单。

角色名格式：统一使用「英文名（中文名）」，如 Zoe（佐伊）、Ethan（伊森）。仅有英文名时只用英文名，仅有中文名时只用中文名。

输出纯JSON，不带任何其他文字：
{"characters":["名1","名2","名3"],"total":数量}"""

# 第一轮不做知识库注入（知识库内容为角色详情提取规则，与名单罗列任务无关，会干扰AI输出）

LIST_USER = "完整列出以下剧本中所有角色名，不得遗漏任何一个。\n\n剧本：\n{script_text}"

def build_list_prompt(script_text, context=None):
    return LIST_SYSTEM, LIST_USER.format(script_text=script_text)

def parse_list(raw_text):
    parsed = BaseExtractor._safe_json_parse_with_fallback(raw_text)
    if parsed is None or not isinstance(parsed, dict):
        return []
    names = parsed.get("characters") or parsed.get("character") or parsed.get("names") or []
    if isinstance(names, list):
        return [n for n in names if isinstance(n, str) and n.strip()]
    return []

DETAIL_SYSTEM = """你是好莱坞工业级角色资产提取与提示词工程师。

必须处理的角色名单（在用户消息中提供）：你只能处理这些角色，不得增减。每个角色都必须生成完整信息卡和提示词。

每个角色输出：信息卡（角色简介+性格弧光）+ 连续纯文本提示词。

提示词格式（连续文本，无编号标签）：
左侧锁骨以上全脸特写+右侧三视图(正面视角、四分之三侧面视角、正侧面视角、背面视角)，中立T字站姿，[年龄种族标注]。 [外貌特征]。 [服装配饰]。 [身上文字标识]。 [性格气质]。 纯白背景。 realistic skin texture with visible pores, subtle natural skin oil, realistic subsurface scattering, fine facial details, naturally backlit peach fuzz, authentic skin imperfections, cinematic realism, organic rendering，Netflix剧集级角色肖像质感，Arri Alexa摄影机拍摄，HDR高动态范围影像，精致色彩分级，画面通透干净，亮部细节丰富不死白，暗部层次清晰不死黑，柔和对比度，均匀自然曝光，4K/8K超高清分辨率，电影级构图，自然肤色还原。 电影级角色肖像质感，写实超写实质感，真实物理材质与皮肤纹理，自然瑕疵与使用痕迹，真实物理光影，8K超高清，极致细腻真实纹理，浅景深虚化背景，立体空间纵深感，浓厚叙事氛围感，无损高清画质，锐利真实细节。 同一个人物角色，面部特征统一一致，全程穿着同一套服装，服装细节完全相同，相同体型，体格特征一致，保持相同年龄面貌，发型一致，发色统一，文字标识一致。 反向提示词：不要出现AI生成面孔，CGI质感，游戏引擎画面，塑料/蜡质皮肤，瓷娃娃皮肤，美颜滤镜，磨皮过度，过度锐化，数字平滑感，过度干净渲染，过度HDR，高光油腻，非自然面部比例，完美对称，合成光照，均匀光照，非自然眼部反光，虚假景深，人工电影模糊，非自然调色，卡通色彩，纹理重复，漂浮镜头，机械相机运动，完美稳定，人工帧插值，超真实渲染，非自然锐利边缘。

输出JSON（必须包含列表中所有角色，name 字段统一为「英文名（中文名）」格式）：
{"characters":[{"name":"角色名","age_race":"年龄种族","role_type":"主角/配角/龙套","episodes":"第X集","description":"角色描述","personality":["性格"],"relationships":[{"target":"关联角色","relation":"关系"}],"text_signage":"文字标识","info_card":"角色简介+性格弧光","prompt":"连续纯文本提示词"}],"total_count":0,"platform":"Netflix","summary":"概述"}"""

DETAIL_SYSTEM = (DETAIL_SYSTEM + "\n\n---\n\n" + _KB_CONTENT) if _KB_CONTENT else DETAIL_SYSTEM

def build_detail_prompt(script_text, names, context=None, temp_kb=None):
    nl = "\n".join(f"- {n}" for n in names)
    # 注入人物小传
    char_context = ""
    if temp_kb and temp_kb.get("characters"):
        char_context = BaseExtractor._format_temp_characters(temp_kb["characters"])
    system = DETAIL_SYSTEM + char_context if char_context else DETAIL_SYSTEM
    return system, f"剧本：\n{script_text}\n\n以下角色名单必须全部处理({len(names)}个)，一个不能少：\n{nl}\n\n只输出JSON。"

def parse_result(raw_text):
    parsed = BaseExtractor._safe_json_parse_with_fallback(raw_text)
    if parsed is None or not isinstance(parsed, dict):
        return {"characters":[],"total_count":0,"summary":"解析失败","raw":raw_text[:500] if isinstance(raw_text, str) else "EMPTY"}
    chars = parsed.get("characters") or parsed.get("character") or parsed.get("cast") or parsed.get("roles") or []
    if isinstance(chars,dict): chars = list(chars.values())
    if not isinstance(chars,list): chars = []
    tc = parsed.get("total_count")
    return {"characters":chars,"total_count":tc if tc is not None else len(chars),"platform":parsed.get("platform","Netflix"),"summary":parsed.get("summary") or "","raw":"(保留原始返回待调试)"}
