"""H23: 合并拆开的「地名+官名」wikilink。

发现并修复以下三种 pattern：
  1. [[地名]][[官名]]  → [[地名官名]]
  2. [[地名]]官名      → [[地名官名]]
  3. 地名[[官名]]      → [[地名官名]]

前提：「地名官名」必须是已存在的 wiki 词条（在 pages.json 中）。

用法：
  python3 h23_merge_geo_official.py [--limit N] [--dry-run] [--slug SLUG]
"""

import argparse
import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "wiki/scripts"))
from page_bucket import resolve_page_file  # noqa: E402


SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent
PAGES_DIR = REPO_ROOT / 'wiki' / 'public' / 'pages'
PAGES_JSON = REPO_ROOT / 'docs' / 'wiki' / 'pages.json'

OFFICIAL_SUFFIXES = [
    '节度使', '刺史', '太守', '都督', '都护', '都指挥使', '留守', '经略使',
    '观察使', '防御使', '团练使', '招讨使', '安抚使', '转运使', '提点', '知州',
    '知府', '县令', '县尉', '长史', '司马', '参军', '别驾', '从事', '通判',
]

# 保护区域：代码块、行内代码、blockquote、PN 引注
PROTECT_RE = re.compile(
    r'```[\s\S]*?```'
    r'|`[^`]+`'
    r'|^>.*$'
    r'|（\d{3}-\d{3}）'
    r'|\[\d{3}-\d{3}\]',
    re.MULTILINE,
)


def load_geo_official_pages():
    """返回 {label: slug} 的地名+官名词条字典。"""
    with open(PAGES_JSON) as f:
        data = json.load(f)
    pages = data['pages']
    result = {}
    for slug, meta in pages.items():
        label = meta.get('label') or slug
        for suf in OFFICIAL_SUFFIXES:
            if label.endswith(suf) and len(label) > len(suf):
                result[label] = slug
                break
    return result


def build_patterns(geo_official):
    """为每个词条构建三种匹配 pattern，返回列表 (compiled_re, replacement, label)。"""
    patterns = []
    for label, slug in geo_official.items():
        # 确定 prefix/suffix 分割点
        for suf in OFFICIAL_SUFFIXES:
            if label.endswith(suf) and len(label) > len(suf):
                prefix = label[:-len(suf)]
                break
        else:
            continue

        ep = re.escape(prefix)
        es = re.escape(suf)
        repl = f'[[{label}]]'

        # Pattern 1: [[prefix]][[suffix]]
        p1 = re.compile(rf'\[\[{ep}\]\]\[\[{es}\]\]')
        # Pattern 2: [[prefix]]suffix (suffix 后不紧接词字符)
        p2 = re.compile(rf'\[\[{ep}\]\]{es}(?![\w一-鿿])')
        # Pattern 3: prefix[[suffix]] (prefix 前不紧接词字符)
        p3 = re.compile(rf'(?<![\w一-鿿]){ep}\[\[{es}\]\]')

        patterns.append((p1, repl, label))
        patterns.append((p2, repl, label))
        patterns.append((p3, repl, label))

    return patterns


def apply_patterns_protected(text, patterns):
    """在保护区域外应用所有 pattern，返回 (new_text, changes)。"""
    # 提取保护区域
    protected = []

    def protect(m):
        protected.append(m.group(0))
        return f'\x00p{len(protected)-1}\x00'

    safe = PROTECT_RE.sub(protect, text)

    changes = []
    for pat, repl, label in patterns:
        new_safe, n = pat.subn(repl, safe)
        if n:
            changes.append((label, n))
            safe = new_safe

    # 还原保护区域
    result = re.sub(r'\x00p(\d+)\x00', lambda m: protected[int(m.group(1))], safe)
    return result, changes


def process_file(md_path, patterns, dry_run=False):
    """处理单个文件，返回 change 列表（空表示无修改）。"""
    text = md_path.read_text(encoding='utf-8')

    # 跳过章节页（第NNN卷.md）
    fname = md_path.name
    if re.match(r'^第\d{3}卷\.md$', fname):
        return []

    new_text, changes = apply_patterns_protected(text, patterns)
    if not changes:
        return []

    if not dry_run:
        md_path.write_text(new_text, encoding='utf-8')

    return changes


def main():
    parser = argparse.ArgumentParser(description='H23: 合并地名+官名 wikilink')
    parser.add_argument('--limit', type=int, default=50, help='最多处理 N 个文件（默认50）')
    parser.add_argument('--dry-run', action='store_true', help='只报告，不写文件')
    parser.add_argument('--slug', help='只处理指定词条文件')
    args = parser.parse_args()

    geo_official = load_geo_official_pages()
    print(f'[H23] 地名+官名词条: {len(geo_official)} 个')
    patterns = build_patterns(geo_official)

    if args.slug:
        files = [resolve_page_file(PAGES_DIR, args.slug)]
    else:
        files = sorted(PAGES_DIR.rglob('*.md'))

    processed = 0
    total_changes = 0
    file_changes = []

    for md_path in files:
        if processed >= args.limit:
            break
        if not md_path.exists():
            print(f'[H23] 文件不存在: {md_path}', file=sys.stderr)
            continue
        changes = process_file(md_path, patterns, dry_run=args.dry_run)
        if changes:
            processed += 1
            n = sum(c for _, c in changes)
            total_changes += n
            labels = ', '.join(f'{lbl}×{c}' for lbl, c in changes)
            file_changes.append((md_path.stem, labels, n))
            marker = '[DRY]' if args.dry_run else '[FIX]'
            print(f'{marker} {md_path.stem}: {labels}')

    print(f'\n[H23] 完成: {processed} 个文件，{total_changes} 处替换'
          + (' (dry-run，未写入)' if args.dry_run else ''))
    return processed


if __name__ == '__main__':
    main()
