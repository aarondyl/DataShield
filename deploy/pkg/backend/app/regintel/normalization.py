"""文本规范化与内容哈希（版本检测的基础）。

每次抓取后先 normalize 再算 ``SHA256(normalized_text)``：
- 哈希相同 → NO_CHANGE，流程结束；
- 哈希不同 → 创建 RegulationVersion N+1，进入结构级 diff。
"""

from __future__ import annotations

import hashlib
import re

#: 连续 3 个及以上换行折叠为 2 个
_MULTI_NEWLINE = re.compile(r"\n{3,}")
#: 行内连续空白（含全角空格、制表符）折叠为单个空格
_MULTI_SPACE = re.compile(r"[ \t　]+")


def normalize_text(text: str) -> str:
    """规范化法规文本，保证同一内容稳定得到同一哈希。

    步骤：统一换行符 → 行内空白折叠 → 去行尾空白 → 去空行的行内空格 →
    折叠多余空行 → 整体 strip。
    """
    if not text:
        return ""
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_MULTI_SPACE.sub(" ", line).strip() for line in t.split("\n")]
    t = "\n".join(lines)
    t = _MULTI_NEWLINE.sub("\n\n", t)
    return t.strip()


def content_hash(normalized_text: str) -> str:
    """计算规范化文本的 SHA256（十六进制），作为版本指纹。"""
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
