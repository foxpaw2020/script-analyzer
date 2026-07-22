# 修复审计发现（P0/P1）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复审计报告中的 P0/P1 问题：SSRF 漏洞、CORS 过宽、API Key 本地存储、文件上传内容校验缺失、AI 参数范围校验缺失。

**Architecture:** 引入统一的 `validate_api_base_url()` 工具函数，在 `call_ai()` 和 `/api/check_connection` 入口调用；收紧 CORS 为同源；前端不再持久化 API Key 到 localStorage；上传文件时通过 magic bytes 验证真实类型；新增 `api_config` 参数校验。

**Tech Stack:** Python 3.9 / Flask / Jinja2 / Vanilla JS；新增依赖 `python-magic>=0.4`（可选，若不可用则退到文件头读取）。

## Global Constraints
- 保持 Python 3.9 兼容。
- 不引入重型前端框架。
- 所有修改不破坏现有 Ollama/DeepSeek/OpenAI 调用路径。
- 测试使用 `pytest`（将加入 dev 依赖）。
- 不修改知识库 JSON 或提示词内容。

---

## Task 1: 统一 base_url 白名单校验，修复 SSRF

**Files:**
- Create: `utils/url.py`
- Modify: `services/ai_service.py`  
- Modify: `app.py:502-538` (`check_connection`)  
- Modify: `app.py:421-447` (`list_models` 的校验逻辑，统一引用新工具)
- Test: `tests/test_security.py`

**Interfaces:**
- Consumes: `config.ALLOWED_BASE_URLS`, `config.AI_PROVIDERS`
- Produces: `validate_api_base_url(base_url, provider_name=None) -> None`（不通过则抛 `ValueError`）

- [ ] **Step 1: Write the failing test**

```python
def test_validate_api_base_url_rejects_internal():
    from utils.url import validate_api_base_url
    with pytest.raises(ValueError):
        validate_api_base_url("http://169.254.169.254")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_security.py::test_validate_api_base_url_rejects_internal -v`
Expected: FAIL with "cannot import name 'validate_api_base_url'"

- [ ] **Step 3: Implement `validate_api_base_url()` in `utils/url.py`**

```python
from urllib.parse import urlparse
import config

KNOWN_PROVIDER_HOSTS = {
    "ollama": {"localhost", "127.0.0.1"},
    "deepseek": {"api.deepseek.com"},
    "openai": {"api.openai.com"},
}


def validate_api_base_url(base_url, provider_name=None):
    """Validate user-supplied AI base URL to prevent SSRF.

    Raises:
        ValueError: if the URL is not allowed.
    """
    if not base_url:
        return

    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"不支持的 URL scheme: {parsed.scheme}")

    netloc = parsed.netloc.lower()

    # 1. 显式白名单（最高优先级）
    if config.ALLOWED_BASE_URLS:
        allowed = {h.lower() for h in config.ALLOWED_BASE_URLS}
        if netloc in allowed:
            return
        raise ValueError(f"不允许的 API 地址: {base_url}")

    # 2. 默认已知提供商白名单
    if provider_name in KNOWN_PROVIDER_HOSTS:
        if netloc in {h.lower() for h in KNOWN_PROVIDER_HOSTS[provider_name]}:
            return

    # 3. Ollama 本地默认允许
    if provider_name == "ollama" and netloc in {"localhost:11434", "127.0.0.1:11434"}:
        return

    raise ValueError(f"不允许的 API 地址: {base_url}")
```

- [ ] **Step 4: Call validator in `call_ai()`**

Modify `services/ai_service.py` after `base_url` is resolved:

```python
from utils.url import validate_api_base_url

# ... inside call_ai() after base_url is determined
if base_url:
    validate_api_base_url(base_url, provider_name)
```

- [ ] **Step 5: Call validator in `/api/check_connection`**

Replace `check_connection()` body with SSRF-safe version. For `provider == 'ollama'` and `provider == 'deepseek'`/`'openai'`, validate `base_url` before calling `requests`.

- [ ] **Step 6: Refactor `/api/list_models` to use the same validator**

