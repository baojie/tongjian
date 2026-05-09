"""H24: 合并所有被拆开的复合词条 wikilink。

凡「A+B」是已知 wiki 词条，且正文中出现 [[A]][[B]]、[[A]]B 或 A[[B]] 三种拆写，
均合并为 [[A+B]]。

排除范围：已由 H23 处理的「地名+官名」（刺史/太守/节度使等）。

用法：
  python3 h24_merge_compound_wikilinks.py [--limit N] [--dry-run] [--slug SLUG]
"""

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT  = SCRIPT_DIR.parent.parent.parent
PAGES_DIR  = REPO_ROOT / 'wiki' / 'public' / 'pages'
PAGES_JSON = REPO_ROOT / 'docs' / 'wiki' / 'pages.json'

# H23 已处理的后缀，跳过避免重复
GEO_SUFFIXES = {
    '刺史','太守','节度使','都督','都护','都指挥使','留守','经略使',
    '观察使','防御使','团练使','招讨使','安抚使','转运使','提点',
    '知州','知府','县令','县尉','长史','司马','参军','别驾','从事','通判',
}

PROTECT_RE = re.compile(
    r'```[\s\S]*?```'
    r'|`[^`]+`'
    r'|^>.*$'
    r'|（\d{3}-\d{3}）'
    r'|\[\d{3}-\d{3}\]',
    re.MULTILINE,
)


def load_compound_splits():
    """返回 {label: (prefix, suffix)} 的复合词条字典（不含H23范围）。"""
    with open(PAGES_JSON) as f:
        pages = json.load(f)['pages']
    label_set = {(meta.get('label') or slug) for slug, meta in pages.items()}

    result = {}
    for label in label_set:
        if len(label) < 3:
            continue
        if any(label.endswith(s) for s in GEO_SUFFIXES):
            continue
        for i in range(1, len(label)):
            pref, suf = label[:i], label[i:]
            if pref in label_set and suf in label_set:
                result[label] = (pref, suf)
                break
    return result


def build_compiled_patterns(compound_splits):
    """预编译所有 pattern，返回 {label: (pref, suf, [re])}。"""
    compiled = {}
    for label, (pref, suf) in compound_splits.items():
        ep, es = re.escape(pref), re.escape(suf)
        compiled[label] = (pref, suf, [
            re.compile(rf'\[\[{ep}\]\]\[\[{es}\]\]'),
            re.compile(rf'\[\[{ep}\]\]{es}(?![\w一-鿿])'),
            re.compile(rf'(?<![\w一-鿿]){ep}\[\[{es}\]\]'),
        ])
    return compiled


def apply_patterns_protected(text, compiled):
    protected = []

    def protect(m):
        protected.append(m.group(0))
        return f'\x00p{len(protected)-1}\x00'

    safe = PROTECT_RE.sub(protect, text)

    changes = []
    for label, (pref, suf, pats) in compiled.items():
        repl = f'[[{label}]]'
        for pat in pats:
            new_safe, n = pat.subn(repl, safe)
            if n:
                changes.append((label, n))
                safe = new_safe
                break

    result = re.sub(r'\x00p(\d+)\x00', lambda m: protected[int(m.group(1))], safe)
    return result, changes


def process_file(md_path, compiled, dry_run=False):
    if re.match(r'^第\d{3}卷\.md$', md_path.name):
        return []
    text = md_path.read_text(encoding='utf-8')
    new_text, changes = apply_patterns_protected(text, compiled)
    if not changes:
        return []
    if not dry_run:
        md_path.write_text(new_text, encoding='utf-8')
    return changes


def main():
    parser = argparse.ArgumentParser(description='H24: 合并复合词条拆分 wikilink')
    parser.add_argument('--limit',   type=int, default=50)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--slug',    help='只处理指定词条文件')
    args = parser.parse_args()

    compound = load_compound_splits()
    print(f'[H24] 复合词条: {len(compound)} 个')
    compiled = build_compiled_patterns(compound)

    files = ([PAGES_DIR / f'{args.slug}.md'] if args.slug
             else sorted(PAGES_DIR.glob('*.md')))

    processed = total = 0
    for md_path in files:
        if processed >= args.limit:
            break
        if not md_path.exists():
            print(f'[H24] 不存在: {md_path}', file=sys.stderr)
            continue
        changes = process_file(md_path, compiled, dry_run=args.dry_run)
        if changes:
            processed += 1
            n = sum(c for _, c in changes)
            total += n
            labels = ', '.join(f'{l}×{c}' for l, c in changes)
            print(f'{"[DRY]" if args.dry_run else "[FIX]"} {md_path.stem}: {labels}')

    print(f'\n[H24] 完成: {processed} 个文件，{total} 处替换'
          + (' (dry-run)' if args.dry_run else ''))


if __name__ == '__main__':
    main()
