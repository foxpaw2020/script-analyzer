"""
P0 紧急测试套件 — 覆盖关键风险路径

组 A: call_ai() 异常分支 mock 测试（~8 个用例）
组 B: parse_txt() 多编码测试（~5 个用例）
组 C: 路径穿越安全测试（~4 个用例）
组 D: /api/analyze 集成测试（~4 个用例）
"""

import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))

import config
from services.ai_service import call_ai
from services.file_parser import parse_txt
from utils.text import detect_episode, split_script_by_episodes


# ============================================================
# 辅助工具
# ============================================================

def parse_sse_events(data: str) -> list:
    """解析 SSE 流内容，返回 [(event_type, data_dict), ...]"""
    events = []
    for block in data.split('\n\n'):
        block = block.strip()
        if not block:
            continue
        event_type = None
        event_data = None
        for line in block.split('\n'):
            if line.startswith('event: '):
                event_type = line[7:]
            elif line.startswith('data: '):
                try:
                    event_data = json.loads(line[6:])
                except json.JSONDecodeError:
                    event_data = line[6:]
        if event_type is not None:
            events.append((event_type, event_data))
    return events


# ============================================================
# 组 A: call_ai() 异常分支 mock 测试
# ============================================================

class TestCallAiOllama:
    """Ollama provider 路径测试"""

    @patch('services.ai_service.requests.post')
    def test_call_ai_ollama_success(self, mock_post):
        """mock 返回 {"message":{"content":"hello"}}，验证返回 "hello" """
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"content": "hello"}}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        api_config = {
            "provider": "ollama",
            "model": "qwen2.5:7b",
            "base_url": "http://localhost:11434",
        }
        result = call_ai("system", "user", api_config)
        assert result == "hello"
        mock_post.assert_called_once()

    @patch('services.ai_service.requests.post')
    def test_call_ai_connection_error(self, mock_post):
        """mock side_effect ConnectionError，验证抛出 ConnectionError"""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        api_config = {
            "provider": "ollama",
            "model": "qwen2.5:7b",
            "base_url": "http://localhost:11434",
        }
        with pytest.raises(ConnectionError, match="无法连接到 Ollama"):
            call_ai("system", "user", api_config)

    @patch('services.ai_service.requests.post')
    def test_call_ai_timeout(self, mock_post):
        """mock side_effect Timeout，验证抛出 TimeoutError"""
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        api_config = {
            "provider": "ollama",
            "model": "qwen2.5:7b",
            "base_url": "http://localhost:11434",
        }
        with pytest.raises(TimeoutError, match="AI 请求超时"):
            call_ai("system", "user", api_config)

    @patch('services.ai_service.requests.post')
    def test_call_ai_ollama_empty_response(self, mock_post):
        """mock 返回 {"message":{}}（无 content），验证返回空字符串"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {}}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        api_config = {
            "provider": "ollama",
            "model": "qwen2.5:7b",
            "base_url": "http://localhost:11434",
        }
        result = call_ai("system", "user", api_config)
        assert result == ""

    @patch('services.ai_service.requests.post')
    def test_call_ai_invalid_temperature(self, mock_post):
        """传入 api_config={"temperature": "abc"}，应转为 RuntimeError 而非崩溃"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"content": "ok"}}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        api_config = {
            "provider": "ollama",
            "model": "qwen2.5:7b",
            "base_url": "http://localhost:11434",
            "temperature": "abc",
        }
        with pytest.raises(RuntimeError, match="AI 参数配置错误"):
            call_ai("system", "user", api_config)

    @patch('services.ai_service.requests.post')
    def test_call_ai_invalid_max_tokens(self, mock_post):
        """传入 api_config={"max_tokens": ""}，应转为 RuntimeError 而非崩溃"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": {"content": "ok"}}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        api_config = {
            "provider": "ollama",
            "model": "qwen2.5:7b",
            "base_url": "http://localhost:11434",
            "max_tokens": "",
        }
        with pytest.raises(RuntimeError, match="AI 参数配置错误"):
            call_ai("system", "user", api_config)


class TestCallAiDeepseek:
    """DeepSeek (OpenAI 兼容) provider 路径测试"""

    @patch('services.ai_service.requests.post')
    def test_call_ai_deepseek_success(self, mock_post):
        """mock 返回 {"choices":[{"message":{"content":"world"}}]}，验证返回 "world" """
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "world"}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        api_config = {
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com",
            "api_key": "sk-test-key",
        }
        result = call_ai("system", "user", api_config)
        assert result == "world"
        mock_post.assert_called_once()

    @patch('services.ai_service.requests.post')
    def test_call_ai_http_error_401(self, mock_post):
        """mock HTTPError 401，验证抛出 RuntimeError（"API Key 无效"）"""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"

        http_error = requests.exceptions.HTTPError()
        http_error.response = mock_resp
        mock_resp.raise_for_status.side_effect = http_error
        mock_post.return_value = mock_resp

        api_config = {
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com",
            "api_key": "sk-bad-key",
        }
        with pytest.raises(RuntimeError, match="API Key 无效"):
            call_ai("system", "user", api_config)

    @patch('services.ai_service.requests.post')
    def test_call_ai_deepseek_reasoning_content(self, mock_post):
        """DeepSeek V4 思考模式：content 为空时回退到 reasoning_content"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "", "reasoning_content": "深度思考结果..."}}]
        }
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        api_config = {
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com",
            "api_key": "sk-test-key",
        }
        result = call_ai("system", "user", api_config)
        assert result == "深度思考结果..."


