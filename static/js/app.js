/**
 * 剧本拆解大师 v2.49 - 前端主逻辑
 */

//  (C) foxpaw

(function() {
    'use strict';

    // ============================================================
    // 状态管理
    // ============================================================
    const state = {
        scriptText: '',
        scriptName: '未命名剧本',
        fileName: '',
        fileSize: 0,
        fileType: '',
        isAnalyzing: false,
        results: {},
        downloadFiles: {},
        modelsFetched: false,
        fetchTimer: null,
        startTime: null,
        timerInterval: null,
        abortController: null,
        reader: null,
        breakdownStyle: 'female',
        charBioText: '',
        outlineText: '',
        charBioFile: null,
        outlineFile: null,
        materialsPreprocessed: false,
        preprocessSummary: null,
    };

    // ============================================================
    // DOM 引用
    // ============================================================
    const DOM = {};

    function initDOM() {
        DOM.uploadZone = document.getElementById('uploadZone');
        DOM.fileInput = document.getElementById('fileInput');
        DOM.fileInfo = document.getElementById('fileInfo');
        DOM.fileName = document.getElementById('fileName');
        DOM.fileSize = document.getElementById('fileSize');
        DOM.clearFileBtn = document.getElementById('clearFileBtn');
        DOM.textInput = document.getElementById('textInput');
        DOM.clearTextBtn = document.getElementById('clearTextBtn');
        DOM.charCount = document.getElementById('charCount');
        DOM.apiProvider = document.getElementById('apiProvider');
        DOM.apiKeyInput = document.getElementById('apiKeyInput');
        DOM.modelInput = document.getElementById('modelInput');
        DOM.modelSelect = document.getElementById('modelSelect');
        DOM.modelStatus = document.getElementById('modelStatus');
        DOM.baseUrlInput = document.getElementById('baseUrlInput');
        DOM.startBtn = document.getElementById('startBtn');
        DOM.stopBtn = document.getElementById('stopBtn');
        DOM.stopBtn2 = document.getElementById('stopBtn2');
        DOM.analysisTimer = document.getElementById('analysisTimer');
        DOM.modeAuto = document.getElementById('modeAuto');
        DOM.modeStep = document.getElementById('modeStep');
        DOM.autoBtns = document.getElementById('autoBtns');
        DOM.stepBtns = document.getElementById('stepBtns');
        DOM.stepCharBtn = document.getElementById('stepCharBtn');
        DOM.stepPropBtn = document.getElementById('stepPropBtn');
        DOM.stepSceneBtn = document.getElementById('stepSceneBtn');
        DOM.stepShotBtn = document.getElementById('stepShotBtn');
        DOM.progressPanel = document.getElementById('progressPanel');
        DOM.progressBar = document.getElementById('progressBar');
        DOM.resultsSection = document.getElementById('resultsSection');
        DOM.resultSummary = document.getElementById('resultSummary');
        DOM.resultDetail = document.getElementById('resultDetail');
        DOM.downloadHtmlBtn = document.getElementById('downloadHtmlBtn');
        DOM.downloadWordBtn = document.getElementById('downloadWordBtn');
        DOM.previewBtn = document.getElementById('previewBtn');
        DOM.outputPathHint = document.getElementById('outputPathHint');
        DOM.outputPathText = document.getElementById('outputPathText');
        DOM.openFolderBtn = document.getElementById('openFolderBtn');
        DOM.errorToast = document.getElementById('errorToast');
        DOM.errorMessage = document.getElementById('errorMessage');
        DOM.errorClose = document.getElementById('errorClose');
        // 高级参数
        DOM.paramsToggle = document.getElementById('paramsToggle');
        DOM.paramsBody = document.getElementById('paramsBody');
        DOM.paramTemperature = document.getElementById('paramTemperature');
        DOM.paramTopP = document.getElementById('paramTopP');
        DOM.paramFreqPenalty = document.getElementById('paramFreqPenalty');
        DOM.paramPresPenalty = document.getElementById('paramPresPenalty');
        DOM.paramMaxTokens = document.getElementById('paramMaxTokens');
        DOM.paramThinking = document.getElementById('paramThinking');
        DOM.valTemperature = document.getElementById('valTemperature');
        DOM.valTopP = document.getElementById('valTopP');
        DOM.valFreqPenalty = document.getElementById('valFreqPenalty');
        DOM.valPresPenalty = document.getElementById('valPresPenalty');
        DOM.valMaxTokens = document.getElementById('valMaxTokens');
        DOM.hintMaxTokens = document.getElementById('hintMaxTokens');
        DOM.testConnBtn = document.getElementById('testConnBtn');
        DOM.splitShotsBtn = document.getElementById('splitShotsBtn');
        // 新增：风格选择 & 辅助材料
        DOM.styleNormalRadio = document.querySelector('input[name="breakdownStyle"][value="normal"]');
        DOM.styleFemaleRadio = document.querySelector('input[name="breakdownStyle"][value="female"]');
        DOM.styleMaleRadio = document.querySelector('input[name="breakdownStyle"][value="male"]');
        DOM.charBioText = document.getElementById('charBioText');
        DOM.outlineText = document.getElementById('outlineText');
        DOM.charBioFileInput = document.getElementById('charBioFileInput');
        DOM.outlineFileInput = document.getElementById('outlineFileInput');
        DOM.uploadCharBioBtn = document.getElementById('uploadCharBioBtn');
        DOM.uploadOutlineBtn = document.getElementById('uploadOutlineBtn');
        DOM.clearCharBioBtn = document.getElementById('clearCharBioBtn');
        DOM.clearOutlineBtn = document.getElementById('clearOutlineBtn');
        DOM.clearCacheBtn = document.getElementById('clearCacheBtn');
        DOM.charBioFileInfo = document.getElementById('charBioFileInfo');
        DOM.outlineFileInfo = document.getElementById('outlineFileInfo');
        DOM.preprocessBtn = document.getElementById('preprocessBtn');
        DOM.preprocessHint = document.getElementById('preprocessHint');
        DOM.materialsStatus = document.getElementById('materialsStatus');
    }

    // ============================================================
    // 工具函数
    // ============================================================
    
    function formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    function showError(message, isSuccess) {
        DOM.errorMessage.textContent = message;
        DOM.errorToast.classList.add('show');
        if (isSuccess) {
            DOM.errorToast.classList.add('success');
            DOM.errorToast.querySelector('.error-title').textContent = '成功';
        } else {
            DOM.errorToast.classList.remove('success');
            DOM.errorToast.querySelector('.error-title').textContent = '错误';
        }
        setTimeout(function() {
            DOM.errorToast.classList.remove('show', 'success');
        }, 8000);
    }

    function hideError() {
        DOM.errorToast.classList.remove('show');
    }

    // ============================================================
    // 模型列表自动获取
    // ============================================================
    
    function fetchModels() {
        const provider = DOM.apiProvider.value;
        if (provider !== 'deepseek') return;
        
        const apiKey = DOM.apiKeyInput.value.trim();
        const baseUrl = DOM.baseUrlInput.value.trim() || 'https://api.deepseek.com';
        
        if (!apiKey) {
            // 无 key 时显示后备列表
            showFallbackModels();
            return;
        }
        
        DOM.modelStatus.style.display = 'inline';
        DOM.modelStatus.textContent = '正在获取模型列表...';
        DOM.modelSelect.disabled = true;
        
        fetch('/api/list_models', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: apiKey, base_url: baseUrl })
        })
        .then(r => r.json())
        .then(data => {
            DOM.modelSelect.disabled = false;
            DOM.modelsFetched = true;
            
            populateModelSelect(data.models);
            
            if (data.source === 'api') {
                DOM.modelStatus.textContent = '已加载 ' + data.models.length + ' 个模型';
                setTimeout(() => { DOM.modelStatus.style.display = 'none'; }, 3000);
            } else if (data.error) {
                DOM.modelStatus.textContent = 'API 不可用，使用默认列表';
                setTimeout(() => { DOM.modelStatus.style.display = 'none'; }, 4000);
            }
            
            // 保存 API Key 到 localStorage
            localStorage.setItem('ds_api_key', apiKey);
        })
        .catch(err => {
            DOM.modelSelect.disabled = false;
            DOM.modelStatus.textContent = '获取失败，使用默认列表';
            setTimeout(() => { DOM.modelStatus.style.display = 'none'; }, 4000);
            showFallbackModels();
        });
    }

    function populateModelSelect(models) {
        const currentVal = DOM.modelSelect.value;
        DOM.modelSelect.textContent = '';
        
        if (!models || models.length === 0) {
            showFallbackModels();
            return;
        }
        
        models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.id;
            
            // 友好的显示名
            let label = m.id;
            if (m.id.includes('v4-flash') && m.id.includes('thinking')) {
                label = 'DeepSeek V4 Flash (思考模式)';
            } else if (m.id.includes('v4-flash')) {
                label = 'DeepSeek V4 Flash (快速)';
            } else if (m.id.includes('v4-pro')) {
                label = 'DeepSeek V4 Pro (专业)';
            } else if (m.id === 'deepseek-chat') {
                label = 'DeepSeek Chat (即将弃用)';
            } else if (m.id === 'deepseek-reasoner') {
                label = 'DeepSeek Reasoner (即将弃用)';
            }
            
            opt.textContent = label + ' · ' + (m.ctx||m.context_length||'?') + ' 上下文';
            DOM.modelSelect.appendChild(opt);
        });
        
        // 模型切换后更新滑条上限
        updateParamRange();
        
        // 尝试恢复之前选中的值
        if ([...DOM.modelSelect.options].some(o => o.value === currentVal)) {
            DOM.modelSelect.value = currentVal;
        }
    }

    function showFallbackModels() {
        const fallback = [
            { id: 'deepseek-v4-flash', name: 'DeepSeek V4 Flash (快速)', ctx: '1M' },
            { id: 'deepseek-v4-flash-thinking', name: 'DeepSeek V4 Flash (思考模式)', ctx: '1M' },
            { id: 'deepseek-v4-pro', name: 'DeepSeek V4 Pro (专业)', ctx: '1M' },
            { id: 'deepseek-chat', name: 'DeepSeek Chat (即将弃用)', ctx: '64K' },
            { id: 'deepseek-reasoner', name: 'DeepSeek Reasoner (即将弃用)', ctx: '64K' },
        ];
        populateModelSelect(fallback);
    }

    // ============================================================
    // 步骤状态更新
    // ============================================================
    
    function setStepStatus(stepId, status, message) {
        const stepEl = document.getElementById(stepId);
        if (!stepEl) return;
        
        stepEl.classList.remove('pending', 'processing', 'complete', 'error');
        stepEl.classList.add(status);
        
        const icon = stepEl.querySelector('.step-icon');
        const msgEl = stepEl.querySelector('.step-message');
        const statusEl = stepEl.querySelector('.step-status');
        
        if (icon) icon.classList.remove('spinning');
        
        switch (status) {
            case 'pending':
                if (icon) icon.textContent = '○';
                if (statusEl) statusEl.textContent = '';
                if (msgEl) msgEl.textContent = message || '等待处理';
                break;
            case 'processing':
                if (icon) icon.textContent = '◉';
                if (icon) icon.classList.add('spinning');
                if (msgEl) msgEl.textContent = message || '处理中...';
                break;
            case 'complete':
                if (icon) icon.textContent = '✓';
                if (msgEl) msgEl.textContent = message || '完成';
                break;
            case 'error':
                if (icon) icon.textContent = '✕';
                if (msgEl) msgEl.textContent = message || '失败';
                break;
        }
    }

    function resetAllSteps() {
        ['stepChars', 'stepProps', 'stepScenes', 'stepShots', 'stepReport'].forEach(id => {
            setStepStatus(id, 'pending', '等待处理');
        });
        DOM.progressBar.style.width = '0%';
    }

    function updateProgressBar(progress) {
        DOM.progressBar.style.width = progress + '%';
    }

    // ============================================================
    // 结果展示
    // ============================================================
    
    function showResults(results) {
        // ===== 排序：按重要性 =====
        if (results.characters && results.characters.characters) {
            function roleRank(rt) {
                if (!rt) return 5;
                var t = String(rt);
                if (/主角|男主|女主/.test(t)) return 1;
                if (/反派|奸角|boss/i.test(t)) return 2;
                if (/配角/.test(t)) return 3;
                if (/龙套|群众|群演|路人|兵丁|侍卫|丫鬟|家丁/.test(t)) return 4;
                return 5;
            }
            results.characters.characters.sort(function(a,b) {
                return roleRank(a.role_type) - roleRank(b.role_type);
            });
        }
        if (results.props && results.props.props) {
            function propRank(imp) {
                if (!imp) return 5;
                var t = String(imp);
                if (/核心|A类|主线|主角/.test(t)) return 1;
                if (/重要|高|B类|主要|关键/.test(t)) return 2;
                if (/一般|中|C类|普通/.test(t)) return 3;
                if (/次要|低|D类|背景|龙套|装饰/.test(t)) return 4;
                return 5;
            }
            results.props.props.sort(function(a,b) {
                return propRank(a.importance) - propRank(b.importance);
            });
        }
        
        DOM.resultsSection.classList.add('show');
        
        // 统计卡片
        let statsHTML = '';
        if (results.characters && results.characters.characters) {
            statsHTML += `<div class="result-stat fade-in"><div class="stat-number">${results.characters.characters.length}</div><div class="stat-label">角色</div></div>`;
        }
        if (results.props && results.props.props) {
            statsHTML += `<div class="result-stat fade-in"><div class="stat-number">${results.props.props.length}</div><div class="stat-label">道具</div></div>`;
        }
        if (results.scenes && results.scenes.scenes) {
            // 场景排序：情绪越激烈越靠前
            (function() {
                var scRank = {};
                results.scenes.scenes.forEach(function(s) {
                    var et = String(s.emotion_tags||'').toLowerCase();
                    if (/高潮|决战|冲突|厮杀|危机|爆发|关键|死亡|灾难|暴怒|绝望|对峙/.test(et)) scRank[s.scene_number] = 1;
                    else if (/紧张|惊悚|追逐|打斗|激战|对抗|争夺/.test(et)) scRank[s.scene_number] = 2;
                    else if (/悲伤|恐惧|愤怒|痛苦|激烈争执/.test(et)) scRank[s.scene_number] = 3;
                    else scRank[s.scene_number] = 4;
                });
                results.scenes.scenes.sort(function(a,b) {
                    return (scRank[a.scene_number]||4) - (scRank[b.scene_number]||4);
                });
            })();
            statsHTML += `<div class="result-stat fade-in"><div class="stat-number">${results.scenes.scenes.length}</div><div class="stat-label">场景</div></div>`;
        }
        if (results.shots && results.shots.total_shots !== undefined) {
            statsHTML += `<div class="result-stat fade-in"><div class="stat-number">${results.shots.total_shots}</div><div class="stat-label">分镜</div></div>`;
        }
        DOM.resultSummary.innerHTML = sanitizeHTML(statsHTML);
        
        // 详情卡片区
        let detailHTML = '';
        
        // 角色卡片
        if (results.characters && results.characters.characters && results.characters.characters.length > 0) {
            detailHTML += '<div class="result-section-title">角色提取 (' + results.characters.characters.length + ')</div>';
            results.characters.characters.forEach(function(c, i) {
                var meta = [];
                if (c.role_type) meta.push(c.role_type);
                if (c.age_race) meta.push(c.age_race);
                if (c.episodes) meta.push(c.episodes);
                detailHTML += '<div class="result-card">';
                detailHTML += '<div class="result-card-header" onclick="var b=this.nextElementSibling;this.classList.toggle(\'open\');if(b)b.classList.toggle(\'show\')">';
                detailHTML += '<span class="rc-title">' + escapeHtml(c.name) + '</span>';
                detailHTML += '<span class="rc-meta">' + escapeHtml(meta.join(' | ')) + '</span>';
                detailHTML += '<span class="rc-arrow">▼</span></div>';
                detailHTML += '<div class="result-card-body">';
                if (c.description) detailHTML += '<div style="margin-bottom:6px;">' + escapeHtml(c.description) + '</div>';
                if (c.personality && c.personality.length) detailHTML += '<div style="color:#888;margin-bottom:6px;">性格：' + escapeHtml(c.personality.join('、')) + '</div>';
                if (c.info_card) detailHTML += '<div style="color:#FF9D00;margin-bottom:8px;">' + escapeHtml(c.info_card) + '</div>';
                if (c.prompt) {
                    var pid = 'char_p_' + i;
                    detailHTML += '<div class="prompt-preview" id="' + pid + '">' + escapeHtml(c.prompt) + '</div>';
                    detailHTML += '<button class="copy-btn-small" onclick="copyCardPrompt(\'' + pid + '\',this)">复制提示词</button>';
                }
                detailHTML += '</div></div>';
            });
        }
        
        // 道具卡片
        if (results.props && results.props.props && results.props.props.length > 0) {
            detailHTML += '<div class="result-section-title">道具提取 (' + results.props.props.length + ')</div>';
            results.props.props.forEach(function(p, i) {
                var meta = [p.category || '', (p.frequency||'?')+'场'];
                if (p.episodes) meta.push(p.episodes);
                detailHTML += '<div class="result-card">';
                detailHTML += '<div class="result-card-header" onclick="var b=this.nextElementSibling;this.classList.toggle(\'open\');if(b)b.classList.toggle(\'show\')">';
                detailHTML += '<span class="rc-title">' + escapeHtml(p.name) + '</span>';
                detailHTML += '<span class="rc-meta">' + escapeHtml(meta.join(' | ')) + '</span>';
                detailHTML += '<span class="rc-arrow">▼</span></div>';
                detailHTML += '<div class="result-card-body">';
                if (p.description) detailHTML += '<div style="margin-bottom:4px;">' + escapeHtml(p.description) + '</div>';
                if (p.text_signage) detailHTML += '<div style="color:#FF9D00;font-size:12px;margin-bottom:6px;">' + escapeHtml(p.text_signage) + '</div>';
                if (p.info_card) detailHTML += '<div style="color:#888;margin-bottom:6px;">' + escapeHtml(p.info_card) + '</div>';
                if (p.prompt) {
                    var pid = 'prop_p_' + i;
                    detailHTML += '<div class="prompt-preview" id="' + pid + '">' + escapeHtml(p.prompt) + '</div>';
                    detailHTML += '<button class="copy-btn-small" onclick="copyCardPrompt(\'' + pid + '\',this)">复制提示词</button>';
                }
                detailHTML += '</div></div>';
            });
        }
        
        // 场景卡片
        if (results.scenes && results.scenes.scenes && results.scenes.scenes.length > 0) {
            detailHTML += '<div class="result-section-title">场景拆解 (' + results.scenes.scenes.length + ')</div>';
            results.scenes.scenes.forEach(function(s, i) {
                var meta = [s.time||'', s.location||''];
                if (s.episode) meta.push(s.episode);
                detailHTML += '<div class="result-card">';
                detailHTML += '<div class="result-card-header" onclick="var b=this.nextElementSibling;this.classList.toggle(\'open\');if(b)b.classList.toggle(\'show\')">';
                detailHTML += '<span class="rc-title">' + (s.scene_number||'?') + '. ' + escapeHtml(s.title||'') + '</span>';
                detailHTML += '<span class="rc-meta">' + escapeHtml(meta.join(' | ')) + '</span>';
                detailHTML += '<span class="rc-arrow">▼</span></div>';
                detailHTML += '<div class="result-card-body">';
                if (s.synopsis) detailHTML += '<div style="margin-bottom:6px;">' + escapeHtml(s.synopsis) + '</div>';
                if (s.emotion_tags) detailHTML += '<div style="color:#888;font-size:12px;">情绪：' + escapeHtml(s.emotion_tags) + ' | 光影：' + escapeHtml(s.lighting_scheme||'') + '</div>';
                var wnid = 'wn_' + i, wgid = 'wg_' + i, tnid = 'tn_' + i, tgid = 'tg_' + i;
                if (s.wide_shot_nano) {
                    detailHTML += '<div style="color:#FF9D00;font-size:12px;margin-top:8px;">全景版 · Nano：</div>';
                    detailHTML += '<div class="prompt-preview" id="' + wnid + '">' + escapeHtml(s.wide_shot_nano) + '</div>';
                    detailHTML += '<button class="copy-btn-small" onclick="copyCardPrompt(\'' + wnid + '\',this)">复制</button>';
                }
                if (s.wide_shot_gpt) {
                    detailHTML += '<div style="color:#FF9D00;font-size:12px;margin-top:8px;">全景版 · GPT：</div>';
                    detailHTML += '<div class="prompt-preview" id="' + wgid + '">' + escapeHtml(s.wide_shot_gpt) + '</div>';
                    detailHTML += '<button class="copy-btn-small" onclick="copyCardPrompt(\'' + wgid + '\',this)">复制</button>';
                }
                if (s.topdown_nano) {
                    detailHTML += '<div style="color:#FF9D00;font-size:12px;margin-top:8px;">俯视图版 · Nano：</div>';
                    detailHTML += '<div class="prompt-preview" id="' + tnid + '">' + escapeHtml(s.topdown_nano) + '</div>';
                    detailHTML += '<button class="copy-btn-small" onclick="copyCardPrompt(\'' + tnid + '\',this)">复制</button>';
                }
                if (s.topdown_gpt) {
                    detailHTML += '<div style="color:#FF9D00;font-size:12px;margin-top:8px;">俯视图版 · GPT：</div>';
                    detailHTML += '<div class="prompt-preview" id="' + tgid + '">' + escapeHtml(s.topdown_gpt) + '</div>';
                    detailHTML += '<button class="copy-btn-small" onclick="copyCardPrompt(\'' + tgid + '\',this)">复制</button>';
                }
                detailHTML += '</div></div>';
            });
        }
        
        // 分镜卡片（简略）
        if (results.shots && results.shots.scenes && results.shots.scenes.length > 0) {
            detailHTML += '<div class="result-section-title">分镜拆解 (' + (results.shots.total_shots||0) + ')</div>';
            results.shots.scenes.forEach(function(s) {
                if (s.shots) {
                    s.shots.forEach(function(st) {
                        detailHTML += '<div class="result-card"><div class="result-card-header" style="cursor:default;">';
                        detailHTML += '<span class="rc-title">分镜 ' + escapeHtml(st.shot_id||st.shot_number||'') + '</span>';
                        detailHTML += '<span class="rc-meta">' + escapeHtml((st.total_duration||'')+'s | '+ (st.camera||'')) + '</span>';
                        detailHTML += '</div></div>';
                    });
                }
            });
        }
        
        DOM.resultDetail.innerHTML = sanitizeHTML(detailHTML) || '<div style="color:#666;">暂无数据</div>';
        DOM.resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // 全局复制函数（用于卡片中的复制按钮）
    window.copyCardPrompt = function(elementId, btn) {
        var el = document.getElementById(elementId);
        if (!el) return;
        var text = el.innerText || el.textContent;
        function done() {
            btn.textContent = '已复制!';
            setTimeout(function() { btn.textContent = '复制提示词'; }, 2000);
        }
        function fail() {
            btn.textContent = '复制失败';
            setTimeout(function() { btn.textContent = '复制提示词'; }, 1500);
        }
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).then(done).catch(fail);
        } else {
            var ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.left = '-9999px';
            document.body.appendChild(ta);
            ta.select();
            try { document.execCommand('copy'); ta.remove(); done(); }
            catch(e) { ta.remove(); fail(); }
        }
    };

    // ============================================================
    // 高级参数滑块
    // ============================================================
    
    function updateParamRange() {
        var modelId = (DOM.modelSelect.style.display !== 'none') ? DOM.modelSelect.value : DOM.modelInput.value;
        modelId = modelId || '';
        var maxCtx = 128000;
        if (modelId.includes('v4')) maxCtx = 384000;
        else if (modelId.includes('chat') || modelId.includes('reasoner')) maxCtx = 8192;
        else if (DOM.apiProvider.value === 'ollama') maxCtx = 65536;
        
        DOM.paramMaxTokens.max = maxCtx;
        DOM.hintMaxTokens.textContent = '（最大输出长度，当前模型上限 ' + (maxCtx/1000).toFixed(0) + 'K）';
        if (parseInt(DOM.paramMaxTokens.value) > maxCtx) {
            DOM.paramMaxTokens.value = maxCtx;
            DOM.valMaxTokens.textContent = maxCtx;
        }
        DOM.paramThinking.disabled = !modelId.includes('v4-flash');
        if (DOM.paramThinking.disabled) DOM.paramThinking.checked = false;
    }
    
    function bindParamSliders() {
        var pairs = [
            ['paramTemperature','valTemperature'],
            ['paramTopP','valTopP'],
            ['paramFreqPenalty','valFreqPenalty'],
            ['paramPresPenalty','valPresPenalty'],
            ['paramMaxTokens','valMaxTokens'],
        ];
        pairs.forEach(function(p) {
            var slider = DOM[p[0]], valEl = DOM[p[1]];
            if (slider && valEl) {
                slider.addEventListener('input', function() {
                    valEl.textContent = parseFloat(slider.value).toFixed(
                        slider.step.indexOf('.') > -1 ? slider.step.split('.')[1].length : 0
                    );
                });
            }
        });
        DOM.modelSelect.addEventListener('change', updateParamRange);
        DOM.apiProvider.addEventListener('change', updateParamRange);
        DOM.modelInput.addEventListener('input', updateParamRange);
        DOM.paramsToggle.addEventListener('click', function() {
            var open = DOM.paramsBody.style.display !== 'none';
            DOM.paramsBody.style.display = open ? 'none' : 'block';
            DOM.paramsToggle.classList.toggle('open', !open);
        });
        
        // 连接测试
        DOM.testConnBtn.addEventListener('click', testConnection);
        DOM.preprocessBtn.addEventListener('click', doPreprocess);
        DOM.clearCharBioBtn.addEventListener('click', clearCharBio);
        DOM.clearOutlineBtn.addEventListener('click', clearOutline);
        DOM.clearCacheBtn.addEventListener('click', clearCache);
        
        // 人物小传上传
        DOM.uploadCharBioBtn.addEventListener('click', function() {
            DOM.charBioFileInput.click();
        });
        DOM.charBioFileInput.addEventListener('change', function(e) {
            if (e.target.files.length > 0) {
                handleCharBioFile(e.target.files[0]);
            }
        });
        
        // 故事大纲上传
        DOM.uploadOutlineBtn.addEventListener('click', function() {
            DOM.outlineFileInput.click();
        });
        DOM.outlineFileInput.addEventListener('change', function(e) {
            if (e.target.files.length > 0) {
                handleOutlineFile(e.target.files[0]);
            }
        });
    }
    
    function testConnection() {
        var provider = DOM.apiProvider.value;
        var btn = DOM.testConnBtn;
        btn.disabled = true;
        btn.classList.add('loading');
        btn.classList.remove('success', 'error');
        
        var apiKey = DOM.apiKeyInput.value.trim();
        var baseUrl = DOM.baseUrlInput.value.trim() || (provider === 'ollama' ? 'http://localhost:11434' : 'https://api.deepseek.com');
        
        fetch('/api/check_connection', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ provider: provider, api_key: apiKey, base_url: baseUrl })
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                showError(data.message, true);
                btn.classList.add('success');
                if (provider === 'deepseek' && data.model_count > 0) fetchModels();
            } else {
                showError('连接失败: ' + data.message);
                btn.classList.add('error');
            }
        })
        .catch(function(err) {
            showError('连接失败: ' + (err.message || '网络错误'));
            btn.classList.add('error');
        })
        .finally(function() {
            btn.disabled = false;
            btn.classList.remove('loading');
            setTimeout(function() {
                btn.classList.remove('success', 'error');
            }, 3000);
        });
    }

    // ============================================================
    // 分析流程（自动模式 + 分步模式）
    // ============================================================
    
    const STEP_ORDER = ['characters', 'props', 'scenes', 'shots'];
    const STEP_LABELS = {characters:'角色提取',props:'道具提取',scenes:'场景拆解',shots:'分镜拆解'};
    
    function updateStepButtons() {
        // 分步模式下所有按钮均可点击
        DOM.stepCharBtn.disabled = false;
        DOM.stepPropBtn.disabled = false;
        DOM.stepSceneBtn.disabled = false;
        DOM.stepShotBtn.disabled = false;
        
        // 标记已完成的步骤
        [DOM.stepCharBtn, DOM.stepPropBtn, DOM.stepSceneBtn, DOM.stepShotBtn].forEach(function(b, i) {
            var step = STEP_ORDER[i];
            var done = !!(state.results[step] && Object.keys(state.results[step]).length > 0);
            if (done) b.classList.add('completed');
            else b.classList.remove('completed');
        });
    }
    
    function startAutoAnalysis() {
        if (state.isAnalyzing) return;
        var apiConfig = getApiConfig();
        if (!getScriptText()) { showError('请上传剧本文件或粘贴剧本内容'); return; }
        if (apiConfig.provider === 'deepseek' && !apiConfig.api_key) { showError('请填写 API Key'); return; }
        if (apiConfig.provider === 'openai' && !apiConfig.api_key) { showError('请填写 API Key'); return; }
        
        showScriptNameDialog(function() {
            var hasMaterials = !!(DOM.charBioText.value.trim() || DOM.outlineText.value.trim());
            if (!hasMaterials && !state.materialsPreprocessed) {
                showNoMaterialsDialog(function() {
                    DOM.noMaterialsDialog.style.display = 'none';
                    doStartAnalysis();
                });
                return;
            }
            doStartAnalysis();
        });
    }
    
    function doStartAnalysis() {
        state.isAnalyzing = true; state.results = {}; state.downloadFiles = {};
        // state.scriptName 已在对话框中被设置
        state.startTime = Date.now();
        state.abortController = new AbortController();
        DOM.startBtn.disabled = true; DOM.startBtn.textContent = '分析中...';
        DOM.startBtn.classList.add('btn-loading');
        DOM.stopBtn.style.display = ''; DOM.stopBtn2.style.display = '';
        DOM.analysisTimer.style.display = 'inline'; DOM.analysisTimer.textContent = '00:00';
        if (state.timerInterval) clearInterval(state.timerInterval);
        state.timerInterval = setInterval(updateTimer, 1000);
        DOM.progressPanel.classList.add('show'); DOM.resultsSection.classList.remove('show');
        resetAllSteps(); hideError();
        
        doFetch(null);
    }
    
    function startStepAnalysis(step) {
        if (state.isAnalyzing) return;
        var apiConfig = getApiConfig();
        if (!getScriptText()) { showError('请上传剧本文件或粘贴剧本内容'); return; }
        if (apiConfig.provider === 'deepseek' && !apiConfig.api_key) { showError('请填写 API Key'); return; }
        
        showScriptNameDialog(function() {
            var hasMaterials = !!(DOM.charBioText.value.trim() || DOM.outlineText.value.trim());
            if (!hasMaterials && !state.materialsPreprocessed) {
                showNoMaterialsDialog(function() {
                    DOM.noMaterialsDialog.style.display = 'none';
                    doStartStep(step);
                });
                return;
            }
            doStartStep(step);
        });
    }
    
    function doStartStep(step) {
        state.isAnalyzing = true;
        state.startTime = Date.now();
        state.abortController = new AbortController();
        // state.scriptName 已在对话框中被设置
        // 禁用所有分步按钮防止重复点击
        DOM.stepCharBtn.disabled = true; DOM.stepPropBtn.disabled = true;
        DOM.stepSceneBtn.disabled = true; DOM.stepShotBtn.disabled = true;
        DOM.stopBtn.style.display = ''; DOM.stopBtn2.style.display = '';
        DOM.analysisTimer.style.display = 'inline'; DOM.analysisTimer.textContent = '00:00';
        if (state.timerInterval) clearInterval(state.timerInterval);
        state.timerInterval = setInterval(updateTimer, 1000);
        DOM.progressPanel.classList.add('show');
        DOM.resultsSection.classList.remove('show');
        // 只重置目标步骤及之后
        var startReset = STEP_ORDER.indexOf(step);
        var stepIdMap = {characters:'stepChars',props:'stepProps',scenes:'stepScenes',shots:'stepShots'};
        STEP_ORDER.forEach(function(s, i) {
            if (i >= startReset) setStepStatus(stepIdMap[s], 'pending');
        });
        hideError();
        
        doFetch(step);
    }
    
    function doFetch(step) {
        var text = getScriptText();
        var apiConfig = getApiConfig();
        
        var formData = new FormData();
        var file = DOM.fileInput.files[0];
        if (file) { formData.append('file', file); }
        else { formData.append('text', text); formData.append('script_name', state.scriptName); }
        formData.append('api_config[provider]', apiConfig.provider);
        formData.append('api_config[api_key]', apiConfig.api_key);
        formData.append('api_config[model]', apiConfig.model);
        formData.append('api_config[base_url]', apiConfig.base_url);
        formData.append('api_config[temperature]', apiConfig.temperature);
        formData.append('api_config[top_p]', apiConfig.top_p);
        formData.append('api_config[frequency_penalty]', apiConfig.frequency_penalty);
        formData.append('api_config[presence_penalty]', apiConfig.presence_penalty);
        formData.append('api_config[max_tokens]', apiConfig.max_tokens);
        formData.append('api_config[thinking]', apiConfig.thinking ? '1' : '0');
        // 添加拆解风格
        formData.append('breakdown_style', state.breakdownStyle);
        // 添加人物小传和故事大纲（后端自动生成知识库用）
        formData.append('char_bio', DOM.charBioText.value);
        formData.append('story_outline', DOM.outlineText.value);
        if (step) {
            formData.append('step', step);
            formData.append('prior_results', JSON.stringify(state.results));
        }
        
        fetch('/api/analyze', { method: 'POST', body: formData, signal: state.abortController.signal })
        .then(handleStreamResponse)
        .catch(function(err) {
            console.error('Analysis error:', err);
            showError(err.message || '分析过程发生错误');
            endAnalysis();
        });
    }
    
    function handleStreamResponse(response) {
        if (!response.ok) {
            return response.text().then(function(t) {
                throw new Error('服务器错误 (' + response.status + '): ' + t.slice(0, 200));
            });
        }
        var reader = response.body.getReader();
        return readSSEStream(reader);
    }
    
    async function readSSEStream(reader) {
        state.reader = reader;
        var decoder = new TextDecoder();
        var buffer = '';
        try {
            while (true) {
                var result = await reader.read();
                if (result.done) break;
                buffer += decoder.decode(result.value, { stream: true });
                buffer = processSSEBuffer(buffer);
            }
            if (buffer.trim()) {
                buffer += decoder.decode();
                buffer = processSSEBuffer(buffer, true);
            }
        } finally {
            if (state.isAnalyzing) endAnalysis();
        }
    }
    
    function processSSEBuffer(buffer, isFlush) {
        var lines = buffer.split('\n');
        buffer = lines.pop() || '';
        var currentEvent = '', currentData = '';
        for (var i = 0; i < lines.length; i++) {
            var line = lines[i];
            if (line.startsWith('event: ')) { currentEvent = line.slice(7).trim(); }
            else if (line.startsWith('data: ')) { currentData = line.slice(6).trim(); }
            else if (line === '' || (isFlush && i === lines.length - 1)) {
                if (currentEvent && currentData) {
                    try { handleSSEEvent(currentEvent, JSON.parse(currentData)); }
                    catch(e) { console.warn('SSE error:', e); }
                }
                currentEvent = ''; currentData = '';
            }
        }
        return buffer;
    }
    
    function handleSSEEvent(event, data) {
        switch (event) {
            case 'info':
                break;
                
            case 'progress':
                handleProgress(data);
                break;
                
            case 'complete':
                state.results = data.results || {};
                state.downloadFiles = {
                    html: data.html_file,
                    word: data.word_file,
                    outputDir: data.output_dir,
                    scriptName: data.script_name
                };
                showResults(state.results);
                // 显示输出目录
                if (data.output_dir) {
                    DOM.outputPathText.textContent = data.output_dir;
                    DOM.outputPathHint.style.display = 'block';
                }
                endAnalysis();
                break;
                
            case 'error':
                showError(data.message || '未知错误');
                endAnalysis();
                break;
        }
    }

    function handleProgress(data) {
        const step = data.step;
        const status = data.status;
        const message = data.message;
        const stepData = data.data;
        
        const stepMap = {
            'characters': 'stepChars',
            'props': 'stepProps',
            'scenes': 'stepScenes',
            'shots': 'stepShots',
            'report': 'stepReport'
        };
        
        const stepId = stepMap[step];
        if (stepId) {
            setStepStatus(stepId, status, message);
            if (status === 'complete' && stepData) {
                state.results[step] = stepData;
                updateStepButtons();
            }
        }
        
        const stepOrder = ['characters', 'props', 'scenes', 'shots', 'report'];
        const currentIndex = stepOrder.indexOf(step);
        let progress = 0;
        
        if (status === 'complete') {
            progress = ((currentIndex + 1) / stepOrder.length) * 100;
        } else if (status === 'processing') {
            progress = (currentIndex / stepOrder.length) * 100 + 5;
        } else if (status === 'error') {
            progress = (currentIndex / stepOrder.length) * 100;
        }
        
        updateProgressBar(Math.min(progress, 100));
    }

    function endAnalysis() {
        state.isAnalyzing = false;
        DOM.startBtn.disabled = false;
        DOM.startBtn.textContent = '开始分析';
        DOM.startBtn.classList.remove('btn-loading');
        DOM.stopBtn.style.display = 'none';
        DOM.stopBtn2.style.display = 'none';
        if (state.timerInterval) {
            clearInterval(state.timerInterval);
            state.timerInterval = null;
        }
        // 计时器显示最终用时
        var elapsed = Math.floor((Date.now() - state.startTime) / 1000);
        var mm = Math.floor(elapsed / 60);
        var ss = elapsed % 60;
        DOM.analysisTimer.textContent = '用时 ' + String(mm).padStart(2,'0') + ':' + String(ss).padStart(2,'0');
        DOM.analysisTimer.classList.add('done');
        updateStepButtons();
        // 有分镜数据时显示拆解按钮
        if (state.results.shots) DOM.splitShotsBtn.classList.add('show');
        // 分步模式完成后也显示结果区
        if (DOM.stepBtns.style.display !== 'none') {
            DOM.resultsSection.classList.add('show');
        }
    }

    function updateTimer() {
        if (!state.startTime) return;
        var elapsed = Math.floor((Date.now() - state.startTime) / 1000);
        var mins = Math.floor(elapsed / 60);
        var secs = elapsed % 60;
        DOM.analysisTimer.textContent = 
            (mins < 10 ? '0' : '') + mins + ':' + (secs < 10 ? '0' : '') + secs;
    }

    function stopAnalysis() {
        if (state.abortController) state.abortController.abort();
        state.isAnalyzing = false;
        if (state.reader) state.reader.cancel();
        showError('分析已停止');
        endAnalysis();
    }

    // ============================================================
    // 输入处理
    // ============================================================
    
    function getScriptText() {
        const file = DOM.fileInput.files[0];
        if (file) return '[FILE_UPLOADED]';
        return DOM.textInput.value.trim();
    }
    
    function guessScriptName() {
        // 有文件则用文件名
        if (state.fileName) return state.fileName.replace(/\.[^/.]+$/, '');
        // 从粘贴内容中提取名称
        const text = DOM.textInput.value.trim();
        if (!text) return '未命名剧本';
        const firstLine = text.split('\n')[0].trim();
        // 尝试匹配 《xxx》、第X集、标题:xxx 等模式
        const titleMatch = firstLine.match(/《(.+?)》/) || firstLine.match(/第[一二三四五六七八九十\d]+[集章回]/);
        if (titleMatch) return titleMatch[0].replace(/《|》/g, '');
        // 取前20个字符作为名称
        const name = firstLine.replace(/[#*\-=\s]/g, '').slice(0, 20);
        return name || '未命名剧本';
    }

    function getApiConfig() {
        const provider = DOM.apiProvider.value;
        const config = {
            provider: provider,
            api_key: '',
            model: '',
            base_url: '',
            temperature: parseFloat(DOM.paramTemperature.value),
            top_p: parseFloat(DOM.paramTopP.value),
            frequency_penalty: parseFloat(DOM.paramFreqPenalty.value),
            presence_penalty: parseFloat(DOM.paramPresPenalty.value),
            max_tokens: parseInt(DOM.paramMaxTokens.value),
            thinking: DOM.paramThinking.checked,
        };
        
        if (provider === 'deepseek') {
            config.api_key = DOM.apiKeyInput.value.trim();
            config.model = DOM.modelSelect.value || 'deepseek-v4-flash';
            config.base_url = DOM.baseUrlInput.value.trim() || 'https://api.deepseek.com';
        } else if (provider === 'openai') {
            config.api_key = DOM.apiKeyInput.value.trim();
            config.model = DOM.modelInput.value.trim() || 'gpt-4o';
            config.base_url = DOM.baseUrlInput.value.trim() || 'https://api.openai.com/v1';
        } else {
            config.model = DOM.modelInput.value.trim() || 'qwen2.5:7b';
            config.base_url = DOM.baseUrlInput.value.trim() || 'http://localhost:11434';
        }
        
        return config;
    }

    // ============================================================
    // 事件绑定
    // ============================================================
    
    function bindEvents() {
        DOM.uploadZone.addEventListener('click', () => {
            DOM.fileInput.click();
        });
        
        DOM.uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            DOM.uploadZone.classList.add('dragover');
        });
        
        DOM.uploadZone.addEventListener('dragleave', () => {
            DOM.uploadZone.classList.remove('dragover');
        });
        
        DOM.uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            DOM.uploadZone.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                DOM.fileInput.files = e.dataTransfer.files;
                handleFileSelect();
            }
        });
        
        DOM.fileInput.addEventListener('change', handleFileSelect);
        
        DOM.clearFileBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            clearFile();
        });
        
        DOM.clearTextBtn.addEventListener('click', () => {
            DOM.textInput.value = '';
            DOM.charCount.textContent = '0 字符';
        });
        
        DOM.textInput.addEventListener('input', () => {
            const len = DOM.textInput.value.length;
            DOM.charCount.textContent = `${len} 字符`;
            if (DOM.fileInput.files.length) {
                clearFile();
            }
        });
        
        DOM.apiProvider.addEventListener('change', handleProviderChange);
        
        // API Key 输入 - 防抖自动获取模型
        DOM.apiKeyInput.addEventListener('input', () => {
            if (state.fetchTimer) {
                clearTimeout(state.fetchTimer);
            }
            state.fetchTimer = setTimeout(() => {
                fetchModels();
            }, 800);
        });
        
        // 地址变更也触发模型刷新
        DOM.baseUrlInput.addEventListener('change', () => {
            if (DOM.apiProvider.value === 'deepseek') {
                fetchModels();
            }
        });
        
        DOM.startBtn.addEventListener('click', startAutoAnalysis);
        DOM.stopBtn.addEventListener('click', stopAnalysis);
        DOM.stopBtn2.addEventListener('click', stopAnalysis);
        
        // 模式切换
        DOM.modeAuto.addEventListener('click', function() {
            DOM.modeAuto.classList.add('active');
            DOM.modeStep.classList.remove('active');
            DOM.autoBtns.style.display = 'flex';
            DOM.stepBtns.style.display = 'none';
        });
        DOM.modeStep.addEventListener('click', function() {
            DOM.modeStep.classList.add('active');
            DOM.modeAuto.classList.remove('active');
            DOM.autoBtns.style.display = 'none';
            DOM.stepBtns.style.display = 'flex';
            updateStepButtons();
        });
        
        // 人物小传 & 故事大纲 输入监听 — 实时更新按钮状态
        DOM.charBioText.addEventListener('input', function() {
            state.charBioText = DOM.charBioText.value;
            updateMaterialsUI();
            saveMaterialsState();
        });
        DOM.outlineText.addEventListener('input', function() {
            state.outlineText = DOM.outlineText.value;
            updateMaterialsUI();
            saveMaterialsState();
        });
        
        // 分步按钮
        DOM.stepCharBtn.addEventListener('click', function() { startStepAnalysis('characters'); });
        DOM.stepPropBtn.addEventListener('click', function() { startStepAnalysis('props'); });
        DOM.stepSceneBtn.addEventListener('click', function() { startStepAnalysis('scenes'); });
        DOM.stepShotBtn.addEventListener('click', function() { startStepAnalysis('shots'); });
        
        DOM.downloadHtmlBtn.addEventListener('click', downloadHtml);
        DOM.downloadWordBtn.addEventListener('click', downloadWord);
        DOM.previewBtn.addEventListener('click', previewReport);
        DOM.errorClose.addEventListener('click', hideError);
        DOM.openFolderBtn.addEventListener('click', function() {
            var dir = state.downloadFiles.outputDir;
            if (dir) {
                // 尝试打开文件管理器
                window.open('file://' + dir, '_blank');
            }
        });
        
        // 分镜拆解浮动按钮
        DOM.splitShotsBtn.addEventListener('click', function() {
            var btn = DOM.splitShotsBtn;
            btn.disabled = true;
            btn.textContent = '...';
            fetch('/api/split-shots', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({script_name: state.scriptName})
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.error) { showError(data.error); return; }
                showError('拆解完成！已生成 ' + data.count + ' 个单集分镜文件到 ' + data.folder, true);
            })
            .catch(function(e) { showError('拆解失败: ' + e.message); })
            .finally(function() { btn.disabled = false; btn.textContent = '拆'; });
        });
        
        loadProviderConfig();
    }

    function handleFileSelect() {
        const file = DOM.fileInput.files[0];
        if (!file) return;
        
        const ext = file.name.split('.').pop().toLowerCase();
        const validExts = ['pdf', 'docx', 'doc', 'txt', 'md', 'markdown'];
        
        if (!validExts.includes(ext)) {
            showError('不支持的文件格式，请上传 PDF、Word、TXT 或 MD 文件');
            DOM.fileInput.value = '';
            return;
        }
        
        state.fileName = file.name;
        state.fileSize = file.size;
        state.fileType = ext;
        
        DOM.fileName.textContent = file.name;
        DOM.fileSize.textContent = formatFileSize(file.size);
        DOM.fileInfo.style.display = 'block';
        DOM.uploadZone.classList.add('has-file');
        
        DOM.textInput.value = '';
        DOM.charCount.textContent = '0 字符';
        
        state.scriptName = file.name.replace(/\.[^/.]+$/, '');
    }

    function clearFile() {
        DOM.fileInput.value = '';
        DOM.fileInfo.style.display = 'none';
        DOM.uploadZone.classList.remove('has-file');
        state.fileName = '';
        state.fileSize = 0;
        state.fileType = '';
    }

    function handleProviderChange() {
        loadProviderConfig();
        
        // 切换提供商时自动获取模型
        if (DOM.apiProvider.value === 'deepseek') {
            fetchModels();
        }
    }

    function loadProviderConfig() {
        const provider = DOM.apiProvider.value;
        
        if (provider === 'deepseek') {
            DOM.apiKeyInput.style.display = 'block';
            DOM.apiKeyInput.placeholder = 'sk-...';
            DOM.modelInput.style.display = 'none';
            DOM.modelSelect.style.display = 'block';
            if (!DOM.modelSelect.value) DOM.modelSelect.value = 'deepseek-v4-flash';
            DOM.baseUrlInput.placeholder = 'https://api.deepseek.com';
            DOM.baseUrlInput.value = 'https://api.deepseek.com';
            const savedKey = localStorage.getItem('ds_api_key');
            if (savedKey) DOM.apiKeyInput.value = savedKey;
            const savedUrl = localStorage.getItem('ds_base_url');
            if (savedUrl) DOM.baseUrlInput.value = savedUrl;
            
        } else if (provider === 'openai') {
            DOM.apiKeyInput.style.display = 'block';
            DOM.apiKeyInput.placeholder = 'sk-...';
            DOM.modelInput.style.display = 'block';
            DOM.modelSelect.style.display = 'none';
            DOM.modelStatus.style.display = 'none';
            DOM.modelInput.placeholder = 'gpt-4o';
            DOM.modelInput.value = DOM.modelInput.value || 'gpt-4o';
            DOM.baseUrlInput.placeholder = 'https://api.openai.com/v1';
            DOM.baseUrlInput.value = 'https://api.openai.com/v1';
            const savedKey = localStorage.getItem('oa_api_key');
            if (savedKey) DOM.apiKeyInput.value = savedKey;
            
        } else {
            DOM.apiKeyInput.style.display = 'none';
            DOM.apiKeyInput.value = '';
            DOM.modelInput.style.display = 'block';
            DOM.modelSelect.style.display = 'none';
            DOM.modelStatus.style.display = 'none';
            DOM.modelInput.placeholder = 'qwen2.5:7b';
            DOM.baseUrlInput.placeholder = 'http://localhost:11434';
            DOM.baseUrlInput.value = 'http://localhost:11434';
            
            const savedUrl = localStorage.getItem('ollama_base_url');
            if (savedUrl) DOM.baseUrlInput.value = savedUrl;
            const savedModel = localStorage.getItem('ollama_model');
            if (savedModel) DOM.modelInput.value = savedModel;
        }
    }

    function resetAll() {
        if (state.isAnalyzing) return;
        
        clearFile();
        DOM.textInput.value = '';
        DOM.charCount.textContent = '0 字符';
        DOM.progressPanel.classList.remove('show');
        DOM.resultsSection.classList.remove('show');
        resetAllSteps();
        state.results = {};
        state.downloadFiles = {};
        hideError();
        DOM.startBtn.disabled = false;
        DOM.startBtn.textContent = '开始分析';
        DOM.stopBtn.style.display = 'none';
        DOM.stopBtn2.style.display = 'none';
        DOM.analysisTimer.style.display = 'none';
        updateStepButtons();
        // 注意：不清除风格选择和辅助材料
    }

    // ============================================================
    // 辅助材料管理
    // ============================================================
    
    function clearCache() {
        if (state.isAnalyzing) return;
        
        // 清空 localStorage：保留 API Key，清除其他
        localStorage.removeItem('wm_script_name');
        localStorage.removeItem('wm_breakdown_style');
        localStorage.removeItem('wm_char_bio_text');
        localStorage.removeItem('wm_char_bio_filename');
        localStorage.removeItem('wm_outline_text');
        localStorage.removeItem('wm_outline_filename');
        
        // 调用后端清除知识库
        var scriptName = state.scriptName || '未命名剧本';
        fetch('/api/clear_materials', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({script_name: scriptName})
        }).catch(function() {});
        
        // 重置状态
        state.scriptName = '未命名剧本';
        state.charBioText = '';
        state.charBioFile = null;
        state.outlineText = '';
        state.outlineFile = null;
        state.materialsPreprocessed = false;
        state.preprocessSummary = null;
        state.breakdownStyle = 'female';
        
        // 重置 UI
        DOM.charBioText.value = '';
        DOM.outlineText.value = '';
        DOM.charBioFileInput.value = '';
        DOM.outlineFileInput.value = '';
        DOM.charBioFileInfo.style.display = 'none';
        DOM.outlineFileInfo.style.display = 'none';
        document.querySelector('input[name="breakdownStyle"][value="female"]').checked = true;
        
        updateMaterialsUI();
        
        showError('缓存已清除，下次分析时需重新确认剧本名称', true);
    }

    function saveMaterialsState() {
        localStorage.setItem('wm_breakdown_style', state.breakdownStyle);
        localStorage.setItem('wm_char_bio_text', state.charBioText);
        localStorage.setItem('wm_outline_text', state.outlineText);
        localStorage.setItem('wm_script_name', state.scriptName);
        if (state.charBioFile) {
            localStorage.setItem('wm_char_bio_filename', state.charBioFile.name);
        }
        if (state.outlineFile) {
            localStorage.setItem('wm_outline_filename', state.outlineFile.name);
        }
    }
    
    function restoreMaterialsState() {
        var savedName = localStorage.getItem('wm_script_name');
        if (savedName) state.scriptName = savedName;
        
        var style = localStorage.getItem('wm_breakdown_style');
        if (style && (style === 'female' || style === 'male' || style === 'normal')) {
            state.breakdownStyle = style;
        } else {
            style = 'female';
            state.breakdownStyle = 'female';
        }
        var radio = document.querySelector('input[name="breakdownStyle"][value="' + style + '"]');
        if (radio) radio.checked = true;
        
        var charBio = localStorage.getItem('wm_char_bio_text');
        if (charBio) {
            state.charBioText = charBio;
            DOM.charBioText.value = charBio;
        }
        var outline = localStorage.getItem('wm_outline_text');
        if (outline) {
            state.outlineText = outline;
            DOM.outlineText.value = outline;
        }
        updateMaterialsUI();
    }
    
    function updateMaterialsUI() {
        var hasCharBio = !!(state.charBioText || state.charBioFile);
        var hasOutline = !!(state.outlineText || state.outlineFile);
        
        DOM.clearCharBioBtn.style.display = hasCharBio ? '' : 'none';
        DOM.clearOutlineBtn.style.display = hasOutline ? '' : 'none';
        
        if (state.materialsPreprocessed && state.preprocessSummary) {
            DOM.materialsStatus.textContent = '(知识库已就绪)';
            DOM.materialsStatus.style.color = '#4CAF50';
            DOM.preprocessBtn.style.display = '';
            DOM.preprocessBtn.textContent = '更新知识库';
            DOM.preprocessBtn.disabled = false;
            DOM.preprocessBtn.style.opacity = '1';
            DOM.preprocessBtn.style.cursor = 'pointer';
            DOM.preprocessHint.textContent = '已生成：' + (state.preprocessSummary.char_count || 0) + '个角色，点击可重新生成';
        } else if (hasCharBio || hasOutline) {
            DOM.materialsStatus.textContent = '(未生成知识库)';
            DOM.materialsStatus.style.color = '#FF9D00';
            DOM.preprocessBtn.style.display = '';
            DOM.preprocessBtn.textContent = '生成知识库';
            DOM.preprocessBtn.disabled = false;
            DOM.preprocessBtn.style.opacity = '1';
            DOM.preprocessBtn.style.cursor = 'pointer';
            DOM.preprocessHint.textContent = '分析前需要先生成临时知识库';
        } else {
            DOM.materialsStatus.textContent = '(请填写人物小传或故事大纲)';
            DOM.materialsStatus.style.color = '#888';
            DOM.preprocessBtn.style.display = '';
            DOM.preprocessBtn.textContent = '生成知识库';
            DOM.preprocessBtn.disabled = true;
            DOM.preprocessBtn.style.opacity = '0.4';
            DOM.preprocessBtn.style.cursor = 'not-allowed';
            DOM.preprocessHint.textContent = '请先填写或上传人物小传/故事大纲';
        }
        
        if (state.charBioFile) {
            DOM.charBioFileInfo.style.display = '';
            DOM.charBioFileInfo.textContent = '已上传: ' + state.charBioFile.name;
        } else {
            DOM.charBioFileInfo.style.display = 'none';
        }
        if (state.outlineFile) {
            DOM.outlineFileInfo.style.display = '';
            DOM.outlineFileInfo.textContent = '已上传: ' + state.outlineFile.name;
        } else {
            DOM.outlineFileInfo.style.display = 'none';
        }
    }
    
    function showNoMaterialsDialog(onSkip) {
        if (!DOM.noMaterialsDialog) {
            var dlg = document.createElement('div');
            dlg.id = 'noMaterialsDialog';
            dlg.style.cssText = 'display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);z-index:9999;align-items:center;justify-content:center;';
            dlg.innerHTML = '<div style="background:#1A1A1A;border:1px solid #333;border-radius:12px;padding:32px;max-width:420px;text-align:center;">' +
                '<div style="font-size:40px;margin-bottom:16px;">📋</div>' +
                '<h3 style="color:#FFF;margin-bottom:8px;">未提供人物小传和故事大纲</h3>' +
                '<p style="color:#999;font-size:14px;margin-bottom:24px;">分析结果可能缺少角色和场景细节。建议上传或粘贴材料以获得更精准的拆解效果。</p>' +
                '<div style="display:flex;gap:12px;justify-content:center;">' +
                    '<button id="noMatSkipBtn" style="padding:10px 24px;background:#333;color:#CCC;border:none;border-radius:8px;cursor:pointer;font-size:14px;">跳过继续</button>' +
                    '<button id="noMatBackBtn" style="padding:10px 24px;background:#FF6600;color:#FFF;border:none;border-radius:8px;cursor:pointer;font-size:14px;">去上传材料</button>' +
                '</div></div>';
            document.body.appendChild(dlg);
            DOM.noMaterialsDialog = dlg;
        }
        DOM.noMaterialsDialog.style.display = 'flex';
        document.getElementById('noMatSkipBtn').onclick = onSkip;
        document.getElementById('noMatBackBtn').onclick = function() {
            DOM.noMaterialsDialog.style.display = 'none';
            DOM.charBioText.focus();
        };
    }

    function showScriptNameDialog(onConfirm) {
        var detected = guessScriptName();
        if (!DOM.scriptNameDialog) {
            var dlg = document.createElement('div');
            dlg.id = 'scriptNameDialog';
            dlg.style.cssText = 'display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);z-index:9999;align-items:center;justify-content:center;';
            dlg.innerHTML = '<div style="background:#1A1A1A;border:1px solid #333;border-radius:12px;padding:32px;max-width:440px;text-align:center;">' +
                '<div style="font-size:36px;margin-bottom:12px;">📝</div>' +
                '<h3 style="color:#FFF;margin-bottom:16px;">确认剧本名称</h3>' +
                '<p style="color:#999;font-size:13px;margin-bottom:16px;">用于生成输出文件和识别剧集系列，可手动修改</p>' +
                '<input id="scriptNameInput" type="text" style="width:100%;padding:10px 14px;background:#0D0D0D;border:1px solid #333;border-radius:8px;color:#FFF;font-size:15px;margin-bottom:20px;outline:none;" />' +
                '<div style="display:flex;gap:12px;justify-content:center;">' +
                    '<button id="scriptNameConfirmBtn" style="padding:10px 32px;background:#FF6600;color:#FFF;border:none;border-radius:8px;cursor:pointer;font-size:14px;">确认</button>' +
                '</div></div>';
            document.body.appendChild(dlg);
            DOM.scriptNameDialog = dlg;
            DOM.scriptNameInput = document.getElementById('scriptNameInput');
            DOM.scriptNameConfirmBtn = document.getElementById('scriptNameConfirmBtn');
        }
        DOM.scriptNameInput.value = detected;
        DOM.scriptNameInput.select();
        DOM.scriptNameInput.focus();
        DOM.scriptNameDialog.style.display = 'flex';
        // Remove old listener and add new one
        var newBtn = DOM.scriptNameConfirmBtn.cloneNode(true);
        DOM.scriptNameConfirmBtn.parentNode.replaceChild(newBtn, DOM.scriptNameConfirmBtn);
        DOM.scriptNameConfirmBtn = newBtn;
        DOM.scriptNameConfirmBtn.addEventListener('click', function() {
            var name = DOM.scriptNameInput.value.trim();
            if (!name) {
                DOM.scriptNameInput.style.borderColor = '#f44';
                return;
            }
            DOM.scriptNameInput.style.borderColor = '#333';
            state.scriptName = name;
            saveMaterialsState();
            DOM.scriptNameDialog.style.display = 'none';
            if (onConfirm) onConfirm();
        });
        // Enter key
        DOM.scriptNameInput.onkeydown = function(e) {
            if (e.key === 'Enter') DOM.scriptNameConfirmBtn.click();
        };
    }

    function handleStyleChange(value) {
        state.breakdownStyle = value;
        saveMaterialsState();
    }
    
    function handleCharBioFile(file) {
        state.charBioFile = file;
        var reader = new FileReader();
        reader.onload = function(e) {
            state.charBioText = e.target.result;
            DOM.charBioText.value = state.charBioText;
            state.materialsPreprocessed = false;
            saveMaterialsState();
            updateMaterialsUI();
        };
        reader.readAsText(file);
    }
    
    function handleOutlineFile(file) {
        state.outlineFile = file;
        var reader = new FileReader();
        reader.onload = function(e) {
            state.outlineText = e.target.result;
            DOM.outlineText.value = state.outlineText;
            state.materialsPreprocessed = false;
            saveMaterialsState();
            updateMaterialsUI();
        };
        reader.readAsText(file);
    }
    
    function clearCharBio() {
        state.charBioText = '';
        state.charBioFile = null;
        DOM.charBioText.value = '';
        DOM.charBioFileInput.value = '';
        state.materialsPreprocessed = false;
        state.preprocessSummary = null;
        localStorage.removeItem('wm_char_bio_text');
        localStorage.removeItem('wm_char_bio_filename');
        saveMaterialsState();
        updateMaterialsUI();
    }
    
    function clearOutline() {
        state.outlineText = '';
        state.outlineFile = null;
        DOM.outlineText.value = '';
        DOM.outlineFileInput.value = '';
        state.materialsPreprocessed = false;
        state.preprocessSummary = null;
        localStorage.removeItem('wm_outline_text');
        localStorage.removeItem('wm_outline_filename');
        saveMaterialsState();
        updateMaterialsUI();
    }
    
    function doPreprocess() {
        var charBio = DOM.charBioText.value.trim();
        var outline = DOM.outlineText.value.trim();
        if (!charBio && !outline) {
            showError('请先输入人物小传或故事大纲');
            return;
        }
        
        var apiConfig = getApiConfig();
        if (apiConfig.provider === 'deepseek' && !apiConfig.api_key) {
            showError('请填写 API Key');
            return;
        }
        
        state.charBioText = charBio;
        state.outlineText = outline;
        saveMaterialsState();
        
        // 先确认剧本名称，再生成知识库
        showScriptNameDialog(function() {
            DOM.preprocessBtn.disabled = true;
            DOM.preprocessBtn.textContent = '⏳ 生成中...';
            DOM.preprocessHint.textContent = '正在分析人物小传和故事大纲...';
            
            fetch('/api/preprocess', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                char_bio: charBio,
                story_outline: outline,
                script_name: state.scriptName,
                api_config: apiConfig
            })
        })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            DOM.preprocessBtn.disabled = false;
            if (data.success) {
                state.materialsPreprocessed = true;
                state.preprocessSummary = data.summary;
                DOM.preprocessHint.textContent = data.message;
                DOM.preprocessHint.style.color = '#4CAF50';
                updateMaterialsUI();
            } else {
                showError(data.error || '预处理失败');
                DOM.preprocessHint.textContent = '预处理失败，请重试';
                DOM.preprocessHint.style.color = '#f44';
                updateMaterialsUI();
            }
        })
        .catch(function(err) {
            DOM.preprocessBtn.disabled = false;
            showError('预处理请求失败: ' + (err.message || '网络错误'));
            DOM.preprocessHint.textContent = '网络错误，请重试';
            DOM.preprocessHint.style.color = '#f44';
        });
    });
}

    // ============================================================
    // 下载和预览
    // ============================================================
    
    function downloadHtml() {
        if (!state.downloadFiles.html) {
            showError('报告尚未生成');
            return;
        }
        window.location.href = `/api/download/${state.downloadFiles.html}`;
    }
    
    function downloadWord() {
        if (!state.downloadFiles.word) {
            showError('报告尚未生成');
            return;
        }
        window.location.href = `/api/download/${state.downloadFiles.word}`;
    }
    
    function previewReport() {
        if (!state.downloadFiles.html) {
            showError('报告尚未生成');
            return;
        }
        window.open(`/api/preview/${state.downloadFiles.html}`, '_blank');
    }

    // ============================================================
    // 初始化
    // ============================================================
    
    // ===== 安全: HTML 净化函数 =====
