# 🎬 剧本拆解大师 Script Analyzer

AI 驱动的剧本工业化拆解工具，一站式提取角色、道具、场景、分镜，输出 HTML + Word 双格式报告。

## 功能

```
粘贴/上传剧本 → AI 分析 → 四步拆解
────────────────────────────────────────
  角色提取 → 道具提取 → 场景拆解 → 分镜拆解
      ↓          ↓          ↓          ↓
  角色信息卡   道具信息卡   双版提示词   六模块分镜
  角色提示词   道具提示词   全景+俯视   秒级动作链
```

每个步骤完成后**即时输出**独立的 HTML 和 Word 文件。

## 技术栈

- **后端**: Python 3.9+ / Flask / SSE 实时进度推送
- **前端**: 原生 JS + CSS / Jinja2 模板
- **AI**: 支持 DeepSeek API 和 Ollama 本地模型
- **报告**: python-docx (Word) / Jinja2 (HTML)

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

```bash
PORT=5005 python3 app.py
```

浏览器打开 `http://localhost:5005`

### 3. 配置 AI

| 提供商 | 需要填写 | 说明 |
|--------|---------|------|
| **DeepSeek API**（推荐） | API Key | 到 [platform.deepseek.com](https://platform.deepseek.com) 创建 |
| **Ollama**（本地） | 无 | 需先安装并启动 [Ollama](https://ollama.com) |

**推荐模型**: `deepseek-v4-flash`（1M 上下文，速度最快）

### 4. 使用

1. 粘贴剧本文字或上传 `.txt` / `.docx` / `.pdf` 文件
2. 选择 AI 提供商并填入 API Key（DeepSeek）
3. 点击 **开始分析**
4. 等待进度条走完四步拆解
5. 查看结果 → 下载 HTML / Word 报告

## 输出文件

分析完成后，报告保存在 `outputs/剧本名/` 下：

```
outputs/剧名/
├── 角色提取.html         角色提取.docx
├── 道具提取.html         道具提取.docx
├── 场景拆解.html         场景拆解.docx
└── 分镜拆解.html         分镜拆解.docx
```

## 项目结构

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

## 配置项

通过网页界面的「高级参数」或在 `.env` 中设置：

| 参数 | 默认值 | 说明 |
|------|-------|------|
| `PORT` | 5000 | 服务端口 |
| `max_tokens` | 4000 | AI 单次输出上限 |
| `temperature` | 0 | 生成随机性 |
| `top_p` | 0.95 | 核采样 |

## License

MIT
