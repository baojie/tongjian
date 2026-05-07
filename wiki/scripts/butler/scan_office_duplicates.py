#!/usr/bin/env python3
"""扫描所有官职页面，查找 ## 历任列表 中的重复/伪section问题。

检测项:
  - 是否存在伪section header（如 ## 初元 |）
  - 是否存在重复的任职记录（同人名多行）
  - page总行数和预估正确行数的差距
"""

import sys
import re
from pathlib import Path

PAGES_DIR = Path(__file__).resolve().parent.parent.parent / "public" / "pages"

def scan_page(slug: str) -> dict | None:
    md_path = PAGES_DIR / f"{slug}.md"
    if not md_path.exists():
        return None

    text = md_path.read_text(encoding="utf-8")
    issues = []

    # 检测伪section header: ## word | (紧随的下一行是 | 开头)
    if re.search(r'\n## [^|\n]*\|\n\|', text):
        issues.append("伪section header（含 | 的 ## 行，紧随 | 行）")

    # 检测多次出现的 ## 历任列表
    count_headers = text.count('## 历任列表')
    if count_headers > 1:
        issues.append(f"多个 ## 历任列表 节（{count_headers}处）")

    # 检测 ## 初元 等王朝名/年号出现在 ## 行上
    pseudo_headers = re.findall(r'\n(## [^|\n]*)\|\n', text)
    if pseudo_headers:
        issues.append(f"发现了 {len(pseudo_headers)} 个伪section: {pseudo_headers}")

    # 检测表格数据行中提取的姓名是否重复
    if '## 历任列表' in text:
        rows = re.findall(r'^\| \[\[([^\]]+)\]\]', text, re.MULTILINE)
        seen_names = {}
        for r in rows:
            seen_names.setdefault(r, 0)
            seen_names[r] += 1
        dupes = {n: c for n, c in seen_names.items() if c > 1}
        if dupes:
            issues.append(f"重复任职记录: {len(dupes)}个姓名重复出现")

    if not issues:
        return None

    return {
        "slug": slug,
        "issues": issues,
        "total_lines": len(text.split('\n')),
        "approx_expected": None,
    }


def main():
    print("=" * 60)
    print("扫描官职页面重复/伪section问题")
    print("=" * 60)

    all_pages = sorted(PAGES_DIR.glob("*.md"))
    affected = []

    for md in all_pages:
        slug = md.stem
        # 跳过卷页和明显非官职页
        if slug.startswith("第") or slug in ("index", "pages"):
            continue
        result = scan_page(slug)
        if result:
            affected.append(result)
            print(f"\n⚠️  {slug} ({result['total_lines']}行)")
            for issue in result["issues"]:
                print(f"   • {issue}")

    print("\n" + "=" * 60)
    if not affected:
        print("✅ 未发现受影响的页面")
    else:
        print(f"发现 {len(affected)} 个受影响的页面:")
        for a in affected:
            print(f"  • {a['slug']} — {'; '.join(a['issues'])}")


if __name__ == "__main__":
    main()
