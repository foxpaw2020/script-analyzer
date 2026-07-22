# 剧本拆解大师 v2.52 全面应用审计报告

**审计日期:** 2026-07-21  
**应用版本:** v2.52（前端页面显示 v2.55）  
**审计模型:** Ollama `ornith:latest`  
**审计范围:** 静态代码分析 + 本地运行时测试 + 红队探针  

---

## 执行摘要

| 维度 | 风险评级 | 说明 |
|------|----------|------|
| 服务端安全 | 🔴 高 | 存在多处 SSRF、CORS 过宽、上传校验不足 |
| 前端安全 | 🟠 中 | API Key 落 localStorage、自定义 HTML 净化可绕过 |
| 代码质量 | 🟠 中 | app.py 过大、异常处理过宽、重复代码、测试依赖缺失 |
| AI 流程 | 🟠 中 | Prompt 注入不可避免、JSON 解析复杂但兜底完善 |
| 性能稳定 | 🟡 低中 | 大文件/长 AI 调用缺乏取消与流控 |

**整体建议：** 优先修复 SSRF 和 CORS，随后集中治理 `app.py` 的体积与异常处理，最后补齐测试与前端密钥管理。

---

## 1. 安全 findings

### 1.1 🔴 高危：/api/check_connection 存在 SSRF

- **位置:** `app.py:502-538`
- **描述:** 该接口接收用户传入的 `base_url`，未做任何白名单校验，直接发起 HTTP 请求。可探测内网（`169.254.169.254`）、访问本地服务，或作为跳板对外发起请求。
- **复现:**
  ```bash
  curl -X POST http://127.0.0.1:8080/api/check_connection \
    -H "Content-Type: application/json" \
    -d '{"provider":"deepseek","base_url":"http://169.254.169.254","api_key":"x"}'
  # 返回：无法连接到 http://169.254.169.254/models
  ```
- **影响:** 攻击者可扫描内网、读取云厂商 metadata、对第三方服务发起请求。
- **修复建议:** 复用 `ALLOWED_BASE_URLS` 校验逻辑；仅允许已配置的提供商域名/IP；默认拒绝非白名单地址。

---

### 1.2 🔴 高危：/api/analyze 主分析接口存在 SSRF

- **位置:** `app.py:626-630`（api_config 解析）→ `services/ai_service.py:175`
- **描述:** `api_config['base_url']` 直接被 `requests.post` 调用，没有白名单校验。`/api/list_models` 有白名单检查，但主分析流程没有复用。
- **复现:** 在 UI 选择 DeepSeek/OpenAI，将 base_url 改为 `http://169.254.169.254`，开始分析，后端会向其发送 `/v1/chat/completions` 请求。
- **影响:** 同 1.1，且因为请求体包含完整剧本，可导致敏感内容外泄到攻击者控制的地址。
- **修复建议:** 在 `call_ai()` 或 `analyze()` 入口统一调用 `ALLOWED_BASE_URLS` 校验；未配置白名单时默认只允许已知提供商域名。

---

### 1.3 🟠 中危：CORS 配置为 `*`，与注释“仅允许同源”矛盾

- **位置:** `app.py:106`
- **描述:** `Access-Control-Allow-Origin: *` 允许任意网站跨域调用 API。虽然认证依赖 API Key 而非 Cookie，但仍增大了钓鱼/CSRF 风险。
- **复现:** 任意第三方页面可通过 `fetch` 调用 `/api/analyze`。
- **影响:** 若用户浏览器中存有 localStorage API Key，配合 XSS 或诱导访问恶意页面，可批量消耗额度或窃取分析结果。
- **修复建议:** 改为读取 `Origin` 请求头并与白名单比对；无白名单时回退到请求同源地址，或完全移除 CORS 头。

---

### 1.4 🟠 中危：API Key 保存在浏览器 localStorage

- **位置:** `static/js/app.js:193, 1515, 1530`
- **描述:** DeepSeek/OpenAI 的 API Key 明文写入 `localStorage`，且页面加载时自动回填。
- **影响:** 任何 XSS 漏洞都能直接窃取 Key；浏览器插件、共享设备也可读取。
- **修复建议:** 不在客户端持久化密钥；提供“仅本次会话有效”的内存存储选项；对必须记忆的场景使用服务端加密会话或浏览器密码管理器集成。

