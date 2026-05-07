#!/usr/bin/env python3
"""
h22_fix_emdash.py — 修复词条正文中滥用「——」切分段落的写法。

规则（优先级从高到低）：
  1. 三项以上平行列举 → Markdown 无序列表
  2. 两段切分（各自≥30字）→ 句号换行
  3. 引出子句（后半<30字）→ 保留或改为逗号
  4. frontmatter description 含「——」→ 改为「；」或截断

跳过：引用块、标题行、只读章节页（第???卷.md）

用法：
  python3 wiki/scripts/butler/h22_fix_emdash.py [--limit N] [--dry-run]
"""
from __future__ import annotations

import re
import sys
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PAGES_DIR = ROOT / "wiki/public/pages"
REG_PATH = ROOT / "wiki/public/pages.json"
RECORD = ROOT / "wiki/scripts/record_revision.py"

FRONTMATTER_RE = re.compile(r'\A---\s*\n(.*?)\n---\s*\n', re.DOTALL)
DESCRIPTION_RE = re.compile(r'^(description:\s*)(.*?)(\s*)$', re.MULTILINE)

# ── 破折号检测 ──────────────────────────────────────────────────────
EM = '——'


def is_chapter_page(slug: str) -> bool:
    return bool(re.match(r'^第\d{3}卷$', slug))


def count_emdash_issues(text: str) -> int:
    """统计正文中有问题的破折号行数（多破折号或超长行）"""
    count = 0
    in_quote = False
    fm_end = FRONTMATTER_RE.match(text)
    body = text[fm_end.end():] if fm_end else text
    for line in body.split('\n'):
        if line.startswith('>'):
            continue
        if line.startswith('#'):
            continue
        if EM in line and len(line) > 60:
            parts = line.split(EM)
            if len(parts) >= 3:
                count += 1
            elif len(parts) == 2 and len(parts[0].strip()) >= 30 and len(parts[1].strip()) >= 30:
                count += 1
    return count


def fix_description(desc: str) -> str:
    """修复 frontmatter description 中的破折号：截断至首个——之前。"""
    if EM not in desc:
        return desc
    # 取破折号前部分，确保以合理标点结尾
    before = desc.split(EM)[0].strip().rstrip('，、：')
    return before


def fix_line(line: str) -> str:
    """处理单行正文中的破折号（保守策略）。"""
    if EM not in line:
        return line
    if line.startswith('>') or line.startswith('#') or line.startswith('|'):
        return line

    parts = line.split(EM)

    if len(parts) >= 3:
        items = [p.strip().rstrip('，；') for p in parts if p.strip()]
        # 仅当各项都较短（纯列举）时转为列表，否则用句号连接
        if all(5 <= len(i) <= 50 for i in items):
            return '\n'.join(f'- {i}' for i in items)
        # 各项较长时，用"。"替换"——"连接
        joined = '。'.join(i for i in items if i)
        if not joined.endswith('。'):
            joined += '。'
        return joined

    # len(parts) == 2
    left = parts[0].strip()
    right = parts[1].strip()
    # 两部分都是独立长句 → 分段
    if len(left) >= 40 and len(right) >= 40:
        left_end = left[-1] if left else ''
        if left_end not in '。；！？':
            left = left + '。'
        return left + '\n\n' + right
    # 右侧很短（注解/括号补充）→ 改为逗号
    if len(right) < 20:
        return left + '，' + right
    # 其余保留
    return line


def fix_text(text: str) -> tuple[str, int]:
    """处理整个页面文本，返回（新文本, 修改行数）。"""
    fm_match = FRONTMATTER_RE.match(text)
    if not fm_match:
        frontmatter = ''
        body = text
    else:
        frontmatter_raw = text[:fm_match.end()]
        body = text[fm_match.end():]
        # 修复 description 字段
        frontmatter = DESCRIPTION_RE.sub(
            lambda m: m.group(1) + fix_description(m.group(2)) + m.group(3),
            frontmatter_raw,
        )

    changes = 0
    new_lines = []
    for line in body.split('\n'):
        if EM not in line or len(line) <= 60:
            new_lines.append(line)
            continue
        if line.startswith('>') or line.startswith('#') or line.startswith('|'):
            new_lines.append(line)
            continue
        fixed = fix_line(line)
        if fixed != line:
            changes += 1
        new_lines.append(fixed)

    new_body = '\n'.join(new_lines)
    new_text = frontmatter + new_body
    if frontmatter != (text[:fm_match.end()] if fm_match else ''):
        changes += 1
    return new_text, changes


def load_registry():
    return json.loads(REG_PATH.read_text(encoding='utf-8'))['pages']


def find_pages_with_issues(pages: dict, limit: int) -> list[str]:
    slugs = []
    for slug, meta in pages.items():
        if meta.get('type') == '章节':
            continue
        if is_chapter_page(slug):
            continue
        md = PAGES_DIR / f'{slug}.md'
        if not md.exists():
            continue
        text = md.read_text(encoding='utf-8')
        if count_emdash_issues(text) > 0:
            slugs.append(slug)
        if len(slugs) >= limit:
            break
    return slugs


def main():
    dry_run = '--dry-run' in sys.argv
    limit = 50
    for i, arg in enumerate(sys.argv):
        if arg == '--limit' and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    pages = load_registry()
    targets = find_pages_with_issues(pages, limit)
    print(f"[H22 fix-emdash] 找到 {len(targets)} 个含破折号段落的词条"
          f"{' (DRY RUN)' if dry_run else ''}...")

    modified = 0
    total_changes = 0

    for slug in targets:
        md = PAGES_DIR / f'{slug}.md'
        original = md.read_text(encoding='utf-8')
        new_text, changes = fix_text(original)

        if changes == 0 or new_text == original:
            continue

        if dry_run:
            print(f"  [dry] {slug}: {changes} 处修改")
            modified += 1
            total_changes += changes
            continue

        md.write_text(new_text, encoding='utf-8')
        r = subprocess.run(
            [sys.executable, str(RECORD), slug,
             '--summary', 'H22: 修复破折号段落→正常段落/列表',
             '--author', 'butler'],
            capture_output=True, text=True, cwd=ROOT,
        )
        if r.returncode != 0:
            print(f"  ✗ {slug}: {r.stderr.strip()[:60]}", file=sys.stderr)
            continue

        modified += 1
        total_changes += changes
        print(f"  ✓ {slug}: {changes} 处修改")

    print(f"\n[H22] {'DRY RUN ' if dry_run else ''}完成："
          f"{modified}/{len(targets)} 页修改，{total_changes} 处变更")


if __name__ == '__main__':
    main()
