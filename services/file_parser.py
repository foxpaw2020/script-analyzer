"""
剧本文件解析服务 - 支持 PDF/Word/TXT 格式
"""

import os
import re


def parse_script(file_path):
    """解析上传的剧本文件（PDF/Word/TXT），返回纯文本"""
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.pdf':
        return parse_pdf(file_path)
    elif ext in ('.docx', '.doc'):
        return parse_docx(file_path)
    elif ext in ('.txt', '.md', '.markdown'):
        return parse_txt(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {ext}，请上传 PDF、Word、TXT 或 MD 文件")


def parse_pdf(file_path):
    """解析 PDF 文件"""
    try:
        import fitz  # PyMuPDF
        text_parts = []
        with fitz.open(file_path) as doc:
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    text_parts.append(f"--- 第 {page_num + 1} 页 ---\n{text}")
        full_text = '\n\n'.join(text_parts)
        if not full_text.strip():
            raise ValueError("PDF 文件内容为空或无法提取文字")
        return full_text
    except ImportError:
        raise RuntimeError("请在终端运行 pip install PyMuPDF 安装 PDF 解析库")
    except Exception as e:
        if "file not found" in str(e).lower():
            raise FileNotFoundError(f"PDF 文件不存在: {file_path}")
        raise RuntimeError(f"PDF 解析失败: {str(e)}")


def parse_docx(file_path):
    """解析 Word 文件"""
    try:
        import mammoth
        with open(file_path, "rb") as f:
            result = mammoth.extract_raw_text(f)
            text = result.value
            if not text.strip():
                raise ValueError("Word 文件内容为空或无法提取文字")
            return text
    except ImportError:
        raise RuntimeError("请在终端运行 pip install mammoth 安装 Word 解析库")
    except ImportError:
        raise RuntimeError("请在终端运行 pip install mammoth 安装 Word 解析库")
    except Exception as e:
        import traceback
        raise RuntimeError(f"Word 解析失败({os.path.basename(file_path)}): {str(e)}")


def parse_txt(file_path):
    """解析 TXT 文件，自动检测编码"""
    # 尝试 UTF-8
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        if not text.strip():
            raise ValueError("TXT 文件内容为空")
        return text
    except UnicodeDecodeError:
        pass
    # 尝试其他编码
    tried = []
    for encoding in ['gbk', 'gb2312', 'latin-1']:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                text = f.read()
            if text.strip():
                return text
            tried.append(f'{encoding}(空内容)')
        except (UnicodeDecodeError, LookupError) as e:
            tried.append(f'{encoding}({e})')
    raise ValueError(f"无法解码 TXT 文件，已尝试: {', '.join(tried)}，请使用 UTF-8 编码保存")


# 文件头魔数映射
FILE_MAGIC = {
    b'%PDF': '.pdf',
    b'PK\x03\x04': '.docx',
    b'\x89PNG\r\n\x1a\n': '.png',
    b'\xff\xd8\xff': '.jpg',
}


def validate_file_type(file_path):
    """通过文件头和内容校验扩展名是否匹配真实类型。

    Args:
        file_path: 上传文件保存路径。

    Returns:
        bool: True if the file content matches the claimed extension.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in ('.pdf', '.docx', '.doc', '.txt', '.md', '.markdown'):
        return False

    try:
        with open(file_path, 'rb') as f:
            header = f.read(8)
    except OSError:
        return False

    if ext in ('.txt', '.md', '.markdown'):
        # 文本文件：尝试 UTF-8 解码，避免二进制可执行文件伪装
        try:
            header.decode('utf-8', errors='strict')
            return True
        except UnicodeDecodeError:
            return False

    for magic, real_ext in FILE_MAGIC.items():
        if header.startswith(magic):
            return ext == real_ext

    # 旧 .doc 格式无法简单识别，允许通过
    return ext == '.doc'