---

### 1.5 🟠 中危：前端自定义 `sanitizeHTML` 可被绕过

- **位置:** `static/js/app.js:2003-2047`
- **描述:** 函数先 `textContent` 转义，再用正则 `&lt;(\/?)(\w+)([^&]*)&gt;` 恢复允许标签。该正则不处理实体编码、大小写混合、标签属性中的 `<`/`>` 等边界情况，且 `a[href]` 未校验协议。
- **影响:** 攻击者可通过构造特殊 payload 在前端注入 `<script>`、`<iframe>`、事件处理器或 `javascript:` 链接。
- **修复建议:** 使用 DOMPurify 或类似成熟库；若必须自研，先通过 DOMParser 解析，再遍历节点按白名单过滤。

---

### 1.6 🟠 中危：文件上传仅校验扩展名，不校验内容与 MIME

- **位置:** `app.py:572-582` 与 `services/file_parser.py`
- **描述:** 仅通过 `os.path.splitext` 判断扩展名；未读取文件 magic bytes；`ALLOWED_EXTS` 里的 MIME 映射也只做展示用途，未真正校验。
- **复现:** 将任意可执行文件重命名为 `.txt` 上传即可绕过。
- **影响:** 可导致解析器崩溃、内存异常；若后续处理逻辑被触发，可能引发命令注入或拒绝服务。
- **修复建议:** 使用 `python-magic` 或读取文件头校验真实类型；校验文件内容是否为空；限制单页/单文件最大字符数。

---

### 1.7 🟡 低危：/api/list_models 白名单默认未启用且校验点单一

- **位置:** `app.py:421-428`
- **描述:** `config.ALLOWED_BASE_URLS` 默认是 `None`，因此默认不生效；校验只比较 `parsed.netloc`，不限制 scheme、path 或端口。
- **影响:** 默认部署下任何 base_url 都可连接；即便启用白名单，仍可能通过 `netloc` 相同但 path 不同的方式绕过。
- **修复建议:** 默认启用白名单且包含已知提供商；校验完整 URL 前缀（scheme+netloc+path）。

---

### 1.8 🟡 低危：生成的报告文件名/路径可能泄露原始文件名片段

- **位置:** `app.py:608-613`
- **描述:** `script_name` 仅替换 `[\\/:*?"<>|]` 和 `\x00`，并 lstrip `.-`，不删除 `()` 等特殊字符。虽然 `safe_join` 阻止了路径穿越，但输出目录名保留了用户输入的变体。
- **复现:** 上传 `<script>alert(1)</script>.txt` 会生成 `outputs/script_alert(1)__script/`。
- **影响:** 信息泄露、目录枚举时产生奇怪名称；在部分文件系统/Shell 下可能引发命令注入（macOS 不会，但打包到 Windows 需谨慎）。
- **修复建议:** 使用更严格的 slug 化函数，仅保留字母、数字、下划线、中文字符。

---

## 2. 代码质量 findings

### 2.1 🟠 中危：app.py 体积过大，职责混杂

- **位置:** `app.py`（1845 行）
- **描述:** 包含路由、进度管理、临时知识库、输出路径、AI 重试、批量处理、资产核对、预处理等逻辑。单文件难以维护、审查和测试。
- **影响:** 容易引入回归；新开发者上手成本高；静态审计困难。
- **修复建议:** 按职责拆分为 `routes/`、`progress/`、`knowledge/`、`batch/` 等模块；每个路由函数控制在 50 行以内。

---

### 2.2 🟠 中危：大量 `except Exception` 吞掉错误细节

- **位置:** `app.py` 多处（如 263, 270, 384, 491, 516, 812, 877, 942），`services/ai_service.py:217`
- **描述:** 顶层函数频繁使用 `except Exception` 捕获所有异常，仅通过 `str(e)` 返回前端，丢失堆栈；部分异常被静默吞掉后继续流程。
- **影响:** 排查困难；潜在错误被掩盖；用户体验“卡死但无明确错误”。
- **修复建议:** 区分可恢复异常与致命异常；记录 `exc_info=True`；对预期异常返回明确错误码，对未预期异常返回通用提示并在日志中记录完整 traceback。

