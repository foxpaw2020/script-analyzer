"""Flask 测试基础设施"""
import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))

from app import app as flask_app


@pytest.fixture
def app():
    """创建测试用 Flask 应用"""
    flask_app.config['TESTING'] = True
    return flask_app


@pytest.fixture
def client(app):
    """创建 Flask 测试客户端"""
    return app.test_client()
