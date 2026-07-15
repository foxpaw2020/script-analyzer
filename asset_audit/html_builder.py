"""HTML 汇总生成器 - 可编辑交互式全剧资产表（剧本拆解报告风格）"""
import json, os

CSS = r"""
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    background: #0A0A0A;
    color: #E0E0E0;
    line-height: 1.6;
}
.container { max-width: 960px; margin: 0 auto; padding: 40px 24px; }

.report-header { text-align: center; padding: 60px 0 40px; border-bottom: 1px solid #2A2A2A; margin-bottom: 48px; }
.report-header h1 { font-size: 42px; font-weight: 700; color: #FFF; letter-spacing: -0.02em; margin-bottom: 12px; }
.report-header .subtitle { font-size: 18px; color: #999; }
.report-header .meta { font-size: 14px; color: #666; margin-top: 8px; }

.global-actions { display: flex; gap: 10px; margin-bottom: 32px; flex-wrap: wrap; align-items: center; }
.btn { padding: 8px 20px; border-radius: 20px; border: 1px solid #333; background: #1A1A1A; color: #999; font-size: 14px; cursor: pointer; transition: all 0.3s; font-family: inherit; }
.btn:hover { background: #2A2A2A; color: #FFF; border-color: #555; }
.btn.primary { background: linear-gradient(135deg, #FF6600, #FF9D00); color: #FFF; border: none; font-weight: 600; }
.btn.primary:hover { opacity: 0.9; color: #FFF; }
.btn-sm { padding: 4px 12px; font-size: 11px; border-radius: 6px; }
.btn.save { background: #238636; border-color: #238636; color: #fff; }
.btn.save:hover { background: #2ea043; border-color: #2ea043; color: #fff; }
.btn.danger:hover { background: #da3633; border-color: #da3633; color: #fff; }

.section { margin-bottom: 60px; }
.section-header { display: flex; align-items: center; gap: 16px; margin-bottom: 32px; padding-bottom: 16px; border-bottom: 1px solid #2A2A2A; }
.section-header h2 { font-size: 28px; font-weight: 600; color: #FFF; }
.section-header .count { background: linear-gradient(135deg, #FF6600, #FF9D00); color: #FFF; padding: 4px 14px; border-radius: 20px; font-size: 14px; font-weight: 600; }
.section-header .ep-actions-header { margin-left: auto; display: flex; gap: 8px; }

.asset-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px; }
.asset-card { background: #1A1A1A; border-radius: 12px; padding: 18px 20px; border-left: 3px solid #FF6600; transition: transform 0.2s, box-shadow 0.2s; position: relative; }
.asset-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(255, 102, 0, 0.08); }
.asset-card.editing { border-left-color: #FF9D00; box-shadow: 0 0 0 1px rgba(255, 157, 0, 0.2); }
.asset-card .field { margin-bottom: 4px; font-size: 14px; }
.asset-card .field .label { font-size: 10px; color: #888; text-transform: uppercase; letter-spacing: 0.06em; margin-right: 6px; display: inline-block; min-width: 50px; }
.asset-card .field .value { color: #CCC; word-break: break-word; }
.asset-card .asset-name { font-size: 15px; font-weight: 600; color: #FFF; margin-bottom: 6px; }
.asset-card .asset-name .en { font-weight: 400; color: #999; font-size: 13px; }
.asset-card .card-actions { display: flex; gap: 6px; margin-top: 10px; justify-content: flex-end; }

.edit-input, .edit-textarea { width: 100%; background: #0D0D0D; border: 1px solid #333; border-radius: 6px; color: #E0E0E0; font-size: 13px; padding: 6px 8px; font-family: inherit; resize: vertical; margin-bottom: 4px; }
.edit-textarea { min-height: 50px; }
.edit-input:focus, .edit-textarea:focus { border-color: #FF9D00; outline: none; }

.col-section { margin-bottom: 32px; }
.col-title { font-size: 16px; font-weight: 700; color: #FFF; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid #2A2A2A; display: flex; align-items: center; gap: 8px; }
.col-title .count { background: rgba(255, 102, 0, 0.15); color: #FF9D00; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }

.btn-add { width: 100%; text-align: center; padding: 10px; border: 1px dashed #333; background: transparent; color: #666; border-radius: 8px; cursor: pointer; transition: all 0.2s; font-size: 13px; font-family: inherit; }
.btn-add:hover { border-color: #FF9D00; color: #FF9D00; background: rgba(255, 157, 0, 0.03); }

.toast { position: fixed; bottom: 32px; right: 32px; padding: 12px 24px; border-radius: 8px; font-size: 13px; z-index: 999; opacity: 0; transform: translateY(12px); transition: all 0.3s; pointer-events: none; font-weight: 600; }
.toast.show { opacity: 1; transform: translateY(0); }
.toast.ok { background: #238636; color: #FFF; }
.toast.err { background: #DA3633; color: #FFF; }
"""