Remove inline `urlparse` check; call `validate_api_base_url(base_url, 'deepseek')`.

- [ ] **Step 7: Run tests**

Run: `python -m pytest tests/test_security.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add utils/url.py services/ai_service.py app.py tests/test_security.py
git commit -m "security: add base_url whitelist to prevent SSRF"
```

---

## Task 2: 收紧 CORS 为同源/白名单

**Files:**
- Modify: `app.py:99-113` (`add_security_headers`)
- Test: `tests/test_security.py`

**Interfaces:**
- Consumes: `request.headers.get('Origin')`, `config.ALLOWED_ORIGINS`（可选）
- Produces: 动态 `Access-Control-Allow-Origin` 响应头

- [ ] **Step 1: Write the failing test**

```python
def test_cors_blocks_unknown_origin(client):
    resp = client.get('/', headers={'Origin': 'https://evil.com'})
    assert resp.headers.get('Access-Control-Allow-Origin') != 'https://evil.com'
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL with `Access-Control-Allow-Origin` equals `*`

- [ ] **Step 3: Implement same-origin CORS**

Modify `add_security_headers`:

```python
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Cache-Control'] = 'no-store'

    origin = request.headers.get('Origin')
    if origin:
        allowed = config.ALLOWED_ORIGINS if hasattr(config, 'ALLOWED_ORIGINS') and config.ALLOWED_ORIGINS else [request.host_url.rstrip('/')]
        if origin in allowed:
            response.headers['Access-Control-Allow-Origin'] = origin
        # 否则不设置 CORS 头
    return response
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_security.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app.py config.py tests/test_security.py
git commit -m "security: restrict CORS to same-origin"
```

---

## Task 3: 前端不再持久化 API Key

**Files:**
- Modify: `static/index.html`（输入框类型）
- Modify: `static/js/app.js`（localStorage 读写 API Key 的逻辑）
- Test: 手动测试（无需单元测试，因为纯前端行为）

**Interfaces:**
- Consumes: 用户输入
- Produces: 页面刷新后 API Key 输入框为空

- [ ] **Step 1: 将输入框改为 password 类型**

In `static/index.html`, find API Key input and add `type="password"` with a toggle button.

- [ ] **Step 2: 移除 localStorage 的 API Key 读写**

Remove lines:
- `localStorage.setItem('ds_api_key', apiKey)`
- `localStorage.setItem('oa_api_key', apiKey)`
- `localStorage.getItem('ds_api_key')` / `localStorage.getItem('oa_api_key')` usage

Keep `ds_base_url`, `oa_base_url`, `ollama_base_url`, `ollama_model` as non敏感配置可保留。

- [ ] **Step 3: 添加显示/隐藏切换**

Add small JS helper to toggle `type` between `password` and `text`.

- [ ] **Step 4: 手动测试**

Open the page, enter an API Key, refresh, confirm the field is empty.

- [ ] **Step 5: Commit**

```bash
git add static/index.html static/js/app.js
git commit -m "security: stop persisting API keys in localStorage"
```

---

## Task 4: 文件上传增加内容校验

**Files:**
- Modify: `services/file_parser.py`（新增 `validate_file_type`）
- Modify: `app.py:572-582`（调用校验）
- Modify: `requirements.txt`（添加 `python-magic>=0.4; sys_platform != 'win32'`）
- Test: `tests/test_security.py`

**Interfaces:**
- Consumes: 上传文件 bytes
- Produces: `True/False` 或抛出异常

- [ ] **Step 1: Write the failing test**

```python
def test_rejects_binary_renamed_to_txt(tmp_path):
    from services.file_parser import validate_file_type
    p = tmp_path / "fake.txt"
    p.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert validate_file_type(str(p)) is False
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL with "name 'validate_file_type' is not defined"

- [ ] **Step 3: Implement content validation**

Add to `services/file_parser.py`:

