"""
剧本拆解大师v2.49版 - Flask Web 应用
支持上传/粘贴剧本，通过 AI 进行角色、道具、场景、分镜四步提取
"""
# (C) foxpaw


import os
import sys
import json
import time
import uuid
import logging
import re
import subprocess
import threading
import requests
from flask import (
    Flask, request, jsonify, send_file,
    Response, stream_with_context
)
from werkzeug.utils import safe_join

import config
from utils import get_base_path
from extractors import characters, props, scenes, shots, emotion_timeline

# 导入拆分后的模块
from services.ai_service import call_ai
from services.file_parser import parse_script
from utils.text import detect_episode, split_script_by_episodes
from utils.sse import json_sse
from reports.word_report import generate_word_report
from reports.html_report import generate_html_report

app = Flask(__name__,
    static_folder=os.path.join(get_base_path(), 'static'),
    static_url_path='',
    template_folder=os.path.join(get_base_path(), 'templates'))
app.secret_key = config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER

# ===== 安全增强: CORS + 安全响应头 =====
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Cache-Control'] = 'no-store'
    # CORS: 仅允许同源
    response.headers['Access-Control-Allow-Origin'] = request.host_url.rstrip('/') if request.host else '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

# ===== 安全增强: 速率限制 =====
_rate_limit_store = {}

def _check_rate_limit(key, max_requests=30, window=60):
    """简单的内存速率限制: 每窗口最多 max_requests 次"""
    now = time.time()
    if key in _rate_limit_store:
        count, window_start = _rate_limit_store[key]
        if now - window_start > window:
            _rate_limit_store[key] = (1, now)
            return True
        if count >= max_requests:
            return False
        _rate_limit_store[key] = (count + 1, window_start)
        return True
    _rate_limit_store[key] = (1, now)
    return True

def _get_client_id():
    """获取客户端标识用于速率限制"""
    return request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown')

os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)


def _series_name(script_name):
    """从剧本名提取系列名：移除 _第X集 后缀，实现单系列共享知识库"""
    if not script_name:
        return script_name
    import re
    # 匹配 _第X集 或 _第XX集 或 第X集（无下划线时也考虑）
    cleaned = re.sub(r'_第[一二三四五六七八九十\d]+集$', '', script_name)
    # 如果没变化（没有 _第X集），也尝试去掉末尾的 第X集
    if cleaned == script_name:
        cleaned = re.sub(r'第[一二三四五六七八九十\d]+集$', '', script_name)
    cleaned = cleaned.strip(' _-')
    # 如果去掉后缀后为空（如用户直接命名"第1集"），回退到 script_name 自身
    if not cleaned:
        return script_name
    return cleaned