# ============================================================
# 组 B: parse_txt() 多编码测试
# ============================================================

class TestParseTxtEncoding:
    """parse_txt() 编码回退逻辑测试"""

    def test_parse_txt_utf8(self):
        """标准 UTF-8 中文文件"""
        content = "这是UTF-8编码的中文测试内容"
        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.txt', delete=False, encoding='utf-8'
        )
        try:
            tmp.write(content)
            tmp.close()
            result = parse_txt(tmp.name)
            assert result == content
        finally:
            os.unlink(tmp.name)

    def test_parse_txt_gbk(self):
        """GBK 编码文件"""
        raw = "中文测试内容".encode('gbk')
        tmp = tempfile.NamedTemporaryFile(
            mode='wb', suffix='.txt', delete=False
        )
        try:
            tmp.write(raw)
            tmp.close()
            result = parse_txt(tmp.name)
            assert "中文测试内容" in result
        finally:
            os.unlink(tmp.name)

    def test_parse_txt_gb2312(self):
        """GB2312 编码文件"""
        raw = "GB2312编码测试".encode('gb2312')
        tmp = tempfile.NamedTemporaryFile(
            mode='wb', suffix='.txt', delete=False
        )
        try:
            tmp.write(raw)
            tmp.close()
            result = parse_txt(tmp.name)
            assert "GB2312编码测试" in result
        finally:
            os.unlink(tmp.name)

    def test_parse_txt_latin1(self):
        """latin-1 编码文件（英文为主）"""
        content = "Hello World! Latin-1 content with accents: cafe ol"
        raw = content.encode('latin-1')
        tmp = tempfile.NamedTemporaryFile(
            mode='wb', suffix='.txt', delete=False
        )
        try:
            tmp.write(raw)
            tmp.close()
            result = parse_txt(tmp.name)
            assert result == content
        finally:
            os.unlink(tmp.name)

    def test_parse_txt_empty_file(self):
        """空文件应 raise ValueError"""
        tmp = tempfile.NamedTemporaryFile(
            mode='w', suffix='.txt', delete=False, encoding='utf-8'
        )
        try:
            tmp.write("")
            tmp.close()
            with pytest.raises(ValueError, match="内容为空"):
                parse_txt(tmp.name)
        finally:
            os.unlink(tmp.name)


# ============================================================
# 组 C: 路径穿越安全测试
# ============================================================

