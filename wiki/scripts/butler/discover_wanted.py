#!/usr/bin/env python3
"""
发现待创建页面：优先找 broken wikilinks，若不足则从章节频率中发现。

两阶段策略：
  Phase 1: 扫描所有 [[wikilink]] 找无对应页的 broken links（引用驱动）
  Phase 2: 若 Phase 1 结果不足，扫描章节页面高频词（语料驱动）

用法:
    python3 wiki/scripts/butler/discover_wanted.py [--top N]
    python3 wiki/scripts/butler/discover_wanted.py --json
    python3 wiki/scripts/butler/discover_wanted.py --corpus-only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
PAGES_DIR = ROOT / 'wiki' / 'public' / 'pages'

WIKILINK_RE = re.compile(r'\[\[([^\[\]|]+?)(?:\|[^\[\]]+?)?\]\]')
FRONTMATTER_RE = re.compile(r'\A---\s*\n.*?\n---\s*\n', re.DOTALL)

# 人名/词条候选高频词的过滤：忽略通用词
STOPWORDS = {
    '他', '她', '它', '的', '了', '是', '在', '有', '不', '也', '都', '而',
    '这', '那', '就', '被', '与', '对', '从', '为', '以', '上', '下', '中',
    '大', '小', '来', '去', '说', '道', '看', '见', '听', '知', '如',
    '其', '之', '或', '等', '自', '已', '又', '再', '更', '便', '却', '只',
    '资治通鉴', '司马光',  # 项目本身不建词条
}


def load_page_ids(pages_root: Path) -> set[str]:
    ids: set[str] = set()
    for f in pages_root.rglob('*.md'):
        pid = str(f.relative_to(pages_root).with_suffix(''))
        ids.add(pid)
        text = f.read_text(encoding='utf-8')
        m = re.match(r'\A---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
        if m and yaml:
            try:
                front = yaml.safe_load(m.group(1)) or {}
                label = front.get('label', '')
                if label:
                    ids.add(label)
                for alias in (front.get('aliases') or []):
                    if isinstance(alias, str):
                        ids.add(alias)
            except Exception:
                pass
    return ids


def scan_broken_links(pages_root: Path, top: int) -> list[tuple[str, int]]:
    """扫描所有页面的 broken wikilink，按引用次数排序。"""
    existing = load_page_ids(pages_root)
    wanted: Counter = Counter()
    for f in pages_root.rglob('*.md'):
        text = f.read_text(encoding='utf-8')
        body = FRONTMATTER_RE.sub('', text)
        for m in WIKILINK_RE.finditer(body):
            target = m.group(1).strip()
            if target not in existing and target not in STOPWORDS:
                wanted[target] += 1
    return wanted.most_common(top)


def scan_chapter_entities(pages_root: Path, top: int, min_freq: int = 3) -> list[tuple[str, int]]:
    """从章节页面提取高频人名/地名候选（章节页面中不含 wikilink，直接扫描文本）。"""
    existing = load_page_ids(pages_root)
    freq: Counter = Counter()

    # 扫描章节页面（第NNN回.md）
    for f in sorted(pages_root.rglob('第*.md')):
        text = f.read_text(encoding='utf-8')
        body = FRONTMATTER_RE.sub('', text)
        # 简单的2-4字词提取（中文名字长度）
        for word in re.findall(r'[一-鿿]{2,4}', body):
            if word not in existing and word not in STOPWORDS:
                freq[word] += 1

    return [(w, c) for w, c in freq.most_common(top * 5) if c >= min_freq][:top]


def main():
    ap = argparse.ArgumentParser(description='发现资治通鉴待创建词条')
    ap.add_argument('--pages', default=str(PAGES_DIR))
    ap.add_argument('--top', type=int, default=30)
    ap.add_argument('--min-freq', type=int, default=3)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--corpus-only', action='store_true', help='只做章节频率扫描')
    args = ap.parse_args()

    pages_root = Path(args.pages)

    results = []

    if not args.corpus_only:
        broken = scan_broken_links(pages_root, args.top)
        for slug, count in broken:
            results.append({'slug': slug, 'count': count, 'source': 'broken-link'})

    if len(results) < args.top:
        need = args.top - len(results)
        existing_slugs = {r['slug'] for r in results}
        corpus_cands = scan_chapter_entities(pages_root, need * 2, args.min_freq)
        for slug, count in corpus_cands:
            if slug not in existing_slugs:
                results.append({'slug': slug, 'count': count, 'source': 'corpus-freq'})
                if len(results) >= args.top:
                    break

    if args.json:
        print(json.dumps(results[:args.top], ensure_ascii=False, indent=2))
    else:
        print(f"发现 {len(results)} 个待建词条：\n")
        for r in results[:args.top]:
            src = r['source']
            print(f"  [{r['count']:3d}] {r['slug']:<20s} ({src})")


if __name__ == '__main__':
    main()
