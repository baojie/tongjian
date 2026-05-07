#!/usr/bin/env python3
"""合并重叠类型：将英文类型替换为对应的中文概念子类。

映射表:
  military → 军事  economy → 经济  law → 法律  ritual → 礼制
  astronomy → 天文  artifact → 器物  official → 官职  tribe → 民族

用法:
    python3 wiki/scripts/batch_merge_types.py wiki/public/pages
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TYPE_MAP = {
    'military': '军事',
    'economy': '经济',
    'law': '法律',
    'ritual': '礼制',
    'astronomy': '天文',
    'artifact': '器物',
    'official': '官职',
    'tribe': '民族',
}

FRONTMATTER_RE = re.compile(r"\A(---\s*\n.*?\n---)\s*\n", re.DOTALL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pages_root", help="wiki/public/pages directory")
    args = ap.parse_args()

    root = Path(args.pages_root)
    if not root.is_dir():
        print(f"[error] not a directory: {root}", file=sys.stderr)
        sys.exit(1)

    stats = {eng: 0 for eng in TYPE_MAP}
    total = 0

    for md_file in sorted(root.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(text)
        if not m:
            continue
        front = m.group(1)

        # Check type line
        changed = False
        for eng, cn in TYPE_MAP.items():
            if re.search(rf"^type:\s*{eng}\s*$", front, re.MULTILINE):
                # Replace type line
                new_front = re.sub(
                    rf"^type:\s*{eng}\s*$",
                    f"type: {cn}",
                    front,
                    flags=re.MULTILINE,
                )
                new_text = text[:m.start()] + new_front + "\n" + text[m.end():]
                md_file.write_text(new_text, encoding="utf-8")
                stats[eng] += 1
                total += 1
                changed = True
                break  # one type per file

    print(f"已合并 {total} 个页面：")
    for eng, cn in TYPE_MAP.items():
        if stats[eng]:
            print(f"  {eng}({stats[eng]}) → {cn}")


if __name__ == "__main__":
    main()