class TestPathTraversal:
    """download / preview 端点路径穿越防护测试"""

    @pytest.fixture(autouse=True)
    def setup_output_dir(self, tmp_path, monkeypatch):
        """用临时目录替换 OUTPUT_DIR"""
        self.tmp_output = tmp_path / "outputs"
        self.tmp_output.mkdir(exist_ok=True)
        monkeypatch.setattr(config, 'OUTPUT_DIR', str(self.tmp_output))

    def test_download_path_traversal_blocked(self, client):
        """GET /api/download/../../../etc/passwd -> 404"""
        resp = client.get('/api/download/../../../etc/passwd')
        assert resp.status_code == 404

    def test_download_normal_file(self, client):
        """在 OUTPUT_DIR 放文件，GET 正常路径 -> 200"""
        test_file = self.tmp_output / "test_report.docx"
        test_file.write_bytes(b"fake docx content")
        resp = client.get('/api/download/test_report.docx')
        assert resp.status_code == 200

    def test_preview_path_traversal_blocked(self, client):
        """GET /api/preview/..%2F..%2F..%2Fetc%2Fpasswd -> 404"""
        resp = client.get('/api/preview/..%2F..%2F..%2Fetc%2Fpasswd')
        assert resp.status_code == 404

    def test_preview_normal_file(self, client):
        """在 OUTPUT_DIR 放 HTML 文件，GET 正常路径 -> 200"""
        test_file = self.tmp_output / "test_report.html"
        test_file.write_text("<html><body>Test</body></html>", encoding='utf-8')
        resp = client.get('/api/preview/test_report.html')
        assert resp.status_code == 200
        assert "Test" in resp.get_data(as_text=True)


# ============================================================
# 组 D: /api/analyze 集成测试
# ============================================================

class TestAnalyzeEndpoint:
    """/api/analyze SSE 流式端点集成测试"""

    def test_analyze_no_file_no_text(self, client):
        """POST /api/analyze 无 file 无 text -> SSE error event"""
        resp = client.post('/api/analyze', data={})
        assert resp.status_code == 200
        assert 'text/event-stream' in resp.content_type

        events = parse_sse_events(resp.get_data(as_text=True))
        assert len(events) >= 1
        assert events[0][0] == "error"

    def test_analyze_empty_text(self, client):
        """POST /api/analyze text="" -> SSE error "剧本内容为空" """
        resp = client.post('/api/analyze', data={'text': ''})
        assert resp.status_code == 200

        events = parse_sse_events(resp.get_data(as_text=True))
        assert len(events) >= 1
        assert events[0][0] == "error"
        error_data = events[0][1]
        assert "内容为空" in error_data.get("message", "")

    @patch('app.call_ai')
    def test_analyze_with_text(self, mock_call_ai, client):
        """POST /api/analyze text="测试剧本内容..." -> SSE 流中有 progress + complete"""
        # Mock call_ai 依次返回 8 次调用的结果（4 步 × 2 轮）
        mock_call_ai.side_effect = [
            # 步骤1: characters — 第1轮：列出角色
            '{"characters":["小明","小红"],"total":2}',
            # 步骤1: characters — 第2轮：生成详情
            '{"characters":['
            '  {"name":"小明","age_race":"25岁 亚洲","role_type":"主角","episodes":"第1集",'
            '   "description":"主角小明","personality":["勇敢"],"relationships":[],'
            '   "text_signage":"","info_card":"小明信息卡","prompt":"小明提示词"}],'
            '"total_count":1,"summary":"ok"}',
            # 步骤2: props — 第1轮：列出道具
            '{"characters":[],"total":0}',
            # 步骤2: props — 第2轮：详情（无道具时跳过？不，仍会调用）
            '{"props":[],"total_count":0,"summary":"无道具"}',
            # 步骤3: scenes — 第1轮：列出场景
            '{"characters":[],"total":0}',
            # 步骤3: scenes — 第2轮：详情
            '{"scenes":[],"total_count":0,"summary":"无场景"}',
            # 步骤4: shots — 第1轮：规划分镜
            '{"characters":[],"total":0}',
            # 步骤4: shots — 第2轮：详情
            '{"scenes":[],"total_scenes":0,"total_shots":0,"summary":"无分镜"}',
        ]

        resp = client.post('/api/analyze', data={
            'text': '测试剧本内容，这是一个简短的剧本。',
            'script_name': '测试剧本',
        })
        assert resp.status_code == 200

        events = parse_sse_events(resp.get_data(as_text=True))
        event_types = [e[0] for e in events]

        # 必须有 info 和 progress 事件
        assert "info" in event_types or "progress" in event_types, \
            f"Expected info/progress events, got: {event_types}"

        # 检查没有 error 事件
        error_events = [e for e in events if e[0] == "error"]
        assert len(error_events) == 0, \
            f"Unexpected error events: {error_events}"

        # 最后必须有 complete 事件
        assert event_types[-1] == "complete", \
            f"Expected 'complete' as last event, got: {event_types[-1]}"

    def test_analyze_missing_script_name(self, client):
        """POST /api/analyze text="hello" 无 script_name -> 使用默认名"""
        # 直接测试空文本让它快速返回 error（不需要 AI）
        resp = client.post('/api/analyze', data={'text': 'hello'})
        assert resp.status_code == 200

        events = parse_sse_events(resp.get_data(as_text=True))
        # info 事件应包含默认名 "未命名剧本"
        info_events = [e for e in events if e[0] == "info"]
        if info_events:
            found = False
            for _, data in info_events:
                if data and "未命名剧本" in str(data.get("message", "")):
                    found = True
                    break
            assert found, f"Expected '未命名剧本' in info events: {info_events}"


