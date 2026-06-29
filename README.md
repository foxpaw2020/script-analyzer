# 🎬 剧本拆解大师 Script Analyzer

> AI-powered script breakdown tool for film/TV production. Extract characters, props, scenes, and storyboard shots from screenplays. Outputs HTML + Word reports with generation-ready AI prompts.

[中文说明](#中文使用说明) | [English Guide](#english-guide)

---

## English Guide

### What It Does

```
Paste/Upload Script → AI Analysis → Four-Step Breakdown
─────────────────────────────────────────────────────────
  Characters  →   Props    →   Scenes    →   Storyboard
      ↓            ↓            ↓              ↓
  Profile Card   Info Card    Dual Prompts   6-Module Shots
  AI Prompt      AI Prompt    Wide+Topdown   Timeline Chains
```

Each step outputs **independent HTML and Word files** as soon as it completes.

### Tech Stack

- **Backend**: Python 3.9+ / Flask / SSE real-time progress
- **Frontend**: Vanilla JS + CSS / Jinja2 templates
- **AI**: DeepSeek API (recommended) or Ollama local models
- **Reports**: python-docx (Word) / Jinja2 (HTML)

### Quick Start

```bash
pip install -r requirements.txt
PORT=5005 python3 app.py
# Open http://localhost:5005
```

### AI Configuration

| Provider | Required | How to Get |
|----------|----------|------------|
| **DeepSeek API** | API Key | Sign up at [platform.deepseek.com](https://platform.deepseek.com) |
| **Ollama** | None | Install [Ollama](https://ollama.com) and start it locally |

**Recommended model**: `deepseek-v4-flash` (1M context window, fastest)

### Usage

1. Paste your script text or upload a `.txt` / `.docx` / `.pdf` file
2. Select AI provider and fill in your API Key (if using DeepSeek)
3. Click **开始分析** (Start Analysis)
4. Watch the progress bar as it runs through all four steps
5. Download HTML / Word reports

### Output Files

Reports are saved under `outputs/<script-name>/`:

```
outputs/ScriptName/
├── 角色提取.html         Characters.html
├── 道具提取.html         Props.html
├── 场景拆解.html         Scenes.html
├── 分镜拆解.html         Storyboard.html
└── *.docx                (Word versions)
```

### Project Structure

```
script-analyzer/
├── app.py                    # Flask routes + four-step generators
├── config.py                 # Model / API configuration
├── extractors/               # Extractors (prompt + parse logic)
│   ├── base.py               # Shared JSON repair base class
│   ├── characters.py         # Character extraction
│   ├── props.py              # Prop extraction
│   ├── scenes.py             # Scene breakdown
│   └── shots.py              # Storyboard breakdown
├── services/
│   ├── ai_service.py         # AI calls (strategy pattern)
│   └── file_parser.py        # PDF/Word/TXT parsing
├── reports/
│   ├── html_report.py        # HTML report generation
│   └── word_report.py        # Word report generation
├── static/                   # Frontend assets
│   ├── index.html
│   ├── js/app.js
│   └── css/style.css
├── templates/
│   └── report.html           # Jinja2 report template
├── knowledge_base/           # JSON knowledge bases for prompts
├── utils/                    # Utilities (SSE / text processing)
└── requirements.txt
```

### Configuration

Available via the "Advanced Parameters" panel or `.env`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `PORT` | 5000 | Server port |
| `max_tokens` | 4000 | Max output tokens per AI call |
| `temperature` | 0 | Generation randomness |
| `top_p` | 0.95 | Nucleus sampling |

### License

MIT

---

## 中文使用说明

⚠️⚠️⚠️一定要一集一集拆解，不要整个剧本扔进去，模型上下文处理不了⚠️⚠️⚠️

### 功能

```
粘贴/上传剧本 → AI 分析 → 四步拆解
────────────────────────────────────────
  角色提取 → 道具提取 → 场景拆解 → 分镜拆解
      ↓          ↓          ↓          ↓
  角色信息卡   道具信息卡   双版提示词   六模块分镜
  角色提示词   道具提示词   全景+俯视   秒级动作链
```

每个步骤完成后**即时输出**独立的 HTML 和 Word 文件。

### 技术栈

- **后端**: Python 3.9+ / Flask / SSE 实时进度推送
- **前端**: 原生 JS + CSS / Jinja2 模板
- **AI**: 支持 DeepSeek API 和 Ollama 本地模型
- **报告**: python-docx (Word) / Jinja2 (HTML)

### 快速开始

```bash
pip install -r requirements.txt
PORT=5005 python3 app.py
# 浏览器打开 http://localhost:5005
```

### 配置 AI

| 提供商 | 需要填写 | 说明 |
|--------|---------|------|
| **DeepSeek API**（推荐） | API Key | 到 [platform.deepseek.com](https://platform.deepseek.com) 创建 |
| **Ollama**（本地） | 无 | 需先安装并启动 [Ollama](https://ollama.com) |

**推荐模型**: `deepseek-v4-flash`（1M 上下文，速度最快）

### 使用

1. 粘贴剧本文字或上传 `.txt` / `.docx` / `.pdf` 文件
2. 选择 AI 提供商并填入 API Key（DeepSeek）
3. 点击 **开始分析**
4. 等待进度条走完四步拆解
5. 查看结果 → 下载 HTML / Word 报告

### 输出文件

分析完成后，报告保存在 `outputs/剧本名/` 下：

```
outputs/剧名/
├── 角色提取.html         角色提取.docx
├── 道具提取.html         道具提取.docx
├── 场景拆解.html         场景拆解.docx
└── 分镜拆解.html         分镜拆解.docx
```

### 项目结构

```
script-analyzer/
├── app.py                    # Flask 主路由 + 四步生成器
├── config.py                 # 模型 / API 配置
├── extractors/               # 提取器（prompt + 解析逻辑）
│   ├── base.py               # 公共 JSON 修复基类
│   ├── characters.py         # 角色提取
│   ├── props.py              # 道具提取
│   ├── scenes.py             # 场景拆解
│   └── shots.py              # 分镜拆解
├── services/
│   ├── ai_service.py         # AI 调用（策略模式）
│   └── file_parser.py        # PDF/Word/TXT 解析
├── reports/
│   ├── html_report.py        # HTML 报告生成
│   └── word_report.py        # Word 报告生成
├── static/                   # 前端静态资源
│   ├── index.html
│   ├── js/app.js
│   └── css/style.css
├── templates/
│   └── report.html           # Jinja2 报告模板
├── knowledge_base/           # 知识库 JSON
├── utils/                    # 工具函数（SSE / 文本处理）
└── requirements.txt
```

### 配置项

通过网页界面的「高级参数」或在 `.env` 中设置：

| 参数 | 默认值 | 说明 |
|------|-------|------|
| `PORT` | 5000 | 服务端口 |
| `max_tokens` | 4000 | AI 单次输出上限 |
| `temperature` | 0 | 生成随机性 |
| `top_p` | 0.95 | 核采样 |

### License

MIT
