#!/usr/bin/env python3
"""
将《资治通鉴》原文按卷拆分，生成带 PN 标注的 wiki 页面。

输出格式：wiki/public/pages/第NNN卷.md
PN 格式：[NNN-PPP] 段落文本

用法：
    python3 wiki/scripts/import_volumes.py
    python3 wiki/scripts/import_volumes.py --dry-run
    python3 wiki/scripts/import_volumes.py --vol 1   # 只导入第1卷（测试）
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from page_bucket import page_bucket

# 中文数字转阿拉伯数字（处理卷号）
CN_DIGIT = {
    '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
}

def cn_to_int(s: str) -> int:
    """将中文数字（如"二百九十四"）转为整数。支持到999。"""
    s = s.strip()
    hundreds = 0
    tens = 0
    ones = 0
    if '百' in s:
        idx = s.index('百')
        h = s[:idx]
        hundreds = CN_DIGIT.get(h, 1) * 100
        s = s[idx + 1:]
    if '十' in s:
        idx = s.index('十')
        t = s[:idx]
        tens = CN_DIGIT.get(t, 1) * 10
        s = s[idx + 1:]
    if s:
        ones = CN_DIGIT.get(s[0], 0)
    return hundreds + tens + ones


# 匹配卷标题行
RE_VOLUME = re.compile(r'^[●　\s]*卷第([一二三四五六七八九十百零\d]+)')
# 匹配纪名行，如 【周纪一】
RE_JI = re.compile(r'【([^】]+)】')
# 匹配年号行（不含　　缩进），如 "威烈王二十三年"
RE_YEAR = re.compile(r'^[^\s　].*年$')


def parse_volumes(txt_path: Path) -> list[dict]:
    """
    解析原文，返回卷列表。
    每卷 = {
        'num': int,              # 卷号 1-294
        'title': str,            # 卷标题（如"卷第一"）
        'ji': str,               # 纪名（如"周纪一"）
        'lines': list[str],      # 正文行（去除前导空白但保留内容）
    }
    """
    raw = txt_path.read_text(encoding='utf-8')
    raw_lines = raw.splitlines()

    volumes = []
    current: dict | None = None

    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue

        # 检测卷标题
        m = RE_VOLUME.match(stripped)
        if m:
            if current:
                volumes.append(current)
            cn_num = m.group(1)
            # 尝试中文转数字
            try:
                num = int(cn_num)  # 若已是数字
            except ValueError:
                num = cn_to_int(cn_num)
            current = {
                'num': num,
                'title': f'卷第{cn_num}',
                'ji': '',
                'lines': [],
            }
            continue

        if current is None:
            continue  # 跳过卷之前的内容（书名等）

        # 检测纪名
        m_ji = RE_JI.search(stripped)
        if m_ji and not current['ji']:
            current['ji'] = m_ji.group(1)

        # 收集正文行
        current['lines'].append(stripped)

    if current:
        volumes.append(current)

    return volumes


def make_page(vol: dict) -> str:
    """生成单卷的 wiki 页面 Markdown。"""
    num = vol['num']
    nn = f'{num:03d}'
    title = vol['title']
    ji = vol['ji'] or ''
    lines = vol['lines']

    # 构建 frontmatter
    label = f'第{nn}卷'
    description = f'《资治通鉴》{title}'
    if ji:
        description += f'，{ji}'

    # 别名
    aliases = [f'第{num}卷', title]
    aliases_str = ', '.join(f'"{a}"' for a in aliases)

    frontmatter = f"""---
id: {label}
aliases: [{aliases_str}]
type: 章节
label: {label}
description: {description}
vol_num: {num}
vol_title: "{title}"
ji: "{ji}"
pn_prefix: "{nn}"
---"""

    # 标题行
    header = f'\n# [[{label}]]　{title}'
    if ji:
        header += f'　【{ji}】'

    # 正文：每行分配 PN
    body_lines = []
    pn = 1
    for line in lines:
        if not line:
            continue
        body_lines.append(f'\n[{nn}-{pn:03d}] {line}')
        pn += 1

    body = '\n'.join(body_lines)
    return frontmatter + header + '\n' + body + '\n'


def main():
    parser = argparse.ArgumentParser(description='导入《资治通鉴》原文到 wiki 页面')
    parser.add_argument('--dry-run', action='store_true', help='只解析不写文件')
    parser.add_argument('--vol', type=int, default=0, help='只导入指定卷号（调试用）')
    parser.add_argument('--force', action='store_true', help='覆盖已有页面')
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    txt_path = root / 'corpus' / 'raw' / '资治通鉴.txt'
    pages_dir = root / 'wiki' / 'public' / 'pages'

    if not txt_path.exists():
        print(f'✗ 找不到原文：{txt_path}', file=sys.stderr)
        sys.exit(1)

    print(f'[import] 解析原文: {txt_path}')
    volumes = parse_volumes(txt_path)
    print(f'[import] 共解析 {len(volumes)} 卷')

    if args.vol:
        volumes = [v for v in volumes if v['num'] == args.vol]
        if not volumes:
            print(f'✗ 未找到第 {args.vol} 卷', file=sys.stderr)
            sys.exit(1)

    created = skipped = 0
    for vol in volumes:
        nn = f'{vol["num"]:03d}'
        slug = f'第{nn}卷'
        bucket = page_bucket(slug)
        out_dir = pages_dir / bucket
        out_path = out_dir / f'{slug}.md'

        if out_path.exists() and not args.force:
            skipped += 1
            continue

        page = make_page(vol)

        if args.dry_run:
            print(f'[dry-run] 第{nn}卷 ({len(vol["lines"])} 段落)')
            continue

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(page, encoding='utf-8')
        created += 1
        if created % 50 == 0 or vol['num'] <= 5:
            print(f'[import] 第{nn}卷 → {out_path.name} ({len(vol["lines"])} 段落)')

    if not args.dry_run:
        print(f'[import] 完成：新建 {created} 卷，跳过 {skipped} 卷（已有）')
    else:
        print(f'[dry-run] 将新建 {len(volumes)} 卷')


if __name__ == '__main__':
    main()
