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
    except Exception as e:
        raise RuntimeError(f"Word 解析失败: {str(e)}")


def parse_txt(file_path):
    """解析 TXT 文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        if not text.strip():
            raise ValueError("TXT 文件内容为空")
        return text
    except UnicodeDecodeError:
        # 尝试其他编码
        for encoding in ['gbk', 'gb2312', 'latin-1']:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    text = f.read()
                if text.strip():
                    return text
            except (UnicodeDecodeError, LookupError):
                continue
        raise ValueError("无法解码 TXT 文件，请使用 UTF-8 编码保存")