def _load_temp_knowledge(script_name):
    """加载剧本的临时知识库（自动从磁盘读取，优先系列级目录）"""
    import os, json
    from werkzeug.utils import safe_join
    
    series = _series_name(script_name)
    # 先尝试系列级目录
    d = safe_join(config.OUTPUT_DIR, series) if series else safe_join(config.OUTPUT_DIR, script_name) if script_name else config.OUTPUT_DIR
    if not d:
        return None
    os.makedirs(d, exist_ok=True)
    kb_path = os.path.join(d, f'{series}_人物小传大纲_知识库.json')
    if os.path.exists(kb_path):
        try:
            with open(kb_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None
    # 兼容旧路径：旧版 kb 在脚本级目录
    d2 = safe_join(config.OUTPUT_DIR, script_name) if script_name else None
    if d2:
        kb_path2 = os.path.join(d2, f'{script_name}_人物小传大纲_知识库.json')
        if os.path.exists(kb_path2):
            try:
                with open(kb_path2, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                return None
    return None
def _output_path(script_name, filename):
    """获取剧本专属输出路径，自动创建系列级子文件夹。内部使用 safe_join 防路径穿越。"""
    if not script_name:
        d = config.OUTPUT_DIR
    else:
        series = _series_name(script_name)
        d = safe_join(config.OUTPUT_DIR, series) if series else safe_join(config.OUTPUT_DIR, script_name)
    if not d:
        raise ValueError(f"非法剧本名称: {script_name}")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, filename)

# ============================================================
# 路由
# ============================================================

def _require_auth():
    """可选的 API 认证 — 通过环境变量 AUTH_TOKEN 启用"""
    token = os.environ.get('AUTH_TOKEN', '')
    if not token:
        return True  # 未配置则不启用认证
    auth_header = request.headers.get('Authorization', '')
    if auth_header == f'Bearer {token}':
        return True
    return False

@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/api/config')
def get_config():
    """获取支持的 AI 提供商配置"""
    providers = {}
    for key, info in config.AI_PROVIDERS.items():
        providers[key] = {
            "name": info["name"],
            "default_model": info["default_model"],
        }
    return jsonify({"providers": providers})


@app.route('/api/list_models', methods=['POST'])
def list_models():
    """调用 DeepSeek API 获取可用模型列表"""
    if not _check_rate_limit(_get_client_id(), max_requests=30, window=60):
        return jsonify({"error": "请求过于频繁，请稍后重试"}), 429
    data = request.get_json(silent=True) or {}
    api_key = data.get('api_key', '')
    base_url = data.get('base_url', config.DEEPSEEK_API_URL)
    # SSRF 防护: 验证 base_url 在白名单内
    if config.ALLOWED_BASE_URLS:
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        if parsed.netloc not in config.ALLOWED_BASE_URLS:
            return jsonify({
                "error": "不允许的 API 地址",
                "models": config.DEEPSEEK_KNOWN_MODELS,
                "source": "fallback"
            }), 200
    
    if not api_key:
        # 无 API Key 时返回后备模型列表
        return jsonify({
            "models": config.DEEPSEEK_KNOWN_MODELS,
            "source": "fallback"
        })
    
    try:
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        resp = requests.get(
            f"{base_url.rstrip('/')}/models",
            headers=headers,
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        
        models = data.get('data', [])
        # 过滤和格式化
        formatted = []
        for m in models:
            model_id = m.get('id', '')
            # 排除 embedding 等非对话模型
            if 'embed' in model_id.lower() or 'image' in model_id.lower():
                continue
            formatted.append({
                "id": model_id,
                "name": m.get('id', model_id),
                "owned_by": m.get('owned_by', 'deepseek'),
                "ctx": "1M" if 'v4' in model_id else ("64K" if 'chat' in model_id or 'reasoner' in model_id else "?"),
            })
        
        return jsonify({"models": formatted, "source": "api"})
        
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        if status == 401:
            return jsonify({
                "error": "API Key 无效，请检查",
                "models": config.DEEPSEEK_KNOWN_MODELS,
                "source": "fallback"
            }), 200
        return jsonify({
            "error": f"API 错误 ({status})",
            "models": config.DEEPSEEK_KNOWN_MODELS,
            "source": "fallback"
        }), 200
    except requests.exceptions.ConnectionError:
        return jsonify({
            "error": f"无法连接到 {base_url}",
            "models": config.DEEPSEEK_KNOWN_MODELS,
            "source": "fallback"
        }), 200
    except Exception as e:
        return jsonify({
            "error": str(e),
            "models": config.DEEPSEEK_KNOWN_MODELS,
            "source": "fallback"
        }), 200


@app.route('/api/check_connection', methods=['POST'])
def check_connection():
    """测试 AI API 连通性（代理请求，避免浏览器 CORS 问题）"""
    data = request.get_json(silent=True) or {}
    provider = data.get('provider', 'deepseek')
    api_key = data.get('api_key', '')
    base_url = data.get('base_url', '')
    
    if provider == 'ollama':
        url = (base_url or config.OLLAMA_BASE_URL).rstrip('/') + '/api/tags'
        try:
            resp = requests.get(url, timeout=5)
            if resp.ok:
                return jsonify({"success": True, "message": "Ollama 连接成功"})
            return jsonify({"success": False, "message": f"Ollama 返回 {resp.status_code}"})
        except requests.exceptions.ConnectionError:
            return jsonify({"success": False, "message": f"无法连接到 Ollama ({url})"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})
    else:
        url = (base_url or config.DEEPSEEK_API_URL).rstrip('/') + '/models'
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.ok:
                data = resp.json()
                count = len(data.get('data', []))
                return jsonify({"success": True, "message": f"连接成功! 找到 {count} 个模型", "model_count": count})
            elif resp.status_code == 401:
                return jsonify({"success": False, "message": "API Key 无效"})
            return jsonify({"success": False, "message": f"API 返回 {resp.status_code}"})
        except requests.exceptions.ConnectionError:
            return jsonify({"success": False, "message": f"无法连接到 {url}"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})


@app.route('/api/analyze', methods=['POST'])
def analyze():
    """主分析接口：接收剧本并运行四步提取（SSE 流式进度）"""
    if not _require_auth():
        return jsonify({"error": "未授权访问"}), 401
    if not _check_rate_limit(_get_client_id(), max_requests=20, window=60):
        return jsonify({"error": "请求过于频繁，请稍后重试"}), 429
    
    def generate():
        results = {}
        error = None
        
        try:
            # 1. 获取剧本内容
            script_text = ""
            script_name = "未命名剧本"
            
            if 'file' in request.files:
                file = request.files['file']
                if file.filename == '':
                    yield json_sse("error", {"message": "请选择要上传的文件"})
                    return
                
                # MIME 类型校验
                ext = os.path.splitext(file.filename)[1].lower()
                ALLOWED_EXTS = {'.pdf': 'application/pdf', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.doc': 'application/msword', '.txt': 'text/plain', '.md': 'text/markdown', '.markdown': 'text/markdown'}
                if ext not in ALLOWED_EXTS:
                    yield json_sse("error", {"message": f"不支持的文件格式: {ext}，请上传 PDF、Word、TXT 或 MD 文件"})
                    return
                
                # 保存上传文件
                safe_name = f"{uuid.uuid4().hex}{ext}"
                file_path = os.path.join(config.UPLOAD_FOLDER, safe_name)
                file.save(file_path)
                
                try:
                    script_text = parse_script(file_path)
                except Exception as e:
                    logging.getLogger("app").error("文件解析失败: %s", str(e))
                    yield json_sse("error", {"message": "文件解析失败，请确认文件格式正确且未损坏"})
                    return
                finally:
                    # 清理临时文件
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass
                
                script_name = os.path.splitext(file.filename)[0]
            else:
                data = request.get_json(silent=True)
                if data and 'text' in data:
                    script_text = data['text']
                elif request.form.get('text'):
                    script_text = request.form['text']
                if data and 'script_name' in data:
                    script_name = data['script_name']
                elif request.form.get('script_name'):
                    script_name = request.form['script_name']
            
            # 净化文件名（防止路径穿越）
            script_name = re.sub(r'[\\/:*?"<>|]', '_', script_name)
            script_name = script_name.replace('\x00', '')
            script_name = script_name.lstrip('.-')
            script_name = script_name.strip()[:100] or "未命名剧本"
            
            if not script_text or not script_text.strip():
                yield json_sse("error", {"message": "剧本内容为空，请提供有效的剧本"})
                return
            
            # 截断太长文本（50000字足够覆盖大部分剧本单幕或短剧全本）
            if len(script_text) > 50000:
                yield json_sse("info", {"message": f"剧本较长({len(script_text)}字符)，将完整处理而非截断"})
            # 不再截断剧本内容，完整传递给AI
            
            # 获取 AI 配置（从 FormData 中提取）
            api_config = {}
            for key in ['provider', 'api_key', 'model', 'base_url', 'temperature', 'top_p', 'frequency_penalty', 'presence_penalty', 'max_tokens', 'thinking']:
                val = request.form.get(f'api_config[{key}]')
                if val is not None:
                    api_config[key] = val
            
            # 获取分析步骤参数（空=全部，指定则只跑该步）
            step_filter = request.form.get('step', '').strip()
            
            # 读取剧本拆解风格
            breakdown_style = request.form.get('breakdown_style', 'normal').strip()
            if breakdown_style not in ('female', 'male', 'normal'):
                breakdown_style = 'normal'
            
            # 加载或自动生成临时知识库
            temp_kb = _load_temp_knowledge(script_name)
            
            # 自动预处理：知识库不存在但有材料时，自动生成
            char_bio_in = request.form.get('char_bio', '').strip()
            outline_in = request.form.get('story_outline', '').strip()
            needs_materials = (char_bio_in or outline_in) and not temp_kb
            if needs_materials:
                pre_sys = """你是剧本分析预处理专家。你的任务是分析人物小传和故事大纲，提取结构化信息。

人物小传分析要求：
- 提取每个角色的名称(name)、别名(aliases)、年龄种族(age_race)、性格标签(personality)、弧光走向(arc)、外貌特征(appearance)、人际关系(relationships)、关键特征(key_traits)

故事大纲分析要求：
- 提取年代/时空设定(time_period)、主要地点(location)、类型标签(genre)、整体基调(tone)、关键剧情道具(key_props)、关键情节点(key_plot_points)、环境风格描述(environment_style)

输出纯JSON："""
                pre_user = "请分析以下内容并生成结构化知识库。\n\n"
                if char_bio_in:
                    pre_user += f"=== 人物小传 ===\n{char_bio_in}\n\n"
                if outline_in:
                    pre_user += f"=== 故事大纲 ===\n{outline_in}\n\n"
                pre_user += (
                    '输出JSON格式：\n'
                    '{\n'
                    '  "characters": [{\n'
                    '    "name": "角色名",\n'
                    '    "aliases": ["别名"],\n'
                    '    "age_race": "年龄/种族",\n'
                    '    "personality": ["性格标签"],\n'
                    '    "arc": "角色弧光走向",\n'
                    '    "appearance": "外貌特征",\n'
                    '    "relationships": [{"target": "关联角色", "relation": "关系描述"}],\n'
                    '    "key_traits": "关键特征"\n'
                    '  }],\n'
                    '  "world": {\n'
                    '    "time_period": "年代/时空设定",\n'
                    '    "location": "主要地点",\n'
                    '    "genre": "类型标签",\n'
                    '    "tone": "整体基调",\n'
                    '    "key_props": ["关键剧情道具"],\n'
                    '    "key_plot_points": ["关键情节点"],\n'
                    '    "environment_style": "环境风格描述"\n'
                    '  }\n'
                    '}\n'
                    '只输出JSON。'
                )
                try:
                    api_cfg = {}
                    for key in ['provider', 'api_key', 'model', 'base_url', 'temperature', 'top_p', 'frequency_penalty', 'presence_penalty', 'max_tokens', 'thinking']:
                        val = request.form.get(f'api_config[{key}]', '')
                        if val:
                            api_cfg[key] = val
                    raw = call_ai(pre_sys, pre_user, api_cfg)
                    json_text = raw.strip()
                    js = json_text.find('{')
                    je = json_text.rfind('}')
                    if js != -1 and je != -1:
                        json_text = json_text[js:je+1]
                    parsed = json.loads(json_text)
                    series = _series_name(script_name)
                    d = safe_join(config.OUTPUT_DIR, series) if series else safe_join(config.OUTPUT_DIR, script_name)
                    if d:
                        os.makedirs(d, exist_ok=True)
                        kb_path = os.path.join(d, f'{series}_人物小传大纲_知识库.json')
                        with open(kb_path, 'w', encoding='utf-8') as f:
                            json.dump(parsed, f, ensure_ascii=False, indent=2)
                        temp_kb = parsed
                        yield json_sse("info", {"message": f"已自动分析人物小传和故事大纲（{len(parsed.get('characters', []))}个角色）"})
                except Exception as e:
                    logging.getLogger("app").warning("自动预处理失败: %s", str(e))
                    yield json_sse("info", {"message": "人物小传分析失败，将以普通模式继续"})
            
            # 检查是否需要提示用户（无材料且无kb）
            has_any_material = bool(char_bio_in or outline_in)
            no_material_flag = request.form.get('no_materials_skip', '0')
            
            # 加载已有结果（分步模式用）
            prior_json = request.form.get('prior_results', '')
            if prior_json:
                try:
                    prior = json.loads(prior_json)
                    for k in ['characters', 'props', 'scenes', 'shots']:
                        if k in prior:
                            results[k] = prior[k]
                except Exception:
                    logging.warning("prior_results 解析失败，跳过", exc_info=True)
            
            # 预分块：长剧本切成小块用于第一轮扫描
            CHUNK_SIZE = 4000
            script_chunks = []
            if len(script_text) > CHUNK_SIZE:
                paragraphs = script_text.split('\n\n')
                current = ""
                for p in paragraphs:
                    if len(current) + len(p) > CHUNK_SIZE and current:
                        script_chunks.append(current.strip())
                        current = p
                    else:
                        current += ("\n\n" if current else "") + p
                if current.strip():
                    script_chunks.append(current.strip())
            else:
                script_chunks = [script_text]
            
            # 2. 分析接口调用（可选的）
            yield json_sse("info", {
                "message": f"开始分析《{script_name}》，剧本长度：{len(script_text)} 字符",
                "script_length": len(script_text)
            })
            
            # ===== 步骤1: 角色提取 =====
            if not step_filter or step_filter == 'characters':
                yield json_sse("progress", {"step": "characters", "status": "processing", "label": "角色提取", "message": f"第一轮：分{len(script_chunks)}块扫描角色名..."})
                try:
                    all_names = set()
                    for i, chunk in enumerate(script_chunks):
                        if len(script_chunks) > 1:
                            yield json_sse("progress", {"step": "characters", "status": "processing", "label": "角色提取", "message": f"扫描第{i+1}/{len(script_chunks)}段..."})
                        sys_p, user_p = characters.build_list_prompt(chunk)
                        raw = call_ai(sys_p, user_p, api_config)
                        names = characters.parse_list(raw)
                        all_names.update(names)
                    
                    char_names = sorted(all_names)
                    if not char_names:
                        raise RuntimeError("未找到任何角色名")
                    
                    yield json_sse("progress", {"step": "characters", "status": "processing", "label": "角色提取", "message": f"发现 {len(char_names)} 个角色，第二轮：生成详情和提示词..."})
                    sys_p, user_p = characters.build_detail_prompt(script_text, char_names, temp_kb=temp_kb)
                    raw = call_ai(sys_p, user_p, api_config)
                    result = characters.parse_result(raw)
                    results['characters'] = result
                    cc = len(result.get('characters', []))
                    if cc == 0:
                        raw_preview = str(raw)[:400] if raw else '(AI未返回内容)'
                        logging.getLogger("app").warning("角色第二轮返回0个角色，AI原始返回前500字: %s", str(raw)[:500])
                        raise RuntimeError(f"角色详情生成失败：第二轮返回0个角色。AI原始返回前400字: {raw_preview}")
                    # 按角色重要性排序：主角 > 配角 > 龙套 > 未知
                    char_order = {'主角': 0, '配角': 1, '龙套': 2}
                    result['characters'] = sorted(result.get('characters', []),
                        key=lambda c: char_order.get(c.get('role_type', ''), 99))
                    # 生成分步 HTML 报告
                    partial_html = generate_html_report(results, script_name, episode_info=None)
                    partial_path = _output_path(script_name, '角色提取.html')
                    with open(partial_path, 'w', encoding='utf-8') as f:
                        f.write(partial_html)
                    yield json_sse("progress", {"step": "characters", "status": "complete", "label": "角色提取", "message": f"完成！识别 {cc} 个角色", "data": result, "download_url": f"/api/download/{os.path.basename(partial_path)}"})
                except Exception as e:
                    yield json_sse("progress", {"step": "characters", "status": "error", "label": "角色提取", "message": f"失败：{str(e)}"})
                    yield json_sse("error", {"message": f"角色提取失败: {str(e)}"})
                    return
            
            # ===== 步骤2: 道具提取 =====
            if not step_filter or step_filter == 'props':
                # 检测集数：单集无频率限制，多集要求≥2场
                eps = split_script_by_episodes(script_text)
                ep_count = len(eps) if eps else 0
                min_freq = 1 if ep_count <= 1 else 2
                freq_hint = "单集模式：提取全部道具" if min_freq <= 1 else f"多集模式（{ep_count}集）：仅提取≥2场道具"
                yield json_sse("progress", {"step": "props", "status": "processing", "label": "道具提取", "message": f"第一轮：扫描全剧本道具名（{freq_hint}）..."})
                try:
                    sys_p, user_p = props.build_list_prompt(script_text, min_appearances=min_freq)
                    raw = call_ai(sys_p, user_p, api_config)
                    prop_names = props.parse_list(raw)
                    if not isinstance(prop_names, list):
                        prop_names = []
                    
                    if len(prop_names) == 0:
                        raw_preview = str(raw)[:300] if raw else '(AI未返回内容)'
                        logging.getLogger("app").warning("道具第一轮返回0个道具，AI原始返回前500字: %s", str(raw)[:500])
                        raise RuntimeError(f"道具第一轮未识别到任何道具。AI原始返回: {raw_preview}")
                    else:
                        yield json_sse("progress", {"step": "props", "status": "processing", "label": "道具提取", "message": f"发现 {len(prop_names)} 个道具，第二轮：生成详情和提示词..."})
                        sys_p, user_p = props.build_detail_prompt(script_text, prop_names, results, temp_kb=temp_kb)
                        raw = call_ai(sys_p, user_p, api_config)
                        result = props.parse_result(raw)
                        results['props'] = result
                        pc = len(result.get('props', []))
                        if pc == 0:
                            yield json_sse("progress", {"step": "props", "status": "complete", "label": "道具提取", "message": f"⚠️ 第二轮解析失败。AI原始返回前200字: {raw[:200]}"})
                        else:
                            # 生成分步 HTML 报告
                            partial_html = generate_html_report(results, script_name, episode_info=None)
                            partial_path = _output_path(script_name, '道具提取.html')
                            with open(partial_path, 'w', encoding='utf-8') as f:
                                f.write(partial_html)
                            yield json_sse("progress", {"step": "props", "status": "complete", "label": "道具提取", "message": f"完成！识别 {pc} 个道具", "data": result, "download_url": f"/api/download/{os.path.basename(partial_path)}"})
                except Exception as e:
                    yield json_sse("progress", {"step": "props", "status": "error", "label": "道具提取", "message": f"失败：{str(e)}"})
                    yield json_sse("error", {"message": f"道具提取失败: {str(e)}"})
                    return
            
            # ===== 步骤3: 场景拆解 =====
            if not step_filter or step_filter == 'scenes':
                yield json_sse("progress", {"step": "scenes", "status": "processing", "label": "场景拆解", "message": "第一轮：识别所有场景场次..."})
                try:
                    sys_p, user_p = scenes.build_list_prompt(script_text)
                    raw = call_ai(sys_p, user_p, api_config)
                    scene_list = scenes.parse_list(raw)
                    if not scene_list and raw:
                        logging.getLogger("app").warning("场景第一轮返回无法解析，AI原始返回前500字: %s", str(raw)[:500])
                    if not scene_list:
                        raw_preview = str(raw)[:300] if raw else '(AI未返回内容)'
                        raise RuntimeError(f"第一轮未识别到任何场景。AI原始返回: {raw_preview}")
                    
                    yield json_sse("progress", {"step": "scenes", "status": "processing", "label": "场景拆解", "message": f"发现 {len(scene_list)} 个场景，第二轮：生成十层描述和双版提示词..."})
                    sys_p, user_p = scenes.build_detail_prompt(script_text, scene_list, results, temp_kb=temp_kb)
                    raw = call_ai(sys_p, user_p, api_config)
                    result = scenes.parse_result(raw)
                    results['scenes'] = result
                    sc = len(result.get('scenes', []))
                    if sc == 0:
                        raw_preview = str(raw)[:400] if raw else '(AI未返回内容)'
                        logging.getLogger("app").warning("场景第二轮返回0个场景，AI原始返回前500字: %s", str(raw)[:500])
                        raise RuntimeError(f"第二轮生成0个场景详情。AI原始返回前400字: {raw_preview}")
                    # 生成分步 HTML 报告
                    partial_html = generate_html_report(results, script_name, episode_info=None)
                    partial_path = _output_path(script_name, '场景拆解.html')
                    with open(partial_path, 'w', encoding='utf-8') as f:
                        f.write(partial_html)
                    yield json_sse("progress", {"step": "scenes", "status": "complete", "label": "场景拆解", "message": f"完成！拆解 {sc} 个场景", "data": result, "download_url": f"/api/download/{os.path.basename(partial_path)}"})
                except Exception as e:
                    yield json_sse("progress", {"step": "scenes", "status": "error", "label": "场景拆解", "message": f"失败：{str(e)}"})
                    yield json_sse("error", {"message": f"场景拆解失败: {str(e)}"})
                    return
            
            # ===== 步骤4: 分镜拆解 =====
            if not step_filter or step_filter == 'shots':
                # 尝试按集拆分剧本
                episodes = split_script_by_episodes(script_text)
                # 如果集拆分失败但剧本很长（>2万字），强制按字数切块
                if (not episodes or len(episodes) <= 2) and len(script_text) > 20000:
                    CHUNK_SIZE = 15000
                    episodes = []
                    pos = 0
                    ep_num = 0
                    while pos < len(script_text):
                        end = min(pos + CHUNK_SIZE, len(script_text))
                        # 尽量在段落边界切断
                        if end < len(script_text):
                            nl = script_text.rfind('\n\n', pos, end)
                            if nl > pos + CHUNK_SIZE // 2:
                                end = nl
                        ep_num += 1
                        episodes.append((ep_num, script_text[pos:end].strip()))
                        pos = end
                    yield json_sse("progress", {"step": "shots", "status": "processing", "label": "分镜拆解", "message": f"⚠️ 未检测到集标记，已按字数强制分为 {ep_num} 段批次处理"})

                use_batches = episodes and len(episodes) > 2

                if use_batches:
                    batch_size = 2
                    total_episodes = len(episodes)
                    total_batches = (total_episodes + batch_size - 1) // batch_size
                    ep_nums = [str(e[0]) for e in episodes if e[0] > 0]
                    yield json_sse("progress", {"step": "shots", "status": "processing", "label": "分镜拆解", "message": f"全剧 {total_episodes} 集（检测到：{', '.join(ep_nums[:10])}{'...' if len(ep_nums)>10 else ''}），按 {batch_size} 集一批处理，共 {total_batches} 批..."})

                    all_shot_scenes = []
                    total_shots_all = 0
                    incomplete_batches = []
                    empty_batches = []
                    completed_batches = 0
                    prev_tail = ""

                    for batch_idx in range(0, total_episodes, batch_size):
                        batch_eps = episodes[batch_idx:batch_idx + batch_size]
                        batch_num = batch_idx // batch_size + 1
                        ep_range = f"第{batch_eps[0][0]}-{batch_eps[-1][0]}集"
                        batch_text = "\n\n".join(t for _, t in batch_eps)
                        batch_result = None

                        # 尝试（最多2次：正常 + 1次重试）
                        for attempt in range(2):
                            retry_tag = "（重试）" if attempt == 1 else ""
                            yield json_sse("progress", {"step": "shots", "status": "processing", "label": "分镜拆解", "message": f"批次 {batch_num}/{total_batches}：{ep_range} 第一轮规划{retry_tag}..."})
                            try:
                                # 自动启用推理能力（仅模型支持时开启）
                                shots_api_config = dict(api_config)
                                model_name = shots_api_config.get('model', '')
                                if 'v4-flash' in model_name:
                                    shots_api_config['thinking'] = '1'
                                sys_p, user_p = shots.build_list_prompt(batch_text, results, style=breakdown_style)
                                raw = call_ai(sys_p, user_p, shots_api_config)
                                shot_plan = shots.parse_list(raw)

                                yield json_sse("progress", {"step": "shots", "status": "processing", "label": "分镜拆解", "message": f"批次 {batch_num}/{total_batches}：{ep_range} 第二轮详情{retry_tag}..."})
                                # 情绪时间线预分析
                                et_data = None
                                try:
                                    char_names = [c.get('name','') for c in results.get('characters',{}).get('characters',[])]
                                    scene_list = results.get('scenes',{}).get('scenes',[])
                                    if char_names and scene_list:
                                        yield json_sse("progress", {"step": "shots", "status": "processing", "label": "情绪预分析", "message": "分析角色情绪时间线..."})
                                        et_sys, et_user = emotion_timeline.build_prompt(batch_text, char_names, scene_list)
                                        et_raw = call_ai(et_sys, et_user, api_config)
                                        et_data = emotion_timeline.parse_result(et_raw)
                                except Exception:
                                    pass
                                sys_p, user_p = shots.build_detail_prompt(batch_text, shot_plan, results, style=breakdown_style, emotion_timeline=et_data)
                                if prev_tail:
                                    user_p += f"\n\n【上下文衔接】上一批剧情结束于：{prev_tail}。请确保本批首批分镜从该状态自然接续。"
                                raw = call_ai(sys_p, user_p, api_config)
                                batch_result = shots.parse_result(raw)
                                batch_scenes = batch_result.get('scenes', [])
                                batch_shots = batch_result.get('total_shots', 0)
                                if batch_shots == 0:
                                    if attempt == 0:
                                        yield json_sse("progress", {"step": "shots", "status": "processing", "label": "分镜拆解", "message": f"批次 {batch_num}/{total_batches}：{ep_range} 空结果，重试中...（{raw[:100]}）"})
                                        time.sleep(1)
                                        continue  # 重试
                                    else:
                                        empty_batches.append(ep_range)
                                        yield json_sse("progress", {"step": "shots", "status": "processing", "label": "分镜拆解", "message": f"批次 {batch_num}/{total_batches}：{ep_range} 重试仍为空 ⚠️（{raw[:100]}）"})
                                else:
                                    all_shot_scenes.extend(batch_scenes)
                                    total_shots_all += batch_shots
                                    completed_batches += 1
                                    if batch_scenes:
                                        last_scene = batch_scenes[-1]
                                        last_shots = last_scene.get('shots', [])
                                        if last_shots:
                                            prev_tail = last_shots[-1].get('end_frame', '') or last_shots[-1].get('subject', '')
                                    yield json_sse("progress", {"step": "shots", "status": "processing", "label": "分镜拆解", "message": f"批次 {batch_num}/{total_batches}：{ep_range} 完成 ✓ ({batch_shots} 个分镜)"})
                                    # 增量保存：每批完成就落盘
                                    results['shots'] = {
                                        "scenes": all_shot_scenes,
                                        "total_scenes": len(all_shot_scenes),
                                        "total_shots": total_shots_all,
                                        "summary": f"处理中... {completed_batches}/{total_batches} 批",
                                        "directing_notes": ""
                                    }
                                    try:
                                        partial_html = generate_html_report(results, script_name, episode_info=None)
                                        partial_path = _output_path(script_name, '分镜拆解.html')
                                        with open(partial_path, 'w', encoding='utf-8') as f:
                                            f.write(partial_html)
                                    except Exception:
                                        logging.warning("分镜增量保存失败", exc_info=True)
                                    # 每集独立 HTML：按 shot_id 前缀分组（兼容多种格式）
                                    try:
                                        for ep_pair in batch_eps:
                                            ep_num = ep_pair[0]
                                            if ep_num <= 0:
                                                continue
                                            ep_scenes = []
                                            ep_shot_count = 0
                                            for s in batch_scenes:
                                                ep_shots = [sh for sh in s.get('shots', [])
                                                    if (f'第{ep_num}集' in sh.get('shot_id', '')
                                                        or f'EPISODE {ep_num}' in sh.get('shot_id', '').upper())]
                                                if ep_shots:
                                                    ep_scenes.append({"scene_title": s.get("scene_title", ""), "scene_number": s.get("scene_number", 1), "shots": ep_shots})
                                                    ep_shot_count += len(ep_shots)
                                            if ep_scenes:
                                                ep_result = {"scenes": ep_scenes, "total_scenes": len(ep_scenes), "total_shots": ep_shot_count, "summary": f"第{ep_num}集 · {ep_shot_count} 个分镜", "directing_notes": ""}
                                                ep_html = generate_html_report({"shots": ep_result}, script_name, episode_info=None)
                                                ep_path = _output_path(script_name, f'第{ep_num}集_{time.strftime("%Y%m%d_%H%M%S")}.html')
                                                with open(ep_path, 'w', encoding='utf-8') as f:
                                                    f.write(ep_html)
                                    except Exception:
                                        logging.warning("单集HTML生成失败", exc_info=True)
                                break  # 有结果了就退出重试循环
                            except Exception as e:
                                if attempt == 0:
                                    yield json_sse("progress", {"step": "shots", "status": "processing", "label": "分镜拆解", "message": f"批次 {batch_num}/{total_batches}：{ep_range} 异常，重试中...（{type(e).__name__}）"})
                                    time.sleep(1)
                                    continue
                                incomplete_batches.append(ep_range)
                                yield json_sse("progress", {"step": "shots", "status": "processing", "label": "分镜拆解", "message": f"批次 {batch_num}/{total_batches}：{ep_range} 失败 ⚠️ {type(e).__name__}"})
                                if isinstance(e, GeneratorExit):
                                    break
                            break  # 重试也失败了

                    result = {
                        "scenes": all_shot_scenes,
                        "total_scenes": len(all_shot_scenes),
                        "total_shots": total_shots_all,
                        "summary": f"按集分批处理完成（{completed_batches}/{total_batches} 批成功），共 {total_shots_all} 个分镜",
                        "directing_notes": ""
                    }
                    if incomplete_batches:
                        result["incomplete_batches"] = incomplete_batches
                        result["summary"] += f"（⚠️ {len(incomplete_batches)} 批失败：{', '.join(incomplete_batches)}）"
                    if empty_batches:
                        result["empty_batches"] = empty_batches
                        result["summary"] += f"（⚠️ {len(empty_batches)} 批为空：{', '.join(empty_batches)}）"
                    results['shots'] = result
                    # 生成分步 HTML 报告
                    partial_html = generate_html_report(results, script_name, episode_info=None)
                    partial_path = _output_path(script_name, '分镜拆解.html')
                    with open(partial_path, 'w', encoding='utf-8') as f:
                        f.write(partial_html)
                    yield json_sse("progress", {"step": "shots", "status": "complete", "label": "分镜拆解", "message": f"完成！{completed_batches}/{total_batches} 批，全剧 {total_episodes} 集，生成 {total_shots_all} 个分镜" + (f"（{len(incomplete_batches)} 批失败）" if incomplete_batches else ""), "data": result, "download_url": f"/api/download/{os.path.basename(partial_path)}"})

                else:
                    # 集标记未检测到或只有少量集
                    scene_data = results.get('scenes', {})
                    scene_list = scene_data.get('scenes', []) if isinstance(scene_data, dict) else []
                    sc_count = len(scene_list)
                    ep_info = f"检测到{len(episodes)}集" if episodes else "未检测到集标记"
                    yield json_sse("progress", {"step": "shots", "status": "processing", "label": "分镜拆解", "message": f"⚠️ {ep_info}，单次处理（共 {sc_count} 个场景）。如需按集拆分，请确保剧本中用 \"第X集\" 或 \"EPISODE X\" 标注每集开始。"})
                    try:
                        shots_api_config = dict(api_config)
                        model_name = shots_api_config.get('model', '')
                        if 'v4-flash' in model_name:
                            shots_api_config['thinking'] = '1'
                        sys_p, user_p = shots.build_list_prompt(script_text, results, style=breakdown_style)
                        raw = call_ai(sys_p, user_p, shots_api_config)
                        shot_plan = shots.parse_list(raw)
                        plan_scenes = shot_plan.get('total_scenes', len(shot_plan.get('scenes', [])))
                        yield json_sse("progress", {"step": "shots", "status": "processing", "label": "分镜拆解", "message": f"第二轮：生成六模块分镜详情（规划 {plan_scenes} 场）..."})
                        # 情绪时间线预分析
                        et_data = None
                        try:
                            char_names = [c.get('name','') for c in results.get('characters',{}).get('characters',[])]
                            scene_list = results.get('scenes',{}).get('scenes',[])
                            if char_names and scene_list:
                                yield json_sse("progress", {"step": "shots", "status": "processing", "label": "情绪预分析", "message": "分析角色情绪时间线..."})
                                et_sys, et_user = emotion_timeline.build_prompt(script_text, char_names, scene_list)
                                et_raw = call_ai(et_sys, et_user, api_config)
                                et_data = emotion_timeline.parse_result(et_raw)
                        except Exception:
                            pass
                        sys_p, user_p = shots.build_detail_prompt(script_text, shot_plan, results, style=breakdown_style, emotion_timeline=et_data)
                        raw = call_ai(sys_p, user_p, shots_api_config)
                        result = shots.parse_result(raw)
                        results['shots'] = result
                        st = result.get('total_shots', 0)
                        if st == 0:
                            yield json_sse("progress", {"step": "shots", "status": "complete", "label": "分镜拆解", "message": f"⚠️ 分镜数为 0。AI原始返回前200字: {raw[:200]}", "data": result})
                        else:
                            partial_html = generate_html_report(results, script_name, episode_info=None)
                            partial_path = _output_path(script_name, '分镜拆解.html')
                            with open(partial_path, 'w', encoding='utf-8') as f:
                                f.write(partial_html)
                            yield json_sse("progress", {"step": "shots", "status": "complete", "label": "分镜拆解", "message": f"完成！生成 {st} 个分镜", "data": result, "download_url": f"/api/download/{os.path.basename(partial_path)}"})
                    except Exception as e:
                        yield json_sse("progress", {"step": "shots", "status": "error", "label": "分镜拆解", "message": f"失败：{str(e)}"})
                        yield json_sse("error", {"message": f"分镜拆解失败: {str(e)}"})
                        return
            
            # ===== 生成报告（仅自动模式）=====
            if not step_filter:
                yield json_sse("progress", {"step": "report", "status": "processing", "label": "生成报告", "message": "正在生成拆解报告..."})
                
                try:
                    episode_info = detect_episode(script_text)
                    # HTML 报告
                    html_content = generate_html_report(results, script_name, episode_info)
                    ep_label = f"EP{episode_info['current']}" if episode_info else "EP"
                    html_path = _output_path(script_name, f'{ep_label}_拆解报告.html')
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    
                    # Word 报告
                    word_path = generate_word_report(results, script_name, episode_info)
                    
                    if not os.path.exists(html_path):
                        raise RuntimeError("HTML 报告生成失败")
                    if not os.path.exists(word_path):
                        raise RuntimeError("Word 报告生成失败")
                    
                    yield json_sse("progress", {
                        "step": "report",
                        "status": "complete",
                        "label": "📄 生成报告",
                        "message": f"报告已生成！",
                        "data": {
                            "html_file": os.path.basename(html_path),
                            "word_file": os.path.basename(word_path),
                            "script_name": script_name
                        }
                    })
                    
                    # 完成
                    yield json_sse("complete", {
                        "message": "剧本分析全部完成！",
                        "html_file": os.path.basename(html_path),
                        "word_file": os.path.basename(word_path),
                        "output_dir": config.OUTPUT_DIR,
                        "script_name": script_name,
                        "results": results
                    })
                    
                except Exception as e:
                    yield json_sse("progress", {
                        "step": "report",
                        "status": "error",
                        "label": "📄 生成报告",
                        "message": f"失败：{str(e)}"
                    })
                    yield json_sse("error", {"message": f"报告生成失败: {str(e)}"})
                    return
                
            # 分步模式：生成报告并发送完成事件
            if step_filter:
                try:
                    episode_info = detect_episode(script_text)
                    html_content = generate_html_report(results, script_name, episode_info)
                    ep_label = f"EP{episode_info['current']}" if episode_info else "EP"
                    html_path = _output_path(script_name, f'{ep_label}_拆解报告.html')
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    word_path = generate_word_report(results, script_name, episode_info)
                except Exception:
                    logging.warning("最终报告生成失败", exc_info=True)
                    html_path = None; word_path = None
                step_names = {'characters':'角色提取','props':'道具提取','scenes':'场景拆解','shots':'分镜拆解'}
                yield json_sse("complete", {
                    "message": f"{step_names.get(step_filter, step_filter)}完成！",
                    "html_file": os.path.basename(html_path) if html_path else None,
                    "word_file": os.path.basename(word_path) if word_path else None,
                    "output_dir": config.OUTPUT_DIR,
                    "script_name": script_name,
                    "results": results
                })
        except Exception as e:
            logging.getLogger("app").error("分析过程出错: %s", str(e))
            yield json_sse("error", {"message": "分析过程出错，请稍后重试"})
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        }
    )


@app.route('/api/download/<filename>')
def download_report(filename):
    """下载生成的报告"""
    file_path = safe_join(config.OUTPUT_DIR, filename)
    if file_path is None or not os.path.isfile(file_path):
        return jsonify({"error": "文件不存在"}), 404
    
    # 判断文件类型
    if filename.endswith('.docx'):
        mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    else:
        mimetype = 'text/html; charset=utf-8'
    
    return send_file(
        file_path,
        mimetype=mimetype,
        as_attachment=True,
        download_name=os.path.basename(file_path)
    )


@app.route('/api/split-shots', methods=['POST'])
def split_shots():
    """将全剧分镜HTML按集拆分为独立文件"""
    data = request.get_json(silent=True) or {}
    script_name = data.get('script_name', '').strip()
    if not script_name:
        return jsonify({"error": "请提供剧本名称"}), 400
    try:
        from tool.shot_splitter import split_shots_by_episode
        result = split_shots_by_episode(script_name)
        return jsonify({"success": True, "folder": result["folder"], "files": result["files"], "count": result["count"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/preview/<filename>')
def preview_report(filename):
    """预览生成的 HTML 报告"""
    file_path = safe_join(config.OUTPUT_DIR, filename)
    if file_path is None or not os.path.isfile(file_path):
        return jsonify({"error": "文件不存在"}), 404
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return content, 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route('/api/preprocess', methods=['POST'])
def preprocess():
    """预处理人物小传和故事大纲，生成临时知识库"""
    if not _check_rate_limit(_get_client_id(), max_requests=20, window=60):
        return jsonify({"error": "请求过于频繁，请稍后重试"}), 429
    data = request.get_json(silent=True) or {}
    char_bio = (data.get('char_bio') or '').strip()
    story_outline = (data.get('story_outline') or '').strip()
    script_name = (data.get('script_name') or '未命名剧本').strip()
    api_config = data.get('api_config') or {}
    
    if not char_bio and not story_outline:
        return jsonify({"error": "请提供人物小传或故事大纲"}), 400
    
    script_name = re.sub(r'[\\/:*?"<>|]', '_', script_name)
    script_name = script_name.replace('\x00', '')
    script_name = script_name.lstrip('.-')
    script_name = script_name.strip()[:100] or "未命名剧本"
    
    preprocess_system = """你是剧本分析预处理专家。你的任务是分析人物小传和故事大纲，提取结构化信息。

人物小传分析要求：
- 提取每个角色的名称(name)、别名(aliases)、年龄种族(age_race)、性格标签(personality)、弧光走向(arc)、外貌特征(appearance)、人际关系(relationships)、关键特征(key_traits)

故事大纲分析要求：
- 提取年代/时空设定(time_period)、主要地点(location)、类型标签(genre)、整体基调(tone)、关键剧情道具(key_props)、关键情节点(key_plot_points)、环境风格描述(environment_style)

输出纯JSON："""
    
    preprocess_user = "请分析以下内容并生成结构化知识库。\n\n"
    if char_bio:
        preprocess_user += f"=== 人物小传 ===\n{char_bio}\n\n"
    if story_outline:
        preprocess_user += f"=== 故事大纲 ===\n{story_outline}\n\n"
    
    output_schema = (
        '输出JSON格式：\n'
        '{\n'
        '  "characters": [\n'
        '    {\n'
        '      "name": "角色名",\n'
        '      "aliases": ["别名"],\n'
        '      "age_race": "年龄/种族",\n'
        '      "personality": ["性格标签"],\n'
        '      "arc": "角色弧光走向",\n'
        '      "appearance": "外貌特征",\n'
        '      "relationships": [{"target": "关联角色", "relation": "关系描述"}],\n'
        '      "key_traits": "关键特征"\n'
        '    }\n'
        '  ],\n'
        '  "world": {\n'
        '    "time_period": "年代/时空设定",\n'
        '    "location": "主要地点",\n'
        '    "genre": "类型标签",\n'
        '    "tone": "整体基调",\n'
        '    "key_props": ["关键剧情道具"],\n'
        '    "key_plot_points": ["关键情节点"],\n'
        '    "environment_style": "环境风格描述"\n'
        '  }\n'
        '}\n'
        '只输出JSON。'
    )
    preprocess_user += output_schema
    
    try:
        raw = call_ai(preprocess_system, preprocess_user, api_config)
        parsed = None
        json_text = raw.strip()
        json_start = json_text.find('{')
        json_end = json_text.rfind('}')
        if json_start != -1 and json_end != -1:
            json_text = json_text[json_start:json_end+1]
        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError:
            return jsonify({"error": "AI 返回格式解析失败: " + raw[:300], "raw": raw[:500]}), 500
        
        series = _series_name(script_name)
        d = safe_join(config.OUTPUT_DIR, series) if series else safe_join(config.OUTPUT_DIR, script_name)
        if not d:
            return jsonify({"error": "非法剧本名称: " + script_name}), 400
        os.makedirs(d, exist_ok=True)
        kb_path = os.path.join(d, f'{series}_人物小传大纲_知识库.json')
        with open(kb_path, 'w', encoding='utf-8') as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)
        
        char_count = len(parsed.get('characters', []))
        char_names = [c.get('name', '') for c in parsed.get('characters', [])]
        world_info = parsed.get('world', {})
        
        return jsonify({
            "success": True,
            "message": "知识库已生成：" + str(char_count) + " 个角色，" + str(len(world_info)) + " 项世界观信息",
            "summary": {
                "char_count": char_count,
                "char_names": char_names,
                "world": world_info,
            }
        })
    except Exception as e:
        return jsonify({"error": "预处理失败: " + str(e)}), 500


@app.route('/api/get_materials', methods=['POST'])
def get_materials():
    """获取已存储的临时知识库摘要"""
    data = request.get_json(silent=True) or {}
    script_name = (data.get('script_name') or '').strip()
    if not script_name:
        return jsonify({"error": "请提供剧本名称"}), 400
    
    script_name = re.sub(r'[\\/:*?"<>|]', '_', script_name)
    script_name = script_name.replace('\x00', '')
    script_name = script_name.lstrip('.-')
    script_name = script_name.strip()[:100]
    
    series = _series_name(script_name)
    d = safe_join(config.OUTPUT_DIR, series) if series else safe_join(config.OUTPUT_DIR, script_name)
    if not d:
        return jsonify({"has_materials": False}), 200
    
    kb_path = os.path.join(d, f'{series}_人物小传大纲_知识库.json')
    if os.path.exists(kb_path):
        try:
            with open(kb_path, 'r', encoding='utf-8') as f:
                kb = json.load(f)
            char_count = len(kb.get('characters', []))
            char_names = [c.get('name', '') for c in kb.get('characters', [])]
            world_keys = list(kb.get('world', {}).keys())
            return jsonify({
                "has_materials": True,
                "char_count": char_count,
                "char_names": char_names,
                "world_keys": world_keys,
            })
        except Exception:
            return jsonify({"has_materials": False}), 200
    
    return jsonify({"has_materials": False}), 200


@app.route('/api/clear_materials', methods=['POST'])
def clear_materials():
    """清除指定剧本的临时知识库"""
    data = request.get_json(silent=True) or {}
    script_name = (data.get('script_name') or '').strip()
    if not script_name:
        return jsonify({"error": "请提供剧本名称"}), 400
    
    script_name = re.sub(r'[\\/:*?"<>|]', '_', script_name)
    script_name = script_name.replace('\x00', '')
    script_name = script_name.lstrip('.-')
    script_name = script_name.strip()[:100]
    
    series = _series_name(script_name)
    d = safe_join(config.OUTPUT_DIR, series) if series else safe_join(config.OUTPUT_DIR, script_name)
    if d and os.path.exists(os.path.join(d, f'{series}_人物小传大纲_知识库.json')):
        try:
            os.remove(os.path.join(d, f'{series}_人物小传大纲_知识库.json'))
        except OSError:
            pass
    
    return jsonify({"success": True, "message": "临时知识库已清除"})

# ============================================================
# 启动
# ============================================================

if __name__ == '__main__':
    if 'GUNICORN_CMD_ARGS' in os.environ or 'gunicorn' in sys.argv[0]:
        # gunicorn 会自己 import app，不需要 run
        pass
    else:
        # 开发环境：使用 Flask 内置服务器
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        
        print("=" * 60)
        print("  [Film] 剧本拆解大师 v2.49")
        print("=" * 60)
        print("  OpenAI Compatible API: POST /v1/chat/completions")
        print("  Ollama API: POST /api/chat")
        print()
        
        port = int(os.environ.get('PORT', 5000))
        debug = os.environ.get('FLASK_DEBUG', '0') == '1'
        print(f"  开发模式启动: http://localhost:{port}")
        if getattr(sys, 'frozen', False):
            print(f"  Output directory: {os.path.dirname(os.path.abspath(sys.executable))}")
        print("=" * 60)
        
        # 延迟1.5秒后自动打开默认浏览器（PyInstaller兼容）
        def open_browser():
            import time
            time.sleep(1.5)
            subprocess.run(['open', f'http://localhost:{port}'], check=False)
        threading.Thread(target=open_browser, daemon=True).start()
        
        app.run(
            host=config.BIND_HOST,
            port=port,
            debug=debug,
            threaded=True
        )
