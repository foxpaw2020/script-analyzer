"""Extractors 公共基类 — 共享 JSON 解析逻辑"""
# (C) foxpaw

import json, os, re, sys


class BaseExtractor:
    """所有 extractor 的基类，提供 JSON 提取和解析的公共方法"""
    
    @staticmethod
    def _extract_json(raw_text):
        """用括号深度匹配提取最外层 JSON，防止 {} 内嵌干扰"""
        raw_text = raw_text.strip()
        raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
        raw_text = re.sub(r'\s*```$', '', raw_text)
        # 括号深度匹配：跟踪是否在字符串内，找第一个完整 JSON 对象
        start = raw_text.find('{')
        if start == -1:
            return raw_text
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(raw_text)):
            ch = raw_text[i]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return raw_text[start:i+1]
        return raw_text[start:]
    
    @staticmethod
    def _repair_json(text):
        """激进修复 AI JSON 常见错误"""
        text = re.sub(r'```[a-z]*\s*', '', text)
        text = BaseExtractor._extract_json(text)
        text = re.sub(r',\s*([\}\]])', r'\1', text)
        text = re.sub(r'(\d+)([\u4e00-\u9fff]+)(\s*[,\}\]])', r'\1\3', text)
        def fix_string_content(s):
            result = []
            in_string = False
            escape = False
            for ch in s:
                if escape:
                    result.append(ch)
                    escape = False
                    continue
                if ch == '\\':
                    result.append(ch)
                    escape = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    result.append(ch)
                    continue
                if in_string:
                    if ch in '\n\r':
                        result.append('\\n')
                    elif ord(ch) < 0x20:
                        result.append(' ')
                    else:
                        result.append(ch)
                else:
                    result.append(ch)
            return ''.join(result)
        text = fix_string_content(text)
        return text

    @staticmethod
    def _close_truncated_json(text):
        if '{' not in text:
            return text
        start = text.find('{')
        # Track bracket stack to know what to close
        stack = []
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{' or ch == '[':
                stack.append(ch)
            elif ch == '}' or ch == ']':
                if stack:
                    stack.pop()
        if not stack:
            return text
        # Close in reverse order
        suffix = ''
        for opener in reversed(stack):
            suffix += '}' if opener == '{' else ']'
        # Clean up trailing partial value
        stripped = text.rstrip()
        # Always strip trailing comma before closing (JSON forbids trailing commas)
        if stripped.endswith(','):
            stripped = stripped[:-1]
        # If mid-value, strip back to last comma
        if not any(stripped.endswith(c) for c in ['{', '[', '"', '}', ']']):
            last_comma = stripped.rfind(',')
            if last_comma > start:
                stripped = stripped[:last_comma]
        return stripped + suffix

    @staticmethod
    def _safe_json_parse_with_fallback(raw_text, default=None):

        text = BaseExtractor._extract_json(raw_text)
        for attempt_text in [text, raw_text.strip(), BaseExtractor._repair_json(text)]:
            if not attempt_text:
                continue
            try:
                parsed = json.loads(attempt_text)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
        for attempt_text in [text, raw_text.strip()]:
            if not attempt_text:
                continue
            try:
                decoder = json.JSONDecoder()
                parsed, end_pos = decoder.raw_decode(attempt_text)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                pass
        # Attempt to repair truncated JSON by closing unclosed brackets/braces
        for source_text in [text, raw_text.strip()]:
            if not source_text or '{' not in source_text:
                continue
            try:
                repaired = BaseExtractor._close_truncated_json(source_text)
                if repaired:
                    parsed = json.loads(repaired)
                    if isinstance(parsed, dict):
                        return parsed
            except (json.JSONDecodeError, ValueError):
                pass
        return default

    @staticmethod
    def _format_json_kb(data):
        """将 JSON 结构的知识库转换为可读字符串"""
        parts = []
        meta = data.get("meta", {})
        if meta:
            name = meta.get("name", "")
            ver = meta.get("version", "")
            platforms = meta.get("platforms", [])
            if name:
                parts.append(f"角色/任务: {name}")
            if ver:
                parts.append(f"知识库版本: {ver}")
            if platforms:
                parts.append(f"目标平台: {', '.join(platforms)}")
        
        rules = data.get("rules", {})
        if rules:
            parts.append("")
            parts.append("## 规则")
            if isinstance(rules, dict):
                for k, v in rules.items():
                    parts.append(f"- {k}: {v}")
        
        classification = data.get("classification", {})
        if classification:
            parts.append("")
            parts.append("## 分类")
            if isinstance(classification, dict):
                for k, v in classification.items():
                    parts.append(f"- {k}: {v}")
        
        ten_layers = data.get("ten_layers", {})
        if ten_layers:
            parts.append("")
            parts.append("## 十层描述体系")
            if isinstance(ten_layers, list):
                for t in ten_layers:
                    parts.append(f"- {t}")
        
        shot_density = data.get("shot_density", {})
        if shot_density:
            parts.append("")
            parts.append("## 分镜密度判断")
            for k, v in shot_density.items():
                if isinstance(v, dict):
                    parts.append(f"- {k}:")
                    for sk, sv in v.items():
                        parts.append(f"    {sk}: {sv}")
                else:
                    parts.append(f"- {k}: {v}")
        
        camera_terms = data.get("camera_terms", {})
        if camera_terms:
            parts.append("")
            parts.append("## 镜头术语")
            for category, terms in camera_terms.items():
                if isinstance(terms, dict):
                    parts.append(f"- {category}:")
                    for k, v in terms.items():
                        parts.append(f"    {k}: {v}")
        
        sig_moves = data.get("signature_moves", {})
        if sig_moves:
            parts.append("")
            parts.append("## 招牌运镜")
            if isinstance(sig_moves, dict):
                for k, v in sig_moves.items():
                    parts.append(f"- {k}: {v}")
        
        hss = data.get("hollywood_shot_sequences", {})
        if hss:
            parts.append("")
            parts.append("## 好莱坞大师运镜范例（按场景类型索引，编写动作链时优先参考对应分类）")
            for cat_key, sequences in hss.items():
                cat_names = {
                    "chase_action": "追逐与动作",
                    "confrontation_dialogue": "对峙与对话",
                    "suspense_thriller": "悬疑与惊悚",
                    "emotion_intimacy": "情感与亲密",
                    "epic_warfare": "史诗与战争",
                    "sci_fi_supernatural": "科幻与超现实",
                    "time_manipulation": "时间操控",
                    "subjective_pov": "主观视角"
                }
                cat_label = cat_names.get(cat_key, cat_key)
                parts.append(f"### {cat_label}")
                for seq in sequences:
                    name = seq.get("name", "")
                    desc = seq.get("description", "")
                    parts.append(f"- {name}: {desc}")
                    for seg in seq.get("segments", []):
                        tr = seg.get("time_range", "")
                        act = seg.get("action", "")
                        parts.append(f"  {tr}: {act}")
                    parts.append("")
        
        lighting = data.get("lighting_style", {})
        if lighting and "note" in lighting:
            parts.append("")
            parts.append("## 光影方案")
            for k, v in lighting.items():
                if isinstance(v, dict):
                    parts.append(f"- {k}:")
                    for sk, sv in v.items():
                        parts.append(f"    {sk}: {sv}")
                elif k == "note":
                    parts.append(f"  提示: {v}")
                else:
                    parts.append(f"- {k}: {v}")
        
        dims = data.get("extraction_dimensions", [])
        if dims:
            parts.append("")
            parts.append("## 提取维度")
            for d in dims:
                parts.append(f"- {d}")
        
        ps = data.get("platform_style", {})
        if ps:
            parts.append("")
            parts.append("## 平台风格")
            if isinstance(ps, dict):
                for k, v in ps.items():
                    parts.append(f"- {k}: {v}")
        
        quality = data.get("quality", {})
        if quality:
            parts.append("")
            parts.append("## 画质参数")
            if isinstance(quality, dict):
                for k, v in quality.items():
                    parts.append(f"- {k}: {v}")
        
        consistency = data.get("consistency", "")
        if consistency:
            parts.append("")
            parts.append(f"## 一致性")
            parts.append(consistency)
        
        sm = data.get("semantic_mapping", {})
        if sm:
            parts.append("")
            parts.append("## 语义映射")
            if isinstance(sm, dict):
                for k, v in sm.items():
                    if isinstance(v, dict):
                        parts.append(f"- {k}:")
                        for sk, sv in v.items():
                            parts.append(f"    {sk}: {sv}")
                    else:
                        parts.append(f"- {k}: {v}")
        
        templates = data.get("output_templates", {})
        if templates and "assembly_note" in templates:
            parts.append("")
            parts.append("## 输出注意事项")
            parts.append(templates["assembly_note"])
        
        wf = data.get("workflow", [])
        if wf:
            parts.append("")
            parts.append("## 工作流")
            for i, step in enumerate(wf, 1):
                parts.append(f"{i}. {step}")
        
        delivery = data.get("delivery", "")
        if delivery:
            parts.append("")
            parts.append("## 交付方式")
            parts.append(delivery)
        
        return "\n".join(parts)
    

    @staticmethod
    def _format_director_kb(data):
        """将导演风格知识库（男女频）转可读字符串"""
        parts = []
        name = data.get("knowledge_base_name", "")
        ver = data.get("version", "")
        desc = data.get("description", "")
        if name:
            parts.append(f"# {name} v{ver}")
        if desc:
            parts.append(f"说明: {desc}")

        ctm = data.get("core_thinking_model", {})
        if ctm:
            parts.append("")
            parts.append("## 核心思维模型")
            for k, v in ctm.items():
                parts.append(f"- {k}: {v}")

        sfp = data.get("scene_function_positioning") or data.get("scene_emotion_positioning", {})
        if sfp:
            label = "场景功能定位" if "scene_function_positioning" in data else "场景情绪定位"
            parts.append("")
            parts.append(f"## {label}")
            desc_text = sfp.get("description", "")
            if desc_text:
                parts.append(desc_text)
            dims = sfp.get("dimensions", [])
            for d in dims:
                dname = d.get("name", "")
                if dname:
                    parts.append(f"### {dname}")
                opts = d.get("options", [])
                for o in opts:
                    parts.append(f"- {o}")
                notes = d.get("notes", "")
                if notes:
                    parts.append(notes)

        sle = data.get("shot_language_expression", {})
        if sle:
            parts.append("")
            parts.append("## 镜头语言表达")
            for k, v in sle.items():
                if isinstance(v, dict):
                    parts.append(f"### {k}")
                    for sk, sv in v.items():
                        parts.append(f"- {sk}: {sv}")
                else:
                    parts.append(f"- {k}: {v}")

        tse = data.get("typical_scene_examples", {})
        if tse:
            parts.append("")
            parts.append("## 典型场景示例")
            for scene_name, scene_data in tse.items():
                parts.append(f"### {scene_name}")
                shots_seq = scene_data.get("shot_sequence", [])
                for s in shots_seq:
                    parts.append(f"- {s}")
                dn = scene_data.get("director_note", "")
                if dn:
                    parts.append(f"> {dn}")

        return "\n".join(parts)

    @staticmethod
    def _format_temp_characters(chars):
        """将 temp_knowledge 中的人物档案格式化为可注入 prompt 的字符串"""
        if not chars:
            return ""
        parts = ["", "---", "", "## 人物小传参考（优先使用以下人物信息，角色名和特征以人物小传为准）", ""]
        for c in chars:
            name = c.get("name", "")
            if not name:
                continue
            parts.append(f"### {name}")
            for field in ["age_race", "personality", "appearance", "arc", "key_traits"]:
                val = c.get(field)
                if val:
                    if isinstance(val, list):
                        parts.append(f"- {field}: {', '.join(val)}")
                    else:
                        parts.append(f"- {field}: {val}")
            rels = c.get("relationships", [])
            if rels:
                rel_strs = []
                for r in rels:
                    rel_strs.append(f"{r.get('target','')}: {r.get('relation','')}")
                parts.append(f"- 关系: {'; '.join(rel_strs)}")
        return "\n".join(parts)

    @staticmethod
    def _format_temp_world(world):
        """将 temp_knowledge 中的世界观档案格式化为可注入 prompt 的字符串"""
        if not world:
            return ""
        parts = ["", "---", "", "## 故事大纲参考（以下世界观信息优先使用）", ""]
        for k, v in world.items():
            if isinstance(v, list):
                parts.append(f"- {k}: {', '.join(str(x) for x in v)}")
            else:
                parts.append(f"- {k}: {v}")
        return "\n".join(parts)

    @staticmethod
    def _load_knowledge_base(filename, kb_dir=None):
        """加载知识库文件（.md 或 .json），返回字符串。失败返回空字符串。"""
        if kb_dir is None:
            if getattr(sys, 'frozen', False):
                kb_dir = os.path.join(sys._MEIPASS, 'knowledge_base')
            else:
                kb_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'knowledge_base')
        kb_path = os.path.join(kb_dir, filename)
        ext = os.path.splitext(filename)[1].lower()
        if ext == '.json':
            try:
                with open(kb_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return BaseExtractor._format_json_kb(data)
            except (FileNotFoundError, OSError, json.JSONDecodeError):
                return ""
        try:
            with open(kb_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except (FileNotFoundError, OSError):
            return ""
