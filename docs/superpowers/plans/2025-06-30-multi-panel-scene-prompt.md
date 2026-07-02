# 场景多面板布局参考图提示词 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 场景提取输出增加第三种提示词类型——多面板布局参考图（GPT-Image-2 专用）

**Architecture:** 在场景提取知识库 JSON 中新增 `multi_panel_gpt` 模版，在 `scenes.py` 系统提示词中要求 AI 输出该字段，在 `report.html` 中渲染展示卡片

**Tech Stack:** Python 3, Flask, Jinja2, JSON

## Global Constraints

- 多面板仅出 GPT-Image-2 版本，不出 Nano 版
- 场景物件和光影由 AI 根据十层数据自由组织
- 底部画质段固定不变
- HTML 输出必须附带复制和修改按钮
- 排在俯视图 GPT 之后

---

### Task 1: 知识库新增 multi_panel_gpt 模版

**Files:**
- Modify: `knowledge_base/Scene_Extraction_Skills_v5.1.json` → 升级为 v5.2

**Interfaces:**
- Produces: `output_templates.multi_panel_gpt` 模版字符串

- [ ] **Step 1: 读取当前 JSON，新增模板并升级版本号**

```python
import json

with open('knowledge_base/Scene_Extraction_Skills_v5.1.json', 'r', encoding='utf-8') as f:
    kb = json.load(f)

# 升级 meta 版本
kb['meta']['version'] = 'v5.2'

# 新增多面板模板
kb['output_templates']['multi_panel_gpt'] = (
    "多面板 {场景名称} 概念设计稿，同一场景的多视角呈现，"
    "顶部为 {场景主广角全景}，中间行为 {关键空间分区缩略图}，"
    "底部为 {整场纵览大图}，附带 {2-3个特写细节插图}，"
    "{场景类型标签}，影视美术设计拆解，清晰的分镜排版\n\n"
    "场景与物件\n"
    "{从十层提取：空间骨架 + 真实材质 + 陈设道具 + 文字标识}\n\n"
    "光影与色调\n"
    "{从十层提取：光源位置色温 + 实拍氛围 + 光影方案}\n\n"
    "画质与风格\n"
    "超写实，超高细节，写实3D渲染，精细的环境细节，真实的材质纹理，"
    "8k，高分辨率，电影级构图，Artstation热门风格，"
    "大师级概念艺术，影视美术设计，物理基于渲染"
)

# 另存为 v5.2
with open('knowledge_base/Scene_Extraction_Skills_v5.2.json', 'w', encoding='utf-8') as f:
    json.dump(kb, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 2: 验证 JSON 格式**

```bash
python3 -c "import json; json.load(open('knowledge_base/Scene_Extraction_Skills_v5.2.json')); print('VALID')"
```
Expected: `VALID`

- [ ] **Step 3: Commit**

```bash
git add knowledge_base/Scene_Extraction_Skills_v5.2.json
git commit -m "feat: Scene_Extraction_Skills v5.2 — 新增 multi_panel_gpt 多面板布局模板"
```

---

### Task 2: scenes.py 更新引用 + 输出字段

**Files:**
- Modify: `extractors/scenes.py`

**Interfaces:**
- Consumes: `knowledge_base/Scene_Extraction_Skills_v5.2.json` 的 `output_templates.multi_panel_gpt`
- Consumes: `config.KNOWLEDGE_BASE_DIR` 路径
- Produces: 每个场景对象增加 `multi_panel_gpt` 字段

- [ ] **Step 1: 更新 scenes.py 中的知识库引用路径从 v5.1 → v5.2**

在 `extractors/scenes.py` 中找到加载 Scene_Extraction_Skills 的行，将 `v5.1` 改为 `v5.2`：

```python
# 搜索并替换：
# 'Scene_Extraction_Skills_v5.1.json' → 'Scene_Extraction_Skills_v5.2.json'
```

- [ ] **Step 2: 在 DETAIL_SYSTEM 输出格式 JSON 示例中增加 multi_panel_gpt 字段**

找到 `DETAIL_SYSTEM` 变量中的 JSON 示例（约第 58-65 行），在 `topdown_gpt` 之后追加：

```python
# 在 "topdown_gpt":"俯视图版 GPT-Image-2 完整提示词", 之后添加：
# "multi_panel_gpt":"多面板布局参考图 GPT-Image-2 完整提示词",
```

- [ ] **Step 3: 在 DETAIL_SYSTEM 说明中增加第三个提示词类型的指令**

在描述输出要求的区域（约第 40-50 行附近），追加说明段落：

```
3. 多面板布局版——每个场景输出1组提示词：多面板版(GPT-Image-2专用)
```

- [ ] **Step 4: 在 parse_detail_response 函数中兼容 multi_panel_gpt 字段（无需改动，JSON 自动透传）**

`parse_detail_response` 将 AI 返回的 JSON 逐字段透传，无需额外处理。验证思路：

```python
# 确认场景字典中 multi_panel_gpt 字段会被保留
# 可在 _normalize_scene 中添加默认值：
scene.setdefault("multi_panel_gpt", "")
```

- [ ] **Step 5: 验证语法**

```bash
python3 -c "import extractors.scenes; print('IMPORT OK')"
```
Expected: `IMPORT OK`

- [ ] **Step 6: Commit**

```bash
git add extractors/scenes.py
git commit -m "feat: scenes.py — 场景提取增加 multi_panel_gpt 多面板输出字段"
```

---

### Task 3: report.html 增加多面板展示卡片

**Files:**
- Modify: `templates/report.html`

**Interfaces:**
- Consumes: `scene.multi_panel_gpt` 字段（Jinja2 模板变量）

- [ ] **Step 1: 在俯视图 GPT 卡片之后追加多面板卡片**

在 `templates/report.html` 中找到俯视图 GPT 卡片的结束位置（约第 311 行 `</div>` 后），追加以下 Jinja2 代码：

```html
                {% if scene.multi_panel_gpt %}
                <div class="prompt-pair">
                    <div class="prompt-label">多面板布局参考图 · GPT-Image-2</div>
                    <div class="prompt-block" id="mp_prompt_{{ loop.index0 }}">{{ scene.multi_panel_gpt }}</div>
                    <button class="copy-btn" onclick="copyPrompt('mp_prompt_{{ loop.index0 }}', this)">复制</button>
                    <button class="edit-btn" onclick="toggleEdit('mp_prompt_{{ loop.index0 }}', this)" id="edit_mp_prompt_{{ loop.index0 }}">修改提示词</button>
                    <button class="save-btn" onclick="savePrompt('mp_prompt_{{ loop.index0 }}', this)" id="save_mp_prompt_{{ loop.index0 }}" style="display:none;">保存修改</button>
                    <span class="version-info" id="ver_mp_prompt_{{ loop.index0 }}"></span>
                </div>
                {% endif %}
