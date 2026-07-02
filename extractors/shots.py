"""
分镜拆解 - Storyboard_Breakdown_Skills_v4.1
两轮提取：第一轮拆分镜框架，第二轮生成六模块详情
"""
# (C) foxpaw

import json
from .base import BaseExtractor

LIST_SYSTEM_BASE = """你是剧本分镜规划师。你的任务是拆解每个场景需要几个分镜，仅给出分镜数量和核心动作概要。

输出格式（只输出JSON）：
{"scenes":[{"scene_title":"场景名","scene_number":1,"shot_count":3,"shots_summary":["@角色A 做动作1","@角色B 做动作2"]}],"total_scenes":0}

判断标准：简单场景1镜，中等2-4镜，复杂5-10镜。不要遗漏任何场景。"""

# LIST_SYSTEM 现在在 build_list_prompt 中动态构建

LIST_USER = "拆解所有场景的分镜数量规划。\n\n剧本：\n{script_text}\n角色：{character_context}\n场景：{scene_context}"

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

DETAIL_SYSTEM = """你是竖屏AI短剧好莱坞分镜拆解与提示词工程师。

必须处理的分镜规划（已在用户消息中提供）：你必须按规划数量为每个场景生成全部分镜，一个不能少。

核心规则：角色/道具/场景前加@标记；所有镜头术语统一使用中文；每个分镜总时长≤15s，动作链条数和每段时长完全根据剧情走势推演，不预设条数限制；从导演视角判断这15s内最合理的演绎节奏；提取画面文字标识；纯中文输出。

【Seedance 2.0 兼容性规则】
- 禁止解剖学术语：不使用任何肌肉/骨骼/筋膜的专业名称（如「颧大肌」「颈阔肌」「眼轮匝肌」等），全部转为肉眼可见的视觉化描述（如「脸颊肌肉绷紧」「颈部两侧皮肤拉出线条」「眼角挤出细纹」）。
- 禁止画面硬切：Seedance 是连续视频生成，分镜内不能出现「切回」「切至」「切换到」等剪辑概念。如需转换视角，必须使用连续运镜描述（如「镜头快速横摇从A甩向B」「画面在惯性带动下转向C」）。
- 竖屏9:16构图：每个分镜必须考虑竖屏画幅——主体在画面中下部偏左/右的位置、背景虚化层次、上层留白空间。避免使用适合横屏的「左/右排列」构图，优先「上/下纵深」构图。
- @标记规则：仅对当前动作链时间区间内画面中**正在可见**的角色/道具/场景加@标记。画外音、未出场、已退场、被遮挡的元素**不加@标记**。
- camera 一致性：每个分镜的 camera 字段（核心属性）必须与第一条动作链的景别/运镜保持一致。

【资产字段硬性规则】主体资产(Assets)字段**严禁**使用括号：仅输出@人物、@场景、@道具名称本身，禁止添加任何括号说明、描述文字或修饰语（如"@Kane（身着西装）"为错误格式）。正确格式："@Kane。@Laura。@欢迎宴会大厅"。

【镜头字段硬性规则】镜头(Camera)字段**必须**使用纯中文术语，逗号分隔：格式为「中文景别，中文角度，中文运镜」。正确示例："中近景，平视角度，推进" | 错误示例："VCU + Eye Level + Slow Push In"。禁止使用任何英文缩写或英文单词，禁止使用+号或|号作为分隔符。

【节奏设计规则】
节奏不预设任何机械比例，由导演根据剧情走势来推演。原则：
- 思考这15s内剧情要表达的核心是什么——是一个凝视的张力？一段追逐的紧迫？一句台词的余韵？
- 围绕这个核心，该快的地方快（追逐、爆发、翻转），该慢的地方慢（凝视、蓄力、沉默后的反应）
- 留白也是叙事——不一定填满15s，有时候停在某个表情上比继续推进更有力量
- 节奏角色的标注（铺垫、积累、爆发、过渡、收束）仍然使用，但不绑定固定时长比例——一个铺垫可以只占1s，一个收束可以占5s

【剧本子文本解读规则】
分析每场戏时必须穿透表层文本读取子文本：
- 台词≠情绪：角色嘴上说的和心里感受经常相反。识别潜台词——如Kane说「不好意思」实为炫耀，Grant沉默是愤怒。emotion标注真实情绪而非表面台词。
- 场景氛围锚点：灯光冷暖、空间大小、天气暗示情绪底色。宴会厅灯光打在脸上是权力金色还是压抑灰色？
- 关系张力：每对角色间存在权力差（谁高谁低）、亲密度（亲密/疏远/敌对）、历史恩怨。这些直接影响微表情选择——高权力方微表情外放，低权力方压制内敛。
- 情绪转折信号：在剧本中精准找出触发情绪变化的节点——一句台词、一个动作、一次目光接触、一段沉默。转折点前后微表情应有明显切换。

【动作链描述要求】
每条动作链的action字段必须是一段流畅的中文叙事句，将景别、运镜方式自然地融入画面描述中——不要用标签或分隔符标注景别和运镜，而是以口语化的方式在叙述中带出。例如：「中近景镜头缓推进入，@小红从远处走来，身影逐渐放大……」而非「shot_size:中近景，camera_movement:推进」。
action字段内容按顺序覆盖：(1)节奏定位——以Seedance可理解的中文自然表述（如「节奏舒缓铺垫」「瞬间爆发高潮」「情绪渐缓收束」），(2)景别与运镜——自然融入口语化描述，(3)画面内容——角色具体姿态（站/坐/走/跑/转头/抬手等）、表情变化（参考微表情知识库中的面部微表情和肢体微动作）、空间位移方向和距离、与道具的交互方式、画面中出现的文字标识——全部含@标记。整个action字段≥35字。禁止"做动作""说话""看向对方"等笼统描述。

【连续衔接规则】
每条动作链的action必须具备前后衔接能力，不能各自独立写成孤立的片段：

一、人物状态连续衔接——除第一条动作链外，每条action开头必须包含约10-15字的承接句，将上一段末尾的人物情绪和姿态平滑过渡到当前段。承接句应引用上一段的尾状态作为起点，再引出当前段的新发展。示例：
- 「Kane的冷笑在嘴角凝固半秒后逐渐褪去，转为冷峻的审视」（承接「冷笑」→过渡到「审视」）
- 「从刚才的对视中缓缓抽离，眼神垂落至地面」（承接「对视」→过渡到「低头」）
- 「泪水在眼眶中积聚到极限后终于突破表面张力滑落」（承接「含泪」→过渡到「落泪」）

二、镜头语言连续过渡——相邻两条动作链的景别和运镜**不能跳跃**：
- 特写→远景：action中必须描述拉远过程（如「镜头从特写缓缓拉远至远景」）
- 固定→快速横摇：action中必须描述加速启动过程（如「固定镜头停顿半秒后骤然加速向右横摇」）
- 推进→拉远：中间必须描述停顿再反向（如「镜头推到最近处停住，停顿约半秒后开始反向拉远」）
- 景别差≤2档：中景→特写可直接过渡；中景→远景必须经过至少一次推进或拉远
【说话动作规则】如果某条动作链的时间区间内有台词，action 末尾必须加入说话动作描述——明确标注谁在说、语调特征（挑衅上扬/低声压抑/带着笑意等）、以及可见的口型或喉部反应（如嘴唇张合逐字吐出、喉结随发声微微滚动、嘴角因语气加重而单侧上扬）。

台词规则：
- 保留剧本中的英文台词原文不变。
- 英文台词下方另起一行，加中文翻译注释，格式：`(建议删除: 中文翻译)`。
- 总时长≤15s的分镜中，台词不得超过3句（英文原文1句计1句，翻译不计入句数）。

竖屏推荐景别：中近景（主力）/中景/特写/大特写/远景/全景

每个分镜包含六模块：
1.核心属性：主体资产(Assets) — 纯@标签列表，仅输出@人物、@场景、@道具名称本身，严禁添加任何括号说明、描述文字或修饰语。正确示例: "@Kane。@Laura。@欢迎宴会大厅。@Kane的西装袖口。@Kane的钱包" | 错误示例: "@Kane（身着西装，气场张扬）。@欢迎宴会大厅（水晶吊灯、长桌）"。光影: 光影方案描述
镜头【纯中文·逗号分隔】: 中文景别，中文角度，中文运镜（禁止英文术语、禁止+号|号分隔）
视线: 视线方向描述
贴脸距离(Proximity): 用肉眼可感知的视觉方式描述（如「面部占据画面下2/3」「两人之间隔着一张长桌的纵深」「人物剪影在远景中仅占画面高度1/10」），禁止使用精确米数
情绪烈度: 等级/5
情绪: 情绪基调
3.秒级动作链（对象格式，每条含2个字段）：
   time_range: 时间区间（格式"X.Xs-Y.Ys"，第一段从0.0s起，前一段结束时间=后一段起始时间）
   action: 动作/画面描述——一段流畅中文叙事句，开篇先以Seedance可理解的表述带出本段节奏定位（如「节奏舒缓铺垫」「情绪逐渐积累」「瞬间爆发高潮」「平滑过渡转场」「节奏渐缓收束」），然后自然融入景别感（如「中近景镜头」「面部特写」）和运镜方式（如「缓推进入」「快速横摇跟随」「固定镜头凝视」），接着展开画面内容（角色姿态+微表情微动作+位移方向+@标记+文字标识+道具交互），整体action字段≥35字。注意：节奏描述必须用中文口语化表述，不要用英文或标签式标注
4.声音与台词：台词(@角色名: 英文原文\n(建议: 中文翻译))+音效SFX
5.收尾画面：定格画面描述
6.统一约束(完整文本)：视频中不得出现字幕，如有台词，对话旁白等，均使用默认字体，字体不透明度为0%。不生成字幕，禁用自动字幕，无台词字幕。电影级实拍摄影质感，禁止AI生成画面，禁止3D渲染/CGI/卡通风格，镜头运动平滑连续，不出现任何生图拼贴。禁止漂浮镜头视角，禁止机械式相机运动，禁止完美稳定效果，禁止人工帧插值。无Logo，无文字，无字幕，无水印，无UI元素，无标志，无书本文字。连续电影级画幅连贯性，画幅比例锁定，无网格拼贴，无CGI/渲染/3D动画感，仅实拍电影质感。禁止美颜滤镜，禁止过度锐化，禁止数字平滑感，禁止过度干净渲染，禁止非自然均匀光照。台词结束后停顿0.5秒，不要有背景音乐BGM。

输出时 shot_id 必须在前面标注所属集数，格式：第X集 EPISODE X 分镜 N-M-P（如 "第一集 EPISODE 1 分镜 1-1-1"、"第二集 EPISODE 2 分镜 2-3-5"）。

⚠️ **最终输出前再次确认**：(1) assets 字段每个 @ 标签后**不得跟任何括号或描述**，仅标签本身；(2) camera 字段**必须使用纯中文**（如"中近景，平视角度，推进"），禁止英文和+号。

JSON模板（必须按规划数量生成所有分镜）：
{"scenes":[{"scene_title":"场景名","scene_number":1,"shots":[{"shot_id":"第一集 EPISODE 1 分镜 1-1-1","shot_number":1,"total_duration":15.0,"action_chains":3,"assets":"@Kane。@Laura。@欢迎宴会大厅。@Kane的西装袖口","lighting":"光影方案","camera":"中近景，平视角度，推进","intensity":"3/5","emotion":"情绪基调","rhythm_notes":"本分镜节奏：慢推铺垫(3.5s)→面部特写积累情绪(4.5s)→对视微笑高潮(3s)→拉远收束(1s)，情绪弧从期待→温暖释然","timeline":[{"time_range":"0.0s-6.0s","action":"节奏舒缓铺垫，中近景镜头缓推进入，@小红从远处走来身影逐渐在画面中央放大，@小明站在原地目光追随，颧大肌微微上提使嘴角泛起若有若无的弧度，眼神从平静转为期待——节奏慢，给重逢的情绪充分发酵的时间"},{"time_range":"6.0s-11.0s","action":"情绪积累至爆发，面部特写固定凝视，@小明眼神从柔和逐渐转为湿润，泪膜在眼球表面缓慢积聚使瞳孔反光扩散为片状模糊，嘴唇微张想说话但随即抿紧——积蓄的克制在第11秒突破，@小红露出温暖灿烂的笑容，眼眶同时因眼周肌肉挤压挤出细密鱼尾纹，@小明跟着笑出声"},{"time_range":"11.0s-15.0s","action":"节奏渐缓收束，镜头缓慢拉远至远景固定，两人并肩而立的身影在夕阳逆光中形成剪影，画面中虚化的路人穿行而过——收束长达4s，故意留出沉默的余韵让观众消化重逢的情感重量"}}],"dialogue":"@小明: \u0022好久不见\u0022\u005cn(建议删除: \u0022好久不见\u0022)","sfx":"轻风拂过树叶沙沙声 + 远处车辆通行楼宇底噪","end_frame":"夕阳逆光下，两人并肩而立的全景剪影，气氛安静温暖","constraints":"视频中不得出现字幕，如有台词，对话旁白等，均使用默认字体，字体不透明度为0%。不生成字幕，禁用自动字幕，无台词字幕。电影级实拍摄影质感，禁止3D渲染/CGI/卡通风格，镜头运动平滑连续，不出现任何生图拼贴。无Logo，无文字，无字幕，无水印，无UI元素，无标志，无书本文字。连续电影级画幅连贯性，画幅比例锁定，无网格拼贴，无CGI/渲染/3D动画感，仅实拍电影质感。台词结束后停顿0.5秒，不要有背景音乐BGM。"}]}],"total_scenes":1,"total_shots":1,"summary":"概述"}

自检清单（逐一确认）：
1. 是否按规划为每个场景生成了正确数量的分镜？
2. 每个分镜的timeline是否都是对象格式（非数组）？每个对象是否包含time_range和action两个字段？
3. 每条动作链的action开头是否清晰表达了本段节奏定位（铺垫/积累/爆发/过渡/收束）？
4. 时间分配是否由剧情驱动而非机械比例？是否该快的地方快、该慢的地方慢？
5. 每条action是否以节奏定位开头、自然融入景别运镜、含@标记且至少35字？
6. 每个分镜是否有rhythm_notes字段？
7. 每个分镜的constraints是否完整？（11句以上）
8. 英文台词是否都有中文注释？
9. 每个分镜的camera字段是否使用纯中文术语、逗号分隔？是否无英文缩写、无+号/|号分隔？
10. 每个分镜的assets字段是否完全不含括号？是否仅输出@标签本身？
11. 是否使用了任何解剖学肌肉/骨骼名称（颧大肌、眼轮匝肌等）？如有，必须改为视觉化描述。
12. 是否出现了「切回」「切至」「切换到」等硬切描述？如有，必须改为连续运镜。
13. 每个分镜的camera字段与第一条动作链的景别/运镜是否一致？
14. @标记是否仅标记了当前时间区间内画面中正在可见的元素？画外元素是否未加@？
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
    micro_kb = _load_micro_kb()
    if micro_kb:
        system += "\n\n---\n\n## 人物微表情动作参考（在动作链action字段中参考使用）\n\n" + micro_kb
    if emotion_timeline:
        et_text = _format_emotion_timeline(emotion_timeline)
        if et_text:
            system += "\n\n---\n\n## 角色情绪时间线（分镜编写时必须参考，每条action的微表情必须匹配当前时间段的情绪状态）\n\n" + et_text
    return system, f"剧本：\n{script_text}\n\n分镜规划（必须按此数量生成）：\n{plan_json}\n\n只输出JSON。每个分镜constraints必须完整。"

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