---

### 2.3 🟡 低危：`services/file_parser.py:57-59` 重复 `except ImportError`

- **描述:** 同一个 `except ImportError` 写了两次，第二次永远不会执行。
- **修复建议:** 删除重复代码。

---

### 2.4 🟡 低危：测试依赖未写入 requirements.txt

- **位置:** `requirements.txt`
- **描述:** 项目有 `tests/` 目录且使用 `pytest`，但 `requirements.txt` 未包含 `pytest`。
- **影响:** 新环境无法直接运行测试；CI 容易遗漏。
- **修复建议:** 新增 `pytest>=7.0`；建议添加 `requirements-dev.txt` 或 `pyproject.toml` 分组。

---

### 2.5 🟡 低危：版本号不一致

- **位置:** `config.py` 写 v2.52，`static/index.html` 写 v2.55
- **影响:** 用户困惑；缓存控制参数 `?v=2.55` 与实际版本不匹配。
- **修复建议:** 统一从 `config.py` 读取版本号并注入模板/静态文件。

---

### 2.6 🟡 低危：前端存在多处 `innerHTML` 注入固定 HTML

- **位置:** `static/js/app.js:1167, 1194, 1713, 1763, 1807, 2109`
- **描述:** 这些 innerHTML 用于构建 overlay/dialog，内容是硬编码字符串，未引入用户输入。风险较低，但建议统一使用 DOM 构建函数以便维护。
- **修复建议:** 抽取 `createDialog()` 辅助函数，避免直接写 innerHTML。

---

## 3. AI 流程 findings

### 3.1 🟠 中危：Prompt 注入风险无法根除

- **描述:** 用户上传的剧本内容直接拼接到 user prompt 中，AI 可能把剧本里的指令当作系统指令执行。
- **影响:** 输出被污染、知识库被绕过、生成有害内容。
- **修复建议:** 这是行业难题，可缓解：在 system prompt 中明确分隔用户内容；使用 XML/JSON 边界标记；对输出做后校验；考虑区分“系统指令”与“待分析文本”。

---

### 3.2 🟡 低危：JSON 修复逻辑复杂且依赖启发式

- **位置:** `extractors/base.py`
- **描述:** `_safe_json_parse_with_fallback` 使用多层正则和截断补齐，逻辑复杂，容易在极端情况下产生错误结构。
- **影响:** 可能把非 JSON 内容“修复”成可解析但语义错误的数据；维护困难。
- **修复建议:** 增加结构化日志记录每次 fallback 的使用情况；考虑使用 Pydantic 校验解析后的结构；对关键字段缺失报错而非静默填充。

---

### 3.3 🟡 低危：模型参数未做上下界校验

- **位置:** `app.py:626-630`、`services/ai_service.py:49, 63`
- **描述:** `max_tokens`、`temperature`、`top_p` 等从表单直接传入，未校验范围。`max_tokens` 默认 200000，用户可设置极大值导致 Ollama 异常或超长等待。
- **修复建议:** 增加参数校验装饰器/函数，限制 `max_tokens` 不超过模型上下文、`temperature` 在 0-2 之间。

---

## 4. 性能与稳定性 findings

### 4.1 🟠 中危：缺少请求取消机制

- **描述:** SSE 分析开始后，客户端刷新/关闭浏览器，后端仍会继续完成所有 AI 调用和报告生成。
- **影响:** 浪费计算资源；用户重新上传时可能产生并发请求。
- **修复建议:** 在 SSE generator 中定期检查客户端连接（`request.is_json` 不可用，但可通过检查连接是否关闭实现）；提供 `/api/cancel/<script_name>` 接口。

---

### 4.2 🟡 低危：AI 超时 120s 固定，长剧本无进度细分

- **位置:** `services/ai_service.py:174`
- **描述:** 单次 AI 调用 timeout=120s，对于大上下文模型和复杂 prompt 可能合理，但失败时前端只能看到“重试中”。
- **修复建议:** 按步骤/批次暴露更细粒度的 SSE 进度；超时按模型动态调整。

---

### 4.3 🟡 低危：大文件解析无字符上限

