#!/usr/bin/env python3
"""
批量创建姓氏页面。
直接写入文件 + 一次 rebuild registry，比挨个调 add_page.py 快得多。

用法:
    python3 wiki/scripts/butler/batch_create_surname_pages.py [--dry-run] [--force]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
PAGES = ROOT / "wiki/public/pages"
REG = ROOT / "wiki/scripts/build_registry.py"

FRONTMATTER_RE = __import__("re").compile(r"\A---\s*\n(.*?)\n---\s*\n", __import__("re").DOTALL)


def parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        import yaml
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="覆盖非姓氏类型的同名页面")
    args = ap.parse_args()

    with open(ROOT / "wiki/public/pages.json") as f:
        registry = json.load(f)

    # 统计各姓氏人物数
    surname_counts = {}
    for pid, entry in registry["pages"].items():
        s = entry.get("surname")
        t = entry.get("type")
        if s and t == "人物":
            surname_counts[s] = surname_counts.get(s, 0) + 1

    print(f"需创建姓氏页面: {len(surname_counts)}")
    created = 0
    existed = 0
    skipped = 0

    for surname in sorted(surname_counts.keys()):
        count = surname_counts[surname]
        page_name = f"{surname}（姓氏）"
        target = PAGES / f"{page_name}.md"

        # 旧格式兼容：先检查旧文件名，再检查新文件名
        old_target = PAGES / f"{surname}.md"
        if old_target.exists() and old_target != target:
            existing_fm = parse_frontmatter(old_target.read_text(encoding="utf-8"))
            if existing_fm.get("type") == "姓氏":
                # 旧格式文件，直接覆盖写入（迁移后旧文件会被重命名逻辑处理）
                pass
            elif not args.force:
                print(f"  ⚠ {surname} 文件名冲突（{old_target.name} type={existing_fm.get('type')}），跳过")
                skipped += 1
                continue

        if target.exists() and not args.force:
            print(f"  · {page_name} 已存在，跳过")
            existed += 1
            continue

        content = f"""---
id: {surname}（姓氏）
type: 姓氏
label: {surname}
description: 姓「{surname}」的历史人物列表，共 {count} 人。
tags: [姓氏]
---

# {surname}姓

::: query
type: 人物
surname: {surname}
display: table
fields: [label, tags, total_refs, description]
sort: total_refs
order: desc
:::
"""

        if args.dry_run:
            print(f"  · {page_name}（{count} 人）")
            created += 1
            continue

        target.write_text(content, encoding="utf-8")
        # 清理旧格式文件（如果存在且路径不同）
        if old_target.exists() and old_target != target:
            old_target.unlink()
        print(f"  ✓ {page_name}（{count} 人）")
        created += 1

    print(f"\n新建: {created}，已存在: {existed}，跳过: {skipped}")

    if created > 0 and not args.dry_run:
        r = subprocess.run(
            [sys.executable, str(REG), str(PAGES),
             "--out", str(ROOT / "wiki/public/pages.json"),
             "--out-lite", str(ROOT / "wiki/public/pages.lite.json")],
            capture_output=True, text=True, cwd=ROOT
        )
        if r.returncode == 0:
            print("✓ pages.json + pages.lite.json 已更新")
        else:
            print(f"⚠ pages.json 更新失败: {r.stderr.strip()}", file=sys.stderr)


if __name__ == "__main__":
    main()