function sanitizeHTML(str) {
    if (!str) return '';
    var temp = document.createElement('div');
    temp.textContent = str;
    var escaped = temp.innerHTML;
    // 允许的基本格式化标签白名单
    var allowed = {
        'b': [], 'i': [], 'u': [], 'em': [], 'strong': [], 'br': [], 'p': [],
        'h3': [], 'h4': [], 'ul': [], 'ol': [], 'li': [], 'span': [],
        'div': ['style'], 'table': ['style'], 'tr': [], 'td': ['style'], 'th': [],
        'pre': [], 'code': [], 'hr': [], 'blockquote': [], 'a': ['href', 'target']
    };
    // 允许带样式的 span/div 重新注入
    return escaped.replace(/&lt;(\/?)(\w+)([^&]*)&gt;/g, function(m, slash, tag, attrs) {
        tag = tag.toLowerCase();
        if (!allowed[tag]) return m;
        var attrStr = attrs.replace(/&quot;/g, '"').replace(/&amp;/g, '&');
        if (allowed[tag].length === 0) return '<' + slash + tag + '>';
        var cleanedAttrs = '';
        var attrRegex = /(\w+)=["']([^"']*)["']/g;
        var match;
        while ((match = attrRegex.exec(attrStr)) !== null) {
            if (allowed[tag].indexOf(match[1].toLowerCase()) !== -1) {
                cleanedAttrs += ' ' + match[1] + '="' + match[2] + '"';
            }
        }
        return '<' + slash + tag + cleanedAttrs + '>';
    }).replace(/&lt;!--[\s\S]*?--&gt;/g, '');
}

document.addEventListener('DOMContentLoaded', function() {
        initDOM();
        bindEvents();
        resetAllSteps();
        bindParamSliders();
        updateParamRange();
        
        // 默认选中 DeepSeek，自动获取模型
        if (DOM.apiProvider.value === 'deepseek') {
            const savedKey = localStorage.getItem('ds_api_key');
            if (savedKey) {
                fetchModels();
            } else {
                showFallbackModels();
            }
        }
        
        // 恢复辅助材料状态
        restoreMaterialsState();
        
        console.log('剧本拆解大师 v2.49 已加载');
        console.log('支持 Ollama + DeepSeek API');
    });

})();
