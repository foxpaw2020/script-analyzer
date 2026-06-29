"""分镜拆解工具：将全剧分镜HTML按集拆分为独立HTML文件"""
import html, os, re, json, logging
from werkzeug.utils import safe_join
from config import OUTPUT_DIR

_log = logging.getLogger(__name__)


def _out_path(script_name, filename):
    d = safe_join(OUTPUT_DIR, script_name) if script_name else OUTPUT_DIR
    if not d:
        raise ValueError(f"非法剧本名称: {script_name}")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, filename)


def split_shots_by_episode(script_name):
    """按集拆分全剧分镜 HTML
    
    Returns:
        dict: {"folder": "输出文件夹路径", "files": ["文件名1", ...], "count": 文件数}
    """
    html_path = _out_path(script_name, f'{script_name}_分镜拆解.html')
    if not os.path.exists(html_path):
        full_path = _out_path(script_name, f'{script_name}_拆解报告.html')
        if os.path.exists(full_path):
            html_path = full_path
        else:
            raise FileNotFoundError(f'未找到分镜文件: {html_path}')
    
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # 提取分镜数据：查找 data-shots-json 脚本标签
    m = re.search(r'<script[^>]*id="shots-data"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        # fallback: 从分镜HTML中按shot_id分组
        shots_by_ep = _extract_shots_from_html(html)
    else:
        data = json.loads(m.group(1))
        shots_by_ep = {}
        for scene in data.get('scenes', []):
            for shot in scene.get('shots', []):
                sid = shot.get('shot_id', '')
                ep = sid.split('-')[0] if '-' in sid else '0'
                if ep not in shots_by_ep:
                    shots_by_ep[ep] = []
                shots_by_ep[ep].append({**shot, 'scene_title': scene.get('scene_title', '')})
    
    if not shots_by_ep:
        raise ValueError('未找到任何分镜数据')
    
    # 创建输出文件夹
    out_dir = _out_path(script_name, '全集散装分镜')
    os.makedirs(out_dir, exist_ok=True)
    
    # 读原始HTML提取头部样式
    head_match = re.search(r'<head>(.*?)</head>', html, re.DOTALL)
    head_content = head_match.group(1) if head_match else '<meta charset="UTF-8"><title>分镜</title>'
    
    files = []
    for ep_num in sorted(shots_by_ep.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        ep_shots = shots_by_ep[ep_num]
        ep_html = _build_episode_html(script_name, ep_num, ep_shots, head_content)
        fname = f'{script_name}_第{ep_num}集_分镜提示词.html'
        fpath = os.path.join(out_dir, fname)
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(ep_html)
        files.append(fname)
    
    return {"folder": out_dir, "files": files, "count": len(files)}


def _extract_shots_from_html(html):
    """从HTML中按shot_id正则提取分镜并分组（备用方案）"""
    shots_by_ep = {}
    # 匹配分镜卡片的shot_id（修复: [<d>] → [\d-]）
    pattern = r'<span class="shot-id">分镜 ([\d-]+)</span>'
    for m in re.finditer(pattern, html):
        sid = m.group(1)
        ep = sid.split('-')[0] if '-' in sid else '0'
        if ep not in shots_by_ep:
            shots_by_ep[ep] = []
        shots_by_ep[ep].append(sid)
    return shots_by_ep


def _build_episode_html(script_name, ep_num, shots, head_content):
    """生成单集分镜HTML"""
    shot_cards_html = ''
    for i, shot in enumerate(shots):
        sid = shot.get('shot_id', shot if isinstance(shot, str) else str(i+1))
        if isinstance(shot, dict):
            card = _render_shot_card(sid, shot)
        else:
            card = f'<div class="shot-card"><span class="shot-id">分镜 {sid}</span></div>'
        shot_cards_html += card
    
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
{head_content}
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0A0A0A; color: #E0E0E0; line-height: 1.6; }}
    .container {{ max-width: 900px; margin: 0 auto; padding: 40px 24px; }}
    .header {{ text-align: center; padding: 40px 0; border-bottom: 1px solid #2A2A2A; margin-bottom: 40px; }}
    .header h1 {{ font-size: 32px; color: #FFF; }}
    .header .sub {{ font-size: 16px; color: #FF9D00; margin-top: 8px; }}
    .shot-card {{ background: #151515; border: 1px solid #2A2A2A; border-radius: 10px; padding: 16px 20px; margin-bottom: 12px; }}
    .shot-id {{ font-size: 14px; font-weight: 600; color: #FF6600; }}
    .shot-attr {{ font-size: 13px; color: #AAA; line-height: 1.8; margin-top: 8px; }}
    .shot-attr strong {{ color: #FF9D00; }}
    .timeline-table {{ width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 12px; }}
    .timeline-table th {{ background: #222; color: #FF9D00; padding: 6px 10px; text-align: left; }}
    .timeline-table td {{ padding: 6px 10px; border-bottom: 1px solid #2A2A2A; color: #BBB; }}
    .end-frame {{ background: #1A1A1A; border-radius: 6px; padding: 10px 14px; margin-top: 8px; color: #BBB; border-left: 2px solid #FF6600; }}
    .constraints {{ font-size: 13px; color: #888; margin-top: 8px; line-height: 1.7; background: #111; padding: 10px; border-radius: 6px; }}
    .copy-btn {{ display: inline-block; padding: 4px 12px; background: #333; color: #CCC; border: none; border-radius: 6px; font-size: 11px; cursor: pointer; margin-top: 10px; }}
    .copy-btn:hover {{ background: #FF6600; color: #FFF; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>《{script_name}》第{ep_num}集 · 分镜提示词</h1>
        <div class="sub">共 {len(shots)} 个分镜</div>
    </div>
    {shot_cards_html}
</div>
<script>
    function copyShot(id, btn) {{
        var card = document.getElementById(id);
        var parts = [];
        var el = card.querySelector('.shot-id');
        if (el) parts.push(el.innerText);
        el = card.querySelector('.shot-attr');
        if (el) parts.push(el.innerText);
        var copyText = parts.join('\\n');
        navigator.clipboard.writeText(copyText).then(function() {{
            btn.textContent = '已复制!';
            btn.style.background = '#4CAF50';
            setTimeout(function() {{ btn.textContent = '复制分镜'; btn.style.background = '#333'; }}, 1500);
        }});
    }}
</script>
</body>
</html>'''


def _render_shot_card(shot_id, shot):
    """渲染单个分镜卡片（所有用户数据经 html.escape 防 XSS）"""
    esc = html.escape
    sid_safe = esc(str(shot_id))
    scene_title = esc(str(shot.get("scene_title", "—")))
    subject = esc(str(shot.get("subject", "—")))
    setting = esc(str(shot.get("setting", "—")))
    lighting = esc(str(shot.get("lighting", "—")))
    camera = esc(str(shot.get("camera", "—")))
    emotion = esc(str(shot.get("emotion", "—")))
    intensity = esc(str(shot.get("intensity", "—")))

    timeline_rows = ''
    for t in shot.get('timeline', []):
        if isinstance(t, list) and len(t) >= 3:
            timeline_rows += f'<tr><td>{esc(str(t[0]))}</td><td>{esc(str(t[1]))}</td><td>{esc(str(t[2]))}</td></tr>'
    
    timeline_html = ''
    if timeline_rows:
        timeline_html = f'<table class="timeline-table"><tr><th>时间</th><th>景别</th><th>动作</th></tr>{timeline_rows}</table>'
    
    end_frame = f'<div class="end-frame"><strong>收尾画面:</strong> {esc(str(shot["end_frame"]))}</div>' if shot.get('end_frame') else ''
    constraints = f'<div class="constraints">{esc(str(shot["constraints"]))}</div>' if shot.get('constraints') else ''

    dom_id = shot_id.replace("-", "_")
    
    return f'''<div class="shot-card" id="shot_{dom_id}">
    <div class="shot-id">分镜 {sid_safe}</div>
    <div class="shot-attr">
        <strong>场景:</strong> {scene_title}<br>
        <strong>主体:</strong> {subject}<br>
        <strong>场景:</strong> {setting}<br>
        <strong>光影:</strong> {lighting}<br>
        <strong>镜头:</strong> {camera}<br>
        <strong>情绪:</strong> {emotion} | 烈度: {intensity}
    </div>
    {timeline_html}
    {end_frame}
    {constraints}
    <button class="copy-btn" onclick="copyShot('shot_{dom_id}', this)">复制分镜</button>
</div>'''