```python
FILE_MAGIC = {
    b'%PDF': '.pdf',
    b'PK\x03\x04': '.docx',  # also modern .doc
    b'\x89PNG\r\n\x1a\n': '.png',
}


def validate_file_type(file_path):
    """通过文件头校验扩展名是否匹配真实类型。"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in ('.pdf', '.docx', '.doc', '.txt', '.md', '.markdown'):
        return False

    try:
        with open(file_path, 'rb') as f:
            header = f.read(8)
    except OSError:
        return False

    if ext in ('.txt', '.md', '.markdown'):
        # 文本文件：尝试 UTF-8 解码，避免二进制可执行文件
        try:
            header.decode('utf-8', errors='strict')
            return True
        except UnicodeDecodeError:
            return False

    for magic, real_ext in FILE_MAGIC.items():
        if header.startswith(magic):
            return ext == real_ext

    # .doc 旧格式无法简单识别，允许通过
    return ext == '.doc'
```

- [ ] **Step 4: Call validator in upload flow**

In `app.py` after `file.save(file_path)`:

```python
if not validate_file_type(file_path):
    os.remove(file_path)
    yield json_sse("error", {"message": "文件内容与实际格式不符，请检查文件"})
    return
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_security.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add services/file_parser.py app.py requirements.txt tests/test_security.py
git commit -m "security: validate uploaded file content by magic bytes"
```

---

## Task 5: 校验 AI 参数范围

**Files:**
- Create: `utils/validation.py`
- Modify: `app.py`（分析入口调用校验）
- Modify: `services/ai_service.py`（使用已校验值）
- Test: `tests/test_validation.py`

**Interfaces:**
- Consumes: raw `api_config` dict
- Produces: sanitized `api_config` dict

- [ ] **Step 1: Write the failing test**

```python
def test_sanitize_api_config_clamps_temperature():
    from utils.validation import sanitize_api_config
    cfg = {"temperature": "99", "max_tokens": "1000000"}
    out = sanitize_api_config(cfg)
    assert out["temperature"] == 2.0
    assert out["max_tokens"] <= 100000
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL with import error

- [ ] **Step 3: Implement `sanitize_api_config`**

```python
from utils.text import safe_float, safe_int
import config


def sanitize_api_config(api_config):
    out = dict(api_config)

    temp = safe_float(out.get("temperature"), 0.7)
    out["temperature"] = max(0.0, min(2.0, temp))

    top_p = out.get("top_p")
    if top_p is not None and str(top_p).strip():
        top_p = safe_float(top_p, None)
        if top_p is not None:
            out["top_p"] = max(0.0, min(1.0, top_p))

    max_tok = safe_int(out.get("max_tokens"), config.MAX_TOKENS)
    out["max_tokens"] = min(max_tok, 100000)  # 100K 上限

    freq = out.get("frequency_penalty")
    if freq is not None and str(freq).strip():
        freq = safe_float(freq, None)
        if freq is not None:
            out["frequency_penalty"] = max(-2.0, min(2.0, freq))

    pres = out.get("presence_penalty")
    if pres is not None and str(pres).strip():
        pres = safe_float(pres, None)
        if pres is not None:
            out["presence_penalty"] = max(-2.0, min(2.0, pres))

    return out
```

- [ ] **Step 4: Call in `app.py` analyze() and preprocess()**

After building `api_config`, sanitize it before passing to `call_ai` or `_call_ai_retry`.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_validation.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add utils/validation.py app.py services/ai_service.py tests/test_validation.py
git commit -m "security: validate and clamp AI API parameters"
```

---

## Task 6: 补充 dev 依赖并运行全量测试

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add pytest**

Append to `requirements.txt`:

```
pytest>=7.0
```

- [ ] **Step 2: Install and run tests**

```bash
venv/bin/pip install pytest
venv/bin/python -m pytest tests/ -v
```

Expected: all new tests pass; existing tests still pass.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add pytest to requirements"
```

---

## Self-Review

- **Spec coverage:** 审计报告中的 P0/P1 全部覆盖（SSRF、CORS、Key 存储、上传校验、参数校验）。
- **Placeholder scan:** 无 TBD/TODO；所有步骤包含代码与命令。
- **Type consistency:** `validate_api_base_url` 和 `sanitize_api_config` 签名在各任务中一致。
