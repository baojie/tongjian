#!/usr/bin/env python3
"""
从《资治通鉴》卷页检索包含关键词的段落，输出 PN 引文编号。

卷页格式（wiki/public/pages/第NNN卷.md）：
    [NNN-PPP] 段落文本…

用法:
    python3 wiki/scripts/butler/corpus_search.py 赵襄子 --max 10
    python3 wiki/scripts/butler/corpus_search.py 智伯 --vol 1 --max 5
    python3 wiki/scripts/butler/corpus_search.py 韩信 --vol 8 --vol 9 --max 20
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
PAGES_DIR = ROOT / 'wiki' / 'public' / 'pages'

RE_PN_LINE = re.compile(r'^\[(\d{3})-(\d{3})\]\s*(.*)')


def load_vol_paragraphs(vol_path: Path) -> list[tuple[str, str]]:
    """解析卷页面，返回 [(pn_label, para_text), ...] 列表。"""
    text = vol_path.read_text(encoding='utf-8')
    text = re.sub(r'^---\n.*?\n---\n', '', text, flags=re.DOTALL)

    pairs: list[tuple[str, str]] = []
    current_pn: str | None = None
    current_lines: list[str] = []

    def flush():
        nonlocal current_pn, current_lines
        if current_pn and current_lines:
            combined = ' '.join(current_lines).strip()
            if combined:
                pairs.append((current_pn, combined))
        current_pn = None
        current_lines = []

    for line in text.splitlines():
        line_s = line.strip()
        if not line_s:
            continue
        if line_s.startswith('#'):
            flush()
            continue
        m = RE_PN_LINE.match(line_s)
        if m:
            flush()
            vol_n, para_n, rest = m.group(1), m.group(2), m.group(3)
            current_pn = f'{vol_n}-{para_n}'
            if rest.strip():
                current_lines = [rest.strip()]
            else:
                current_lines = []
        else:
            if current_pn is not None:
                current_lines.append(line_s)

    flush()
    return pairs


def highlight(text: str, keyword: str) -> str:
    """在文本中用【】标出关键词。"""
    return text.replace(keyword, f'【{keyword}】')


def search(keyword: str, vol_nums: list[int] | None = None,
           max_results: int = 20) -> list[tuple[str, str]]:
    """
    搜索关键词，返回 [(pn_label, snippet), ...] 列表。
    pn_label 格式：NNN-PPP
    snippet：含【关键词】标注的段落截取（前后各 40 字）
    """
    results = []

    if vol_nums:
        vol_paths = []
        for n in vol_nums:
            # 搜索 bucket 子目录
            for p in PAGES_DIR.rglob(f'第{n:03d}卷.md'):
                vol_paths.append(p)
                break
        vol_paths = sorted(vol_paths)
    else:
        vol_paths = sorted(PAGES_DIR.rglob('第???卷.md'))

    for vp in vol_paths:
        for pn, para in load_vol_paragraphs(vp):
            if keyword in para:
                # 截取关键词周围 80 字
                idx = para.index(keyword)
                start = max(0, idx - 40)
                end = min(len(para), idx + len(keyword) + 40)
                snippet = para[start:end]
                if start > 0:
                    snippet = '…' + snippet
                if end < len(para):
                    snippet = snippet + '…'
                snippet = highlight(snippet, keyword)
                results.append((pn, snippet))
                if len(results) >= max_results:
                    return results

    return results


def main():
    parser = argparse.ArgumentParser(description='搜索《资治通鉴》原文段落')
    parser.add_argument('keyword', help='搜索关键词')
    parser.add_argument('--vol', type=int, action='append', dest='vols',
                        help='限定卷号（可多次指定）')
    parser.add_argument('--max', type=int, default=20, help='最大结果数（默认20）')
    parser.add_argument('--pn-only', action='store_true', help='只输出 PN 编号')
    args = parser.parse_args()

    results = search(args.keyword, vol_nums=args.vols, max_results=args.max)

    if not results:
        print(f'未找到包含"{args.keyword}"的段落', file=sys.stderr)
        sys.exit(1)

    for pn, snippet in results:
        if args.pn_only:
            print(pn)
        else:
            print(f'（{pn}）{snippet}')


if __name__ == '__main__':
    main()