JS_TPL = r"""const DATA = __DATA__;
const SERIES = __SERIES__;
let data = JSON.parse(JSON.stringify(DATA));

function saveAll() {
    localStorage.setItem('audit_assets_' + SERIES, JSON.stringify(data));
    toast('全部修改已保存', 'ok');
}

function loadSaved() {
    const saved = localStorage.getItem('audit_assets_' + SERIES);
    if (saved) {
        try { data = JSON.parse(saved); renderAll(); toast('已恢复上次保存', 'ok'); }
        catch(e) { toast('恢复失败', 'err'); }
    } else { toast('没有已保存的数据', 'err'); }
}

function saveEpisode(epIdx) {
    const ep = data[epIdx];
    ['characters','props','scenes'].forEach(function(cat) {
        var items = [];
        var container = document.getElementById('ep-' + epIdx + '-' + cat);
        if (!container) return;
        var cards = container.querySelectorAll('.asset-card');
        cards.forEach(function(card) {
            var inputs = card.querySelectorAll('.edit-input, .edit-textarea');
            var item = {};
            inputs.forEach(function(inp) { item[inp.dataset.field] = inp.value; });
            if (Object.keys(item).length) items.push(item);
        });
        ep[cat] = items;
    });
    localStorage.setItem('audit_assets_' + SERIES, JSON.stringify(data));
    renderEpisode(epIdx);
    toast('已保存', 'ok');
}

function editItem(epIdx, cat, itemIdx) {
    var item = data[epIdx][cat][itemIdx];
    var container = document.getElementById('ep-' + epIdx + '-' + cat);
    var cards = container.querySelectorAll('.asset-card');
    var card = cards[itemIdx];
    var fields = Object.keys(item).filter(function(k) { return k !== '_id'; });

    var html = '';
    fields.forEach(function(f) {
        var isLong = f === 'costume' || f === 'usage' || f === 'synopsis';
        if (isLong) {
            html += '<textarea class="edit-textarea" data-field="' + f + '" rows="2">' + esc(item[f] || '') + '</textarea>';
        } else {
            html += '<input class="edit-input" data-field="' + f + '" value="' + esc(item[f] || '') + '">';
        }
    });
    html += '<div class="card-actions">';
    html += '<button class="btn btn-sm primary" onclick="doneEdit(' + epIdx + ',\'' + cat + '\',' + itemIdx + ')">完成</button>';
    html += '</div>';
    card.innerHTML = html;
    card.classList.add('editing');
    var fi = card.querySelector('input,textarea');
    if (fi) fi.focus();
}

function doneEdit(epIdx, cat, itemIdx) {
    var container = document.getElementById('ep-' + epIdx + '-' + cat);
    var cards = container.querySelectorAll('.asset-card');
    var card = cards[itemIdx];
    var inputs = card.querySelectorAll('.edit-input, .edit-textarea');
    var item = {};
    inputs.forEach(function(inp) { item[inp.dataset.field] = inp.value; });
    data[epIdx][cat][itemIdx] = item;
    renderEpisode(epIdx);
    toast('已修改', 'ok');
}

function deleteItem(epIdx, cat, itemIdx) {
    data[epIdx][cat].splice(itemIdx, 1);
    renderEpisode(epIdx);
    toast('已删除', 'ok');
}

function addItem(epIdx, cat) {
    var templates = {
        characters: {name_cn:'', name_en:'', costume:''},
        props: {name_cn:'', usage:''},
        scenes: {name_cn:'', name_en:'', synopsis:''}
    };
    data[epIdx][cat].push(templates[cat]);
    renderEpisode(epIdx);
    var idx = data[epIdx][cat].length - 1;
    setTimeout(function() { editItem(epIdx, cat, idx); }, 100);
}

function renderCard(item, cat) {
    if (cat === 'characters') {
        var html = '<div class="asset-name">' + esc(item.name_cn || '未命名');
        if (item.name_en) html += ' <span class="en">' + esc(item.name_en) + '</span>';
        html += '</div>';
        html += '<div class="field"><span class="label">服装</span><span class="value">' + esc(item.costume || '—') + '</span></div>';
        return html;
    } else if (cat === 'props') {
        var html = '<div class="asset-name">' + esc(item.name_cn || '未命名') + '</div>';
        html += '<div class="field"><span class="label">情景</span><span class="value">' + esc(item.usage || '—') + '</span></div>';
        return html;
    } else {
        var html = '<div class="asset-name">' + esc(item.name_cn || '未命名');
        if (item.name_en) html += ' <span class="en">' + esc(item.name_en) + '</span>';
        html += '</div>';
        html += '<div class="field"><span class="label">剧情</span><span class="value">' + esc(item.synopsis || '—') + '</span></div>';
        return html;
    }
}

function renderEpisode(epIdx) {
    var ep = data[epIdx];
    var body = document.getElementById('ep-body-' + epIdx);
    if (!body) return;

    var catNames = {characters:'人物', props:'道具', scenes:'场景'};
    var html = '<div class="ep-actions-header" style="display:flex;gap:8px;margin-bottom:20px;">';
    html += '<button class="btn btn-sm save" onclick="saveEpisode(' + epIdx + ')">保存本集</button>';
    html += '</div>';

    ['characters','props','scenes'].forEach(function(cat) {
        var items = ep[cat] || [];
        html += '<div class="col-section"><div class="col-title">' + catNames[cat] + ' <span class="count">' + items.length + '</span></div>';
        html += '<div class="asset-grid" id="ep-' + epIdx + '-' + cat + '">';
        items.forEach(function(item, ii) {
            html += '<div class="asset-card"><div class="card-body">' + renderCard(item, cat) + '</div>';
            html += '<div class="card-actions">';
            html += '<button class="btn btn-sm" onclick="editItem(' + epIdx + ',\'' + cat + '\',' + ii + ')">修改</button>';
            html += '<button class="btn btn-sm danger" onclick="deleteItem(' + epIdx + ',\'' + cat + '\',' + ii + ')">删除</button>';
            html += '</div></div>';
        });
        html += '</div>';
        html += '<button class="btn-add" onclick="addItem(' + epIdx + ',\'' + cat + '\')">+ 添加' + catNames[cat] + '</button>';
        html += '</div>';
    });
    body.innerHTML = html;

    var stats = document.getElementById('ep-stats-' + epIdx);
    if (stats) {
        stats.innerHTML = '<span>人物 ' + (ep.characters||[]).length + '</span><span>道具 ' + (ep.props||[]).length + '</span><span>场景 ' + (ep.scenes||[]).length + '</span>';
    }
}

function renderAll() {
    var html = '';
    data.forEach(function(ep, i) {
        var chars = (ep.characters||[]).length;
        var props = (ep.props||[]).length;
        var scenes = (ep.scenes||[]).length;
        var total = chars + props + scenes;
        html += '<div class="section" id="ep-section-' + i + '">';
        html += '<div class="section-header">';
        html += '<h2>第' + (i+1) + '集</h2>';
        html += '<span class="count">' + total + ' 项资产</span>';
        html += '<div class="ep-actions-header" style="margin-left:auto;display:flex;gap:8px;">';
        html += '<button class="btn btn-sm save" onclick="saveEpisode(' + i + ')">保存本集</button>';
        html += '</div></div>';
        html += '<div class="section-summary" style="background:#1A1A1A;border-left:3px solid #FF6600;padding:16px 20px;border-radius:0 12px 12px 0;margin-bottom:24px;color:#999;font-size:14px;">';
        html += '人物 <strong style="color:#FF9D00;">' + chars + '</strong> · 道具 <strong style="color:#FF9D00;">' + props + '</strong> · 场景 <strong style="color:#FF9D00;">' + scenes + '</strong></div>';
        html += '<div id="ep-body-' + i + '"></div>';
        html += '</div>';
    });
    document.getElementById('root').innerHTML = html;

    // Render each episode body
    data.forEach(function(ep, i) { renderEpisode(i); });
}

function esc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function toast(msg, type) {
    var t = document.getElementById('toast');
    t.textContent = msg; t.className = 'toast ' + type + ' show';
    setTimeout(function() { t.classList.remove('show'); }, 2500);
}

function exportHTML() {
    saveAll();
    var blob = new Blob([document.documentElement.outerHTML], {type:'text/html'});
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = SERIES + '_全剧资产汇总.html'; a.click();
    toast('已导出', 'ok');
}

document.addEventListener('DOMContentLoaded', function() {
    renderAll();
    var saved = localStorage.getItem('audit_assets_' + SERIES);
    if (saved) {
        try {
            var s = JSON.parse(saved);
            if (JSON.stringify(s) !== JSON.stringify(data)) {
                toast('检测到本地保存的修改，点击「恢复上次保存」加载', 'ok');
            }
        } catch(e) {}
    }
});
"""

