"""
路径工具 - 开发环境和 PyInstaller 打包环境兼容
"""
import os
import sys


def get_base_path():
    """获取应用资源根目录（开发:项目目录, 打包:临时解压目录）"""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def get_user_path(*subdirs):
    """获取用户可写目录（打包:exe所在目录, 开发:项目内）"""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, *subdirs)
    os.makedirs(path, exist_ok=True)
    return path
