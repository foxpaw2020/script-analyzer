"""Security-focused tests for the audit fixes."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))

import pytest

import config
from utils.url import validate_api_base_url


class TestValidateApiBaseUrl:
    """Tests for validate_api_base_url SSRF prevention."""

    def test_allows_known_provider(self):
        validate_api_base_url("https://api.deepseek.com/v1", "deepseek")

    def test_allows_local_ollama(self):
        validate_api_base_url("http://localhost:11434", "ollama")
        validate_api_base_url("http://127.0.0.1:11434", "ollama")

    def test_rejects_internal_metadata(self):
        with pytest.raises(ValueError):
            validate_api_base_url("http://169.254.169.254/latest/meta-data/")

    def test_rejects_private_ip(self):
        with pytest.raises(ValueError):
            validate_api_base_url("http://192.168.1.1/models")

    def test_rejects_file_scheme(self):
        with pytest.raises(ValueError):
            validate_api_base_url("file:///etc/passwd")

    def test_rejects_unknown_ollama_host(self):
        with pytest.raises(ValueError):
            validate_api_base_url("http://example.com:11434", "ollama")


class TestAppSecurity:
    """Flask app-level security tests."""

    @pytest.fixture
    def client(self):
        from app import app as flask_app
        flask_app.config['TESTING'] = True
        return flask_app.test_client()

    def test_cors_does_not_echo_arbitrary_origin(self, client):
        resp = client.get('/', headers={'Origin': 'https://evil.com'})
        assert resp.headers.get('Access-Control-Allow-Origin') != 'https://evil.com'

    def test_cors_allows_same_origin(self, client):
        resp = client.get('/', headers={'Origin': 'http://localhost'})
        assert resp.headers.get('Access-Control-Allow-Origin') == 'http://localhost'

    def test_list_models_rejects_ssrf(self, client, monkeypatch):
        # Ensure no env whitelist is set so default behavior kicks in.
        monkeypatch.setattr(config, 'ALLOWED_BASE_URLS', None)
        resp = client.post(
            '/api/list_models',
            json={'api_key': 'fake', 'base_url': 'http://169.254.169.254'}
        )
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['source'] == 'fallback'
        assert '不允许' in data['error']

    def test_check_connection_rejects_ssrf(self, client, monkeypatch):
        monkeypatch.setattr(config, 'ALLOWED_BASE_URLS', None)
        resp = client.post(
            '/api/check_connection',
            json={'provider': 'deepseek', 'base_url': 'http://169.254.169.254', 'api_key': 'fake'}
        )
        data = resp.get_json()
        assert data['success'] is False
        assert '不允许' in data['message']


class TestFileUploadValidation:
    """Tests for file content type validation."""

    def test_accepts_valid_txt(self, tmp_path):
        from services.file_parser import validate_file_type
        p = tmp_path / "valid.txt"
        p.write_text("This is a valid text file.")
        assert validate_file_type(str(p)) is True

    def test_rejects_binary_renamed_to_txt(self, tmp_path):
        from services.file_parser import validate_file_type
        p = tmp_path / "fake.txt"
        p.write_bytes(b"\x89PNG\r\n\x1a\n")
        assert validate_file_type(str(p)) is False

    def test_accepts_valid_pdf(self, tmp_path):
        from services.file_parser import validate_file_type
        p = tmp_path / "valid.pdf"
        p.write_bytes(b'%PDF-1.4\n1 0 obj\n')
        assert validate_file_type(str(p)) is True

    def test_rejects_pdf_renamed_to_docx(self, tmp_path):
        from services.file_parser import validate_file_type
        p = tmp_path / "fake.docx"
        p.write_bytes(b'%PDF-1.4\n1 0 obj\n')
        assert validate_file_type(str(p)) is False

    def test_rejects_unknown_extension(self, tmp_path):
        from services.file_parser import validate_file_type
        p = tmp_path / "malicious.exe"
        p.write_bytes(b"MZ")
        assert validate_file_type(str(p)) is False
