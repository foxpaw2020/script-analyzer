# 剧本拆解大师 — 全面应用审计方案

**Date:** 2026-07-21  
**Version:** v2.52  
**Scope:** Full application audit (static + local runtime + red-team probes)  
**Runtime AI model:** Ollama `ornith:latest`

---

## 1. Objective

Comprehensively audit the `script-analyzer` application to identify security, code-quality, performance, AI-pipeline, and frontend UX issues. Produce a prioritized findings report with reproduction steps and remediation guidance.

## 2. Boundaries

### In scope
- Flask backend: `app.py`, `config.py`, `extractors/`, `services/`, `reports/`, `utils/`
- Frontend: `static/index.html`, `static/js/app.js`, `static/css/style.css`, `templates/report.html`
- Assets & build artifacts: `app.spec`, `start_app.sh`, `run_prod.sh`, `gunicorn.conf.py`
- Knowledge base & prompts: `knowledge_base/*.json`
- Local runtime behavior using Ollama `ornith:latest`

### Out of scope
- Security or correctness of third-party models (DeepSeek, OpenAI, Ollama itself)
- macOS DMG notarization / code-signing validation
- Network-level attacks against a deployed instance (all probes are local-only)
- Long-term operational monitoring (logs, metrics, alerting infrastructure)

## 3. Methodology

| Layer | Technique | Goal |
|-------|-----------|------|
| Static analysis | Read code, configs, git history, README | Find logic bugs, misconfigurations, hardcoded values, unsafe defaults |
| Local runtime test | Start Flask app on a non-production port with Ollama | Validate happy-path upload → parse → AI → report flow |
| Red-team probes | Hand-crafted malicious filenames, payloads, oversized/empty files, malformed documents | Confirm exploitability of suspected vulnerabilities |
| Code-quality review | Check for duplication, error handling, test coverage, large files | Identify maintainability and reliability debt |

## 4. Audit Dimensions

### 4.1 Security
- **File upload**: extension whitelist, content-type validation, size limits, path traversal in filenames, stored-file permissions
- **SSRF**: URL validation for custom AI base URLs, whitelist behavior, `ALLOWED_BASE_URLS`
- **Prompt injection**: ability to override system instructions via user-supplied script content
- **Secrets**: `SECRET_KEY`, `.secret_key`, `.env`, API keys in client-side JS or logs
- **CSRF / CORS / session**: Flask session configuration, cookie flags, CORS headers
- **Output files**: whether generated reports leak sensitive paths or allow XSS via user content

### 4.2 Code Quality & Maintainability
- Module boundaries and single-responsibility violations
- Duplicated logic across extractors and reports
- Exception handling (bare except, swallowed errors, missing rollback)
- Logging practices (sensitive data leakage, insufficient context)
- Configuration drift vs. environment variables
- Test coverage and test quality

### 4.3 Performance & Stability
- Behavior with files near or above `MAX_CONTENT_LENGTH` (50 MB)
- Memory usage during large script parsing and report generation
- AI call timeout, retry, and backoff behavior
- SSE connection lifecycle and error propagation to the frontend
- Concurrent upload handling
- Gunicorn / gevent configuration suitability

### 4.4 AI Pipeline & Prompts
- Prompt clarity and robustness for each extraction step
- JSON parsing and repair reliability (`extractors/base.py`)
- Model switching and provider fallback behavior
- Token limit handling (`MAX_TOKENS`, `CONTEXT_LENGTH`)
- Error handling when AI returns malformed or empty output
- Knowledge base JSON loading and validation

### 4.5 Frontend UX
- Upload state feedback and progress indication
- Error message clarity for network/AI failures
- Form validation before submission
- Mobile responsiveness
- Browser console errors

## 5. Test Inputs

| # | Input | Purpose |
|---|-------|---------|
| 1 | Valid short English screenplay | Happy-path baseline |
| 2 | Empty `.txt` file | Empty-input handling |
| 3 | File > 50 MB | Size limit enforcement |
| 4 | Filename `../../etc/passwd.txt` | Path traversal in upload |
| 5 | Filename `<script>alert(1)</script>.txt` | XSS/reflection in filename handling |
| 6 | Malformed `.docx` / `.pdf` / `.md` | Parser error handling |
| 7 | Script containing prompt-injection payloads | AI instruction override risk |
| 8 | Script with no extractable characters/scenes | Empty-result handling |
| 9 | Binary file renamed to `.txt` | Content-type/extension mismatch |
| 10 | Concurrent upload of two large files | Concurrency and stability |

## 6. Local Runtime Setup

1. Ensure Ollama is installed and running.
2. Pull `ornith:latest`:
   ```bash
   ollama pull ornith:latest
   ```
3. Start the application on a non-default port:
   ```bash
   cd script-analyzer
   source venv/bin/activate
   PORT=5050 OLLAMA_BASE_URL=http://localhost:11434 \
     OLLAMA_MODEL=ornith:latest python3 app.py
   ```
4. Open `http://127.0.0.1:5050` and perform the runtime tests.

> **Note:** Because `ornith:latest` may be smaller/less capable than DeepSeek V4, some AI steps may fail or produce low-quality JSON. The audit will distinguish between “model returned bad output” and “application failed to handle the output gracefully.”

## 7. Deliverables

A single Markdown report at:

```
docs/superpowers/audits/2026-07-21-comprehensive-audit.md
```

Report structure:

1. **Executive Summary** — top risks, quick wins, overall score
2. **Findings by Dimension** — security, quality, performance, AI, frontend
3. **Each Finding Contains:**
   - Severity (Critical / High / Medium / Low)
   - Location (file + line range where possible)
   - Description
   - Reproduction steps
   - Impact
   - Recommended fix
4. **Prioritized Action Plan** — what to fix first, grouped by effort/risk
5. **Appendix** — test data, commands, model notes

## 8. Success Criteria

- Every critical/high finding has a clear reproduction path.
- No new code is written during the audit phase; only findings and recommendations are produced.
- The report is actionable: each recommendation can be turned into a concrete code change.
- Runtime tests are documented with the actual model used (`ornith:latest`).

## 9. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| `ornith:latest` is not available or fails to load | Verify with `ollama list`; fallback to `qwen2.5:7b` if needed, documenting the substitution |
| Local model too weak to complete extraction steps | Test application resilience (error handling, JSON repair) rather than output quality |
| Audit generates large output files | Clean up `outputs/audit-test-*` directories after testing |
| Accidental external API calls | Block requests to `api.deepseek.com`, `api.openai.com`, and non-local URLs via firewall or env config |