```

- [ ] **Step 2: 验证 HTML 语法**

```bash
python3 -c "
from jinja2 import Environment
env = Environment()
with open('templates/report.html') as f:
    env.parse(f.read())
print('VALID TEMPLATE')
"
```
Expected: `VALID TEMPLATE`

- [ ] **Step 3: Commit**

```bash
git add templates/report.html
git commit -m "feat: report.html — 场景详情增加多面板布局参考图展示卡片（含复制/修改按钮）"
```

---

### Task 4: 端到端验证

- [ ] **Step 1: 清缓存并重启服务**

```bash
cd /Users/foxpaw/Documents/web-wm-ai/script-analyzer
rm -rf __pycache__ extractors/__pycache__
screen -S flask-app -X quit 2>/dev/null
screen -dmS flask-app bash -c "PORT=5001 python3 app.py"
sleep 2
curl -s -o /dev/null -w "%{http_code}" http://localhost:5001/
```
Expected: `200`

- [ ] **Step 2: 验证知识库加载正确**

```bash
python3 -c "
import json
with open('knowledge_base/Scene_Extraction_Skills_v5.2.json') as f:
    kb = json.load(f)
t = kb['output_templates']['multi_panel_gpt']
assert '多面板' in t
assert '画质与风格' in t
assert '超写实' in t
print('模版内容验证通过')
"
```
Expected: `模版内容验证通过`

- [ ] **Step 3: Commit**

```bash
git commit --allow-empty -m "verify: 多面板功能端到端验证通过"
```

---

