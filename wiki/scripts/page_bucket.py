"""page_bucket.py — 按页面名拼音前缀计算分片子目录。

用于 pages/ 目录下的文件分布：
  - CJK 开头 → 取第一字拼音的前 2 个字母
  - ASCII 字母/数字开头 → 取前 2 个 ASCII 字母数字
  - 单字名/边界病例 → 补 `0` 或 fallback
"""

from __future__ import annotations

import re
from pathlib import Path

# 前导非字母数字/非汉字的标点符号
LEADING_PUNCT_RE = re.compile(r"^[《》（）\"''。，、？！；：·—…‥‧\s]+")

try:
    from pypinyin import pinyin as _pinyin, Style as _Style
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False


def page_bucket(name: str) -> str:
    """返回页面名对应的分片目录名（不含 /）。

    >>> page_bucket("刘备")
    'li'
    >>> page_bucket("曹操")
    'ca'
    >>> page_bucket("About")
    'ab'
    """
    raw = LEADING_PUNCT_RE.sub("", name)
    if not raw:
        raw = name

    first = raw[0]

    # ASCII 字母/数字开头
    if first.isascii() and first.isalnum():
        chars = [c.lower() for c in raw if c.isascii() and c.isalnum()]
        if len(chars) >= 2:
            return chars[0] + chars[1]
        elif len(chars) == 1:
            return chars[0] + "0"
        return "xx"

    # CJK 开头 → 拼音
    if HAS_PYPINYIN:
        return _cjk_bucket(raw)
    else:
        # fallback: 取前 2 个 UTF-8 字符的 hex
        enc = raw.encode("utf-8")
        return enc[:2].hex() if len(enc) >= 2 else enc.hex().ljust(2, "0")


def _cjk_bucket(name: str) -> str:
    """取第一字拼音的前 2 字母。"""
    try:
        py = _pinyin(name[0], style=_Style.TONE2)[0][0]
    except Exception:
        return _fallback(name)

    letters = "".join(c for c in py.lower() if c.isalpha())

    if len(letters) >= 2:
        return letters[:2]

    # 单字母拼音（如 "阿" → "a"），取第二字首字母补足
    if len(letters) == 1 and len(name) > 1:
        try:
            py2 = _pinyin(name[1], style=_Style.TONE2)[0][0]
        except Exception:
            return letters + "0"
        l2 = "".join(c for c in py2.lower() if c.isalpha())
        return letters + (l2[0] if l2 else "0")

    return letters.ljust(2, "0")


def _fallback(name: str) -> str:
    if len(name) >= 2:
        return name[:2]
    return (name + "0")[:2]


BASE62_ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'


def hash_bucket(h: str) -> str:
    """Base62 hash → 2-char bucket name (62×16=992 buckets)。

    用于 line_index/ 的子目录分配。首字符原样保留（62 种），
    次字符通过 ALPHABET 索引 %16 映射到 0-f（16 种）。
    共 62×16=992 桶，使任意行的 hash 能均匀分布。
    """
    first = h[0]
    second = format(BASE62_ALPHABET.index(h[1]) % 16, 'x')
    return first + second


def page_path(slug: str) -> str:
    """返回页面在 pages/ 下的相对路径（含 .md）。

    >>> page_path("刘备")
    'li/刘备.md'
    """
    bucket = page_bucket(slug)
    if bucket:
        return f"{bucket}/{slug}.md"
    return f"{slug}.md"


def resolve_page_file(pages_root: Path, slug: str) -> Path | None:
    """在 pages_root 下查找 slug.md（先查 bucket 子目录，再查根目录）。

    用于 edit_page / record_revision 等需要按 slug 找文件路径的脚本。
    """
    # 1. 计算 bucket 并尝试
    bucket = page_bucket(slug)
    candidate = pages_root / bucket / f"{slug}.md"
    if candidate.exists():
        return candidate

    # 2. 扫描所有子目录（bucket 算法变更后的兜底）
    for f in pages_root.rglob(f"{slug}.md"):
        return f

    return None