HTML_HEAD = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{series_name} · 全剧资产汇总</title>
<style>
{css}
</style>
</head>
<body>
<div class="container">

<div class="report-header">
    <h1>{series_name} · 全剧资产汇总</h1>
    <div class="subtitle">可编辑交互式资产表 — 点击「修改」编辑 · 点击「保存本集」持久化</div>
    <div class="meta">所有修改自动存储在浏览器本地 · 支持添加/删除/编辑</div>
</div>

<div class="global-actions">
    <button class="btn" onclick="loadSaved()">恢复上次保存</button>
    <button class="btn primary" onclick="saveAll()">保存全部修改</button>
    <button class="btn" onclick="exportHTML()">导出 HTML</button>
</div>

<div id="root"></div>
<div id="toast" class="toast"></div>

<script>
"""

HTML_TAIL = """</script>
</div>
</body>
</html>"""


def build_summary_html(all_episode_assets, series_name, output_path):
    data = []
    for ep in all_episode_assets:
        data.append({
            "characters": ep.get("characters", []),
            "props": ep.get("props", []),
            "scenes": ep.get("scenes", [])
        })

    data_json = json.dumps(data, ensure_ascii=False)
    series_json = json.dumps(series_name, ensure_ascii=False)

    js_code = JS_TPL.replace('__DATA__', data_json).replace('__SERIES__', series_json)

    parts = []
    parts.append(HTML_HEAD.format(series_name=series_name, css=CSS))
    parts.append(js_code)
    parts.append(HTML_TAIL)

    html = ''.join(parts)

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return output_path
