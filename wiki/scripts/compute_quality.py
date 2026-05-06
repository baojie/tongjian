#!/usr/bin/env python3
"""
计算资治通鉴 Wiki 各页面的质量等级，并将 quality 字段写回 frontmatter。

等级定义（从低到高）：
  stub     - 存根：内容 < 100 字，或无 h2 节且 < 200 字
  basic    - 基础：< 500 字，或（h2 < 2 且 PN 引注 < 2）
  standard - 标准：有内容有结构，介于 basic 和 featured 之间
  featured - 精品：≥ 3 个 h2 节 + (PN≥3 或引文≥5) + 散文 ≥ 200 字
  premium  - 旗舰：有图 + ≥ 5 个 h2 节 + 散文 ≥ 1000 字 + (PN≥8 或引文≥8 或散文≥2000)

章节页（type=chapter）不参与评级，保持无 quality 字段。

用法：
    python3 wiki/scripts/compute_quality.py             # 写回所有页面
    python3 wiki/scripts/compute_quality.py --dry-run   # 只打印，不写文件
    python3 wiki/scripts/compute_quality.py --report    # 打印汇总报告
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = ROOT / 'public' / 'pages'

FRONTMATTER_RE = re.compile(r'\A---\s*\n(.*?)\n---\s*\n', re.DOTALL)
# PN 引注格式：（1-02-001） 全角括号
RE_PN = re.compile(r'（\d{3}-\d{3}）')
RE_H2 = re.compile(r'^## ', re.MULTILINE)
RE_BLOCKQUOTE = re.compile(r'^> ', re.MULTILINE)


def count_prose_chars(body: str) -> int:
    """统计散文字符数（跳过 frontmatter、标题、blockquote、代码块、空行）。"""
    total = 0
    in_code = False
    for line in body.splitlines():
        if line.startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        if line.startswith('#') or line.startswith('>') or line.startswith('|'):
            continue
        stripped = line.strip()
        if len(stripped) >= 20:  # 忽略短行（列表符号等）
            total += len(stripped)
    return total


def compute_level(front: dict, body: str) -> str:
    page_type = front.get('type', 'unknown')
    if page_type == 'chapter':
        return None  # 章节页不评级

    has_image = bool(front.get('image') or front.get('images'))
    h2_count = len(RE_H2.findall(body))
    pn_count = len(RE_PN.findall(body))
    quote_lines = len(RE_BLOCKQUOTE.findall(body))
    prose_chars = count_prose_chars(body)

    # stub
    if prose_chars < 100:
        return 'stub'
    if h2_count == 0 and prose_chars < 200:
        return 'stub'

    # basic
    if prose_chars < 500:
        return 'basic'
    if h2_count < 2 and pn_count < 2:
        return 'basic'

    # premium (检查最高级)
    if (has_image
            and h2_count >= 5
            and prose_chars >= 1000
            and (pn_count >= 8 or quote_lines >= 8 or prose_chars >= 2000)):
        return 'premium'

    # featured
    if (h2_count >= 3
            and (pn_count >= 3 or quote_lines >= 5)
            and prose_chars >= 200):
        return 'featured'

    return 'standard'


def compute_quality_score(front: dict, body: str) -> int:
    """综合评分，用于首页排序。"""
    has_image = bool(front.get('image') or front.get('images'))
    h2_count = len(RE_H2.findall(body))
    pn_count = len(RE_PN.findall(body))
    quote_lines = len(RE_BLOCKQUOTE.findall(body))
    prose_chars = count_prose_chars(body)
    wikilinks = len(re.findall(r'\[\[', body))
    tags = front.get('tags', [])

    score = 0
    score += min(h2_count * 3, 15)         # 结构分，最多 15
    score += min(pn_count * 2, 20)          # PN 引注，最多 20
    score += min(quote_lines, 10)           # 引文，最多 10
    score += min(prose_chars // 200, 15)    # 散文长度，最多 15
    score += min(wikilinks * 2, 10)         # wikilink 数，最多 10
    score += min(len(tags) * 2, 8)          # 标签，最多 8
    score += 10 if has_image else 0         # 有图 +10
    return score


def update_frontmatter(text: str, quality: str) -> tuple[str, bool]:
    """在 frontmatter 中写入/更新 quality 等级（不写 quality_score，该字段由 build_registry 动态计算）。"""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return text, False

    fm_str = m.group(1)
    rest = text[m.end():]

    # 移除旧的 quality / quality_score / featured 行
    lines = fm_str.splitlines()
    new_lines = [l for l in lines
                 if not re.match(r'^quality\s*:', l)
                 and not re.match(r'^quality_score\s*:', l)
                 and not re.match(r'^featured\s*:', l)]

    new_lines.append(f'quality: {quality}')

    new_fm = '\n'.join(new_lines)
    new_text = f'---\n{new_fm}\n---\n{rest}'
    return new_text, new_text != text


QUALITY_ORDER = ['stub', 'basic', 'standard', 'featured', 'premium']


def process_page(path: Path, dry_run: bool, upgrade_only: bool = True) -> tuple[str | None, int]:
    """返回 (quality_level, score)，quality_level=None 表示跳过。

    upgrade_only=True（默认）：只升级质量，不降级已手动设置的更高级别。
    """
    text = path.read_text(encoding='utf-8')
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, 0

    import yaml
    try:
        front = yaml.safe_load(m.group(1)) or {}
    except Exception:
        front = {}

    body = text[m.end():]
    level = compute_level(front, body)
    if level is None:
        return None, 0

    score = compute_quality_score(front, body)

    # upgrade_only: never downgrade a page that already has a higher quality set
    if upgrade_only:
        existing = front.get('quality', '')
        if (existing in QUALITY_ORDER and level in QUALITY_ORDER
                and QUALITY_ORDER.index(existing) > QUALITY_ORDER.index(level)):
            return existing, score  # keep existing higher quality

    new_text, changed = update_frontmatter(text, level)

    if changed and not dry_run:
        path.write_text(new_text, encoding='utf-8')

    return level, score


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--report', action='store_true', help='打印汇总报告')
    ap.add_argument('--allow-downgrade', action='store_true',
                    help='允许降级（默认只升级，不降低已手动设置的更高等级）')
    args = ap.parse_args()

    import yaml  # noqa: F401 — 确保可用

    counts: dict[str, int] = {}
    results: list[tuple[str, str, int]] = []

    pages = sorted(
        [p for p in PAGES_DIR.glob('*.md')
         if not (p.stem.startswith('第') and p.stem.endswith('回'))],
        key=lambda p: p.stem
    )

    upgrade_only = not getattr(args, 'allow_downgrade', False)
    for path in pages:
        level, score = process_page(path, args.dry_run, upgrade_only=upgrade_only)
        if level is None:
            continue
        counts[level] = counts.get(level, 0) + 1
        results.append((path.stem, level, score))

    order = ['premium', 'featured', 'standard', 'basic', 'stub']
    label = {'premium': '旗舰', 'featured': '精品', 'standard': '标准',
             'basic': '基础', 'stub': '存根'}

    if args.report or args.dry_run:
        print('\n质量分布：')
        for lvl in order:
            n = counts.get(lvl, 0)
            bar = '█' * min(n, 40)
            print(f'  {label[lvl]:4s} {bar} {n}')
        print()
        for stem, lvl, score in sorted(results, key=lambda x: (order.index(x[1]), -x[2])):
            print(f'  [{label[lvl]}] {stem}  (score={score})')
    else:
        for stem, lvl, score in results:
            print(f'  {stem}: {label[lvl]} (score={score})')

    action = '（dry-run）' if args.dry_run else '已写入'
    print(f'\n共处理 {len(results)} 个非章节页面 {action}')
    for lvl in order:
        if counts.get(lvl):
            print(f'  {label[lvl]}: {counts[lvl]}')


if __name__ == '__main__':
    main()
