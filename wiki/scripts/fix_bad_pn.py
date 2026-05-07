#!/usr/bin/env python3
"""
fix_bad_pn.py — 修复错误的多 PN 合并引注格式。

错误格式示例：
  （008-040、008-051）  → （008-040）（008-051）
  （025-045/046）       → （025-045）（025-046）   短省略形式：同卷
  （100-063/100-066）   → （100-063）（100-066）   全形式斜线
  （016-060/073/087）   → （016-060）（016-073）（016-087）

规则：
  - 顿号（、）/ 斜线（/）均视为分隔符
  - 分隔后若片段为纯 3 位数字（无连字号），则继承上一个完整引注的卷号
  - 不修改章节页（第???卷.md）

用法：
  python3 wiki/scripts/fix_bad_pn.py [--dry-run]
"""
from __future__ import annotations
import re, sys, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGES_DIR = ROOT / "public" / "pages"
RECORD_REVISION = ROOT / "scripts" / "record_revision.py"

# 匹配一个（...）括号内含至少一个 NNN-PPP 且含顿号或斜线
RE_BAD = re.compile(r'（(\d{3}-\d{3})(?:[、/](?:\d{3}-\d{3}|\d{3}))+）')
RE_FULL = re.compile(r'^\d{3}-\d{3}$')
RE_SHORT = re.compile(r'^\d{3}$')


def expand_pns(match_str: str) -> str:
    """把一个错误括号组展开为多个正确引注。"""
    inner = match_str[1:-1]          # 去掉全角括号
    parts = re.split(r'[、/]', inner)

    last_vol = None
    result = []
    for part in parts:
        if RE_FULL.match(part):
            last_vol = part.split('-')[0]
            result.append(f'（{part}）')
        elif RE_SHORT.match(part) and last_vol:
            result.append(f'（{last_vol}-{part}）')
        else:
            # 无法解析，保留原样（不修改）
            return match_str
    return ''.join(result)


def fix_content(text: str) -> tuple[str, int]:
    count = 0
    def replacer(m):
        nonlocal count
        fixed = expand_pns(m.group(0))
        if fixed != m.group(0):
            count += 1
        return fixed
    new_text = RE_BAD.sub(replacer, text)
    return new_text, count


def main():
    dry_run = '--dry-run' in sys.argv
    total_files = 0
    total_fixes = 0

    for md in sorted(PAGES_DIR.glob("*.md")):
        # 跳过章节页
        if re.match(r'第\d{3}卷', md.stem):
            continue

        original = md.read_text(encoding='utf-8')
        new_text, count = fix_content(original)

        if count == 0:
            continue

        total_files += 1
        total_fixes += count

        if dry_run:
            print(f"[dry] {md.name}: {count} 处")
            # 展示具体变更
            for m in RE_BAD.finditer(original):
                fixed = expand_pns(m.group(0))
                if fixed != m.group(0):
                    print(f"      {m.group(0)}  →  {fixed}")
        else:
            md.write_text(new_text, encoding='utf-8')
            r = subprocess.run(
                [sys.executable, str(RECORD_REVISION), md.stem,
                 '--summary', '修复错误多 PN 合并引注格式',
                 '--author', 'butler'],
                capture_output=True, text=True, cwd=ROOT.parent,
            )
            if r.returncode != 0:
                print(f"  ✗ {md.name}: {r.stderr.strip()[:80]}")
            else:
                print(f"  ✓ {md.name}: {count} 处")

    suffix = ' (DRY RUN)' if dry_run else ''
    print(f"\n{'DRY RUN ' if dry_run else ''}完成：{total_files} 文件，{total_fixes} 处修复{suffix}")


if __name__ == '__main__':
    main()
