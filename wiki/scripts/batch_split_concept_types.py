#!/usr/bin/env python3
"""批量修改概念页面：将 type=concept 替换为 concept_cat 的值，删除 concept_cat 字段。

用法:
    python3 wiki/scripts/batch_split_concept_types.py wiki/public/pages
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FRONTMATTER_RE = re.compile(r"\A(---\s*\n.*?\n---)\s*\n", re.DOTALL)


def update_frontmatter(front: str) -> tuple[str, bool]:
    """解析 frontmatter YAML（不依赖 yaml 库，逐行处理），修改 type 和 concept_cat。"""
    lines = front.splitlines()
    new_lines: list[str] = []
    changed = False
    concept_cat_value: str | None = None
    type_seen = False

    # 第一遍：找 concept_cat 的值
    for line in lines:
        # 跳过第一行 --- 和最后一行 ---
        if line.strip() == "---":
            continue
        m = re.match(r"^concept_cat:\s*(.+)$", line)
        if m:
            concept_cat_value = m.group(1).strip()
            # 可能带引号
            concept_cat_value = concept_cat_value.strip("\"'")
            break

    if not concept_cat_value:
        return front, False  # 没有 concept_cat，跳过

    # 第二遍：重写 lines
    for line in lines:
        stripped = line.strip()
        if stripped == "---":
            new_lines.append(line)
            continue

        # 修改 type 行
        m_type = re.match(r"^type:\s*(.+)$", line)
        if m_type:
            type_seen = True
            old_type = m_type.group(1).strip()
            if old_type.strip("\"'") == "概念":
                indent = line[:len(line) - len(line.lstrip())]
                new_lines.append(f"{indent}type: {concept_cat_value}")
                changed = True
            else:
                new_lines.append(line)
            continue

        # 跳过 concept_cat 行（删除）
        if re.match(r"^concept_cat:", line):
            changed = True
            continue

        new_lines.append(line)

    return "\n".join(new_lines), changed


def process_file(md_file: Path) -> bool:
    text = md_file.read_text(encoding="utf-8")

    m = FRONTMATTER_RE.match(text)
    if not m:
        return False  # 无 frontmatter

    front = m.group(1)
    new_front, changed = update_frontmatter(front)
    if not changed:
        return False

    # 替换 frontmatter（保证 --- 后有一个换行）
    new_text = text[:m.start()] + new_front + "\n" + text[m.end():]
    md_file.write_text(new_text, encoding="utf-8")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pages_root", help="wiki/public/pages directory")
    args = ap.parse_args()

    root = Path(args.pages_root)
    if not root.is_dir():
        print(f"[error] not a directory: {root}", file=sys.stderr)
        sys.exit(1)

    total = 0
    changed = 0
    skipped_no_cat = 0
    skipped_non_concept = 0

    for md_file in sorted(root.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(text)
        if not m:
            continue

        front = m.group(1)
        # 检查是否为 type: 概念
        if not re.search(r"^type:\s*概念\s*$", front, re.MULTILINE):
            continue

        total += 1

        # 检查是否有 concept_cat
        if not re.search(r"^concept_cat:", front, re.MULTILINE):
            skipped_no_cat += 1
            continue

        if process_file(md_file):
            changed += 1
        else:
            skipped_no_cat += 1

    print(f"概念页面总计: {total}")
    print(f"已修改: {changed}")
    print(f"跳过（无 concept_cat）: {skipped_no_cat}")

    md_files_updated = changed
    if md_files_updated:
        print(f"\n下一步:")
        print(f"  1. python3 wiki/scripts/build_registry.py wiki/public/pages --out wiki/public/pages.json --out-lite wiki/public/pages.lite.json")
        print(f"  2. 修改前端 TYPE_LABELS 和首页卡片分类")
        print(f"  3. git commit")


if __name__ == "__main__":
    main()
