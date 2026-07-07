# tools/pdf_parser.py
# PDF 简历解析工具：从 PDF 文件中提取纯文本内容

import io
import re
from pypdf import PdfReader


def parse_pdf_to_text(file_bytes: bytes, filename: str = "") -> str:
    """
    从 PDF 文件字节流中提取文本内容。

    参数:
        file_bytes: PDF 文件的原始字节
        filename: 原始文件名（仅用于日志/错误提示）

    返回:
        提取出的纯文本字符串

    异常:
        ValueError: 文件不是有效 PDF 或无法提取文本
    """
    if not file_bytes:
        raise ValueError("文件内容为空，请上传有效的 PDF 文件")

    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"无法解析 PDF 文件：{e}")

    total_pages = len(reader.pages)
    if total_pages == 0:
        raise ValueError("PDF 文件不包含任何页面")

    text_parts = []
    for i, page in enumerate(reader.pages):
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text.strip())

    full_text = "\n\n".join(text_parts)

    # 清理常见格式问题
    full_text = clean_resume_text(full_text)

    if not full_text.strip():
        raise ValueError(
            "无法从 PDF 中提取文本。"
            "可能原因：1) PDF 是扫描图片 2) PDF 使用了特殊的字体编码。"
            "请尝试直接粘贴简历文本。"
        )

    return full_text


def clean_resume_text(text: str) -> str:
    """清理提取出的简历文本中的常见格式问题"""
    # 移除过多的连续空行（超过2个的化为2个）
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 移除行首行尾多余空格但保留缩进结构
    lines = []
    for line in text.split('\n'):
        lines.append(line.rstrip())
    text = '\n'.join(lines)

    # 统一中文/英文标点之间的多余空格
    # 中文字符间的空格
    text = re.sub(r'(?<=[一-鿿])\s+(?=[一-鿿])', '', text)

    return text.strip()


def get_pdf_metadata(file_bytes: bytes) -> dict:
    """
    获取 PDF 文件的元数据（页数、作者等）。

    参数:
        file_bytes: PDF 文件的原始字节

    返回:
        {"pages": 3, "title": "...", "author": "..."}
    """
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        meta = reader.metadata or {}
        return {
            "pages": len(reader.pages),
            "title": str(meta.get("title", "")),
            "author": str(meta.get("author", "")),
        }
    except Exception:
        return {"pages": 0, "title": "", "author": ""}
