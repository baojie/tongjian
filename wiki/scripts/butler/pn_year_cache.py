#!/usr/bin/env python3
"""
扫描所有卷页面，构建 PN→年号 映射缓存。

输出：
  wiki/data/pn_to_year.json
  格式: {"PN": {"year": "年号", "ad": "公元年份(数字)"}, ...}

用法：
    python3 wiki/scripts/butler/pn_year_cache.py [--out PATH]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
PAGES_DIR = ROOT / "wiki" / "public" / "pages"
DEFAULT_OUT = ROOT / "wiki" / "data" / "pn_to_year.json"

RE_PN = re.compile(r"^\[(\d{3})-(\d{3})\]\s*(.*)")
RE_YEAR_END = re.compile(r"[元一二三四五六七八九十零〇○\d]+年[）\)]?\s*$")
RE_VOL_HEADER = re.compile(r"^【")
RE_AD = re.compile(r"公元([零一二三四五六七八九十\d]+)年")
RE_LEADING_ARTIFACT = re.compile(r"^[◎●○]")


def is_year_marker(content: str) -> bool:
    if RE_VOL_HEADER.match(content):
        return False
    return bool(RE_YEAR_END.search(content))


def normalize_year_label(content: str) -> str:
    """清理年份标签：去除 wikilink 和 artifact 字符。"""
    # 去掉行首 artifact 符号
    text = RE_LEADING_ARTIFACT.sub("", content)
    # [[A|B]] → B, [[A]] → A
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    # 多个空白合并
    text = re.sub(r"\s+", "", text)
    return text.strip()


def extract_ad_year(text: str) -> int | None:
    """从年份标签中提取公元年份。"""
    m = RE_AD.search(text)
    if m:
        # 公元三六年 → 36
        ad_str = m.group(1)
        try:
            # 先试阿拉伯数字
            return int(ad_str)
        except ValueError:
            # 中文数字转阿拉伯
            cn_map = {
                "零": 0, "〇": 0, "○": 0, "一": 1, "二": 2, "三": 3,
                "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
            }
            result = 0
            for ch in ad_str:
                if ch in cn_map:
                    result = result * 10 + cn_map[ch]
            return result if result > 0 else None
    return None


def build_cache(pages_dir: Path) -> dict[str, dict]:
    """遍历所有卷页面，返回 {pn: {year, ad}} 映射。"""
    cache: dict[str, dict] = {}
    current_year: str | None = None
    current_ad: int | None = None

    vol_files = sorted(pages_dir.rglob("第???卷.md"))
    for vf in vol_files:
        text = vf.read_text(encoding="utf-8")
        text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL)

        current_year = None
        current_ad = None

        for line in text.splitlines():
            line_s = line.strip()
            if not line_s:
                continue
            m = RE_PN.match(line_s)
            if not m:
                continue
            pn = f"{m.group(1)}-{m.group(2)}"
            raw_content = m.group(3).strip()
            if is_year_marker(raw_content):
                current_year = normalize_year_label(raw_content)
                current_ad = extract_ad_year(raw_content)
            if current_year:
                entry: dict[str, object] = {"year": current_year}
                if current_ad:
                    entry["ad"] = current_ad
                cache[pn] = entry

    return cache


def main():
    out_path = DEFAULT_OUT
    if "--out" in sys.argv:
        idx = sys.argv.index("--out")
        out_path = Path(sys.argv[idx + 1])

    cache = build_cache(PAGES_DIR)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    total_pn = len(cache)
    with_ad = sum(1 for v in cache.values() if "ad" in v)
    unique_years = len(set(v["year"] for v in cache.values()))

    print(f"PN→年号 映射已写入: {out_path}")
    print(f"  总 PN 数: {total_pn}")
    print(f"  含公元年份: {with_ad} ({with_ad / total_pn * 100:.1f}%)")
    print(f"  去重年号数: {unique_years}")

    for pn in ["001-002", "010-020", "069-015", "185-010", "294-050"]:
        entry = cache.get(pn, {})
        print(f"  {pn} → {entry}")


if __name__ == "__main__":
    main()
