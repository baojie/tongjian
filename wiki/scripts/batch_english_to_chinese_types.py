#!/usr/bin/env python3
"""将所有英文类型值转为中文。

映射表:
  person → 人物    place → 地点      event → 事件      battle → 战役
  institution → 制度  state → 国家    dynasty → 王朝   overview → 综述
  quote → 名句     chapter → 章节    concept → 概念    year → 年份
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TYPE_MAP = {
    'person': '人物',
    'place': '地点',
    'event': '事件',
    'battle': '战役',
    'institution': '制度',
    'state': '国家',
    'dynasty': '王朝',
    'overview': '综述',
    'quote': '名句',
    'chapter': '章节',
    'concept': '概念',
    'year': '年份',
}

FRONTMATTER_RE = re.compile(r"\A(---\s*\n.*?\n---)\s*\n", re.DOTALL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pages_root", help="wiki/public/pages directory")
    args = ap.parse_args()

    root = Path(args.pages_root)
    stats = {k: 0 for k in TYPE_MAP}
    total = 0

    for md_file in sorted(root.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(text)
        if not m:
            continue
        front = m.group(1)

        for eng, cn in TYPE_MAP.items():
            if re.search(rf"^type:\s*{eng}\s*$", front, re.MULTILINE):
                new_front = re.sub(
                    rf"^type:\s*{eng}\s*$", f"type: {cn}",
                    front, flags=re.MULTILINE,
                )
                new_text = text[:m.start()] + new_front + "\n" + text[m.end():]
                md_file.write_text(new_text, encoding="utf-8")
                stats[eng] += 1
                total += 1
                break  # one type per file

    print(f"已转换 {total} 个页面：")
    for eng, cn in TYPE_MAP.items():
        if stats[eng]:
            print(f"  {eng}({stats[eng]}) → {cn}")


if __name__ == "__main__":
    main()