# ============================================================
# 组 E: split_script_by_episodes() 单元测试
# ============================================================

class TestSplitScriptByEpisodes:
    """split_script_by_episodes() 按集拆分剧本"""

    def test_split_empty_input_returns_none(self):
        """空输入 → None"""
        result = split_script_by_episodes("")
        assert result is None

    def test_split_no_episode_marker_returns_none(self):
        """无集标记文本 → None"""
        result = split_script_by_episodes("这是一段普通文字，没有集标记。")
        assert result is None

    def test_split_single_episode_returns_none(self):
        """仅 1 集 → None（不足 2 集不启用分批）"""
        result = split_script_by_episodes("第1集\n\n这是第一集的内容。")
        assert result is None

    def test_split_three_episodes_arabic(self):
        """3 集阿拉伯数字标记 → 正确拆分"""
        text = (
            "第1集\n\n第一集内容。\n"
            "第2集\n\n第二集内容。\n"
            "第3集\n\n第三集内容。"
        )
        result = split_script_by_episodes(text)
        assert result is not None
        assert len(result) == 3
        assert result[0][0] == 1
        assert "第1集" in result[0][1]
        assert "第一集内容" in result[0][1]
        assert result[1][0] == 2
        assert "第2集" in result[1][1]
        assert result[2][0] == 3
        assert "第3集" in result[2][1]

    def test_split_mixed_cn_en_markers(self):
        """混合中英文标记 → 正确拆分"""
        text = (
            "第1集\n\n中文标记第一集。\n"
            "Episode 2\n\n英文标记第二集。\n"
            "EP 3\n\n缩写标记第三集。"
        )
        result = split_script_by_episodes(text)
        assert result is not None
        assert len(result) == 3
        assert result[0][0] == 1
        assert "第1集" in result[0][1]
        assert result[1][0] == 2
        assert "Episode 2" in result[1][1]
        assert result[2][0] == 3
        assert "EP 3" in result[2][1]

    def test_split_with_preamble(self):
        """集标记前有前言文字 → 前言作为 ep=0 返回"""
        text = "前言：这是序幕内容。\n\n第1集\n\n正片第一集。\n\n第2集\n\n正片第二集。"
        result = split_script_by_episodes(text)
        assert result is not None
        assert len(result) >= 2
        # 第一项应为前言 (ep=0)
        assert result[0][0] == 0
        assert "序幕" in result[0][1]
        # 第二项应为第1集
        assert result[1][0] == 1
        assert "第1集" in result[1][1]

    def test_split_chinese_numeral_episodes(self):
        """中文数字集标记（如 '第二十集'）→ 正确拆分"""
        text = "第一集\n\n内容一。\n\n第二十集\n\n内容二十。\n\n第一百零一集\n\n内容一百零一。"
        result = split_script_by_episodes(text)
        assert result is not None
        assert len(result) == 3
        assert "第一集" in result[0][1]
        assert "第二十集" in result[1][1]
        assert "第一百零一集" in result[2][1]

    def test_detect_episode_zero_in_pattern(self):
        """detect_episode 支持 '零' 在中文数字中"""
        # "一百零一集" 应能检测
        info = detect_episode("这里是第一百零一集的内容")
        assert info is not None
        assert info['current'] == 101