- **位置:** `services/file_parser.py`
- **描述:** 50MB 文件可包含数百万字符，全部读入内存并传给 AI。
- **修复建议:** 在解析阶段增加字符数上限预警；对超大文件先提示用户确认。

---

## 5. 前端 UX findings

### 5.1 🟡 低危：API Key 输入框默认明文显示

- **位置:** `static/index.html`
- **描述:** 输入框类型为 `text`，Key 在屏幕可见。
- **修复建议:** 改为 `type="password"` 并提供显示/隐藏切换。

---

### 5.2 🟡 低危：错误提示偶尔暴露后端路径或原始 AI 返回

- **位置:** `app.py:799, 851, 918` 等
- **描述:** 错误信息包含 `AI原始返回前400字` 或文件路径片段。
- **修复建议:** 生产环境关闭原始返回展示；仅记录到日志。

---

## 6. 测试结果

| 测试项 | 结果 | 备注 |
|--------|------|------|
| 启动 Flask + Ollama `ornith:latest` | ✅ 通过 | 使用端口 8080 避免与 AirTunes(5000) 冲突 |
| `/api/config` | ✅ 通过 | 返回 providers |
| `/api/check_connection` Ollama | ✅ 通过 | 连接成功 |
| `/api/check_connection` SSRF 内网 | ❌ 可利用 | 未做白名单校验 |
| `/api/list_models` SSRF 内网 | ❌ 可利用 | 默认白名单未启用 |
| `/api/preview` 路径穿越 | ✅ 阻断 | 404 |
| `/api/download` 路径穿越 | ✅ 阻断 | 404 |
| 上传文件名 `<script>alert(1)</script>.txt` | ⚠️ 部分过滤 | 目录名保留括号 |
| 四步分析（短英文剧本） | ⚠️ 模型返回空 | `ornith:latest` 对角色/道具/场景返回空数组，应用降级继续 |
| `tests/test_json_parser.py` | ✅ 通过 | 5/5 |
| `venv/bin/python3 -m pytest tests/` | ❌ 未运行 | `pytest` 未安装 |

---

## 7. 优先修复清单

### P0（立即修复）
1. 在 `call_ai()` 和 `/api/check_connection` 统一加入 `ALLOWED_BASE_URLS` 校验，默认只允许已知 AI 提供商域名。
2. 将 `Access-Control-Allow-Origin: *` 改为同源或白名单模式。

### P1（本周修复）
3. 不在 `localStorage` 中持久化 API Key，输入框改为密码类型。
4. 文件上传增加内容类型/文件头校验，防止扩展名欺骗。
5. 对 `api_config` 参数做范围校验（`max_tokens`、`temperature` 等）。

### P2（下月修复）
6. 拆分 `app.py`，将进度、知识库、批量处理、路由分别抽离。
7. 统一异常处理策略，记录完整 traceback，避免吞异常。
8. 引入 DOMPurify 替换自定义 `sanitizeHTML`。
9. 将 `pytest` 写入依赖，补充 `/api/analyze` 的集成测试覆盖。
10. 统一版本号来源，修复 `v2.52` vs `v2.55` 不一致。

---

## 8. 附录

### 8.1 审计命令参考

```bash
# 启动应用（注意 macOS 5000 端口被 AirTunes 占用）
PORT=8080 OLLAMA_BASE_URL=http://localhost:11434 \
  OLLAMA_MODEL=ornith:latest BIND_HOST=127.0.0.1 \
  venv/bin/python3 app.py

# SSRF 探针
curl -X POST http://127.0.0.1:8080/api/check_connection \
  -H "Content-Type: application/json" \
  -d '{"provider":"deepseek","base_url":"http://169.254.169.254","api_key":"x"}'

# 路径穿越探针
curl http://127.0.0.1:8080/api/preview/..%2f..%2fetc%2fpasswd
```

### 8.2 模型说明

本次运行时测试使用 Ollama `ornith:latest`（9B，Q4_K_M，上下文 262K）。该模型对短英文剧本的角色/道具/场景提取返回空数组，但应用未崩溃，继续降级生成报告。这属于模型能力问题，不属于应用缺陷；但应用应更明确地向用户提示“本地模型能力不足，建议使用 DeepSeek V4”。

