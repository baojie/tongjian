#!/usr/bin/env python3
"""
wikify_chapters.py — 在章节页（第???卷.md）中为「无对应页的人名」加 [[wikilink]]。

来源：扫描实体页面（非章节）中的 [[broken wikilinks]]，过滤为人名候选，
      然后在章节页中查找未标注的出现处并添加链接。

不修改原文文字，只添加 [[]] 标注。
章节页按 Append-Only 原则：不删除任何现有内容。

用法：
    python3 wiki/scripts/butler/wikify_chapters.py --dry-run
    python3 wiki/scripts/butler/wikify_chapters.py [--limit N]
"""
from __future__ import annotations

import re
import json
import sys
import subprocess
import time
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[3]
PAGES_DIR = ROOT / "wiki/public/pages"
REG_PATH = ROOT / "wiki/public/pages.json"
BUILD_REGISTRY = ROOT / "wiki/scripts/build_registry.py"
RECORD_REVISION = ROOT / "wiki/scripts/record_revision.py"

# ── 非人名排除词 ────────────────────────────────────────────────────────────
# 朝代/国家/地名/概念/官职/书名
NON_PERSON = {
    # 朝代/政权
    '北周', '北齐', '北魏', '东魏', '西魏', '北燕', '北凉', '北秦', '后赵', '前赵',
    '后燕', '前燕', '后秦', '前秦', '前凉', '后凉', '南凉', '西凉', '北汉',
    '后唐', '后梁', '后晋', '后汉', '后周', '南唐', '南汉', '前蜀', '后蜀',
    '东晋', '西晋', '南朝梁', '南朝宋', '南朝齐', '南朝陈', '曹魏',
    '西夏', '北宋', '东汉', '西汉', '新朝', '南北朝', '五代', '十六国',
    '麹氏高昌', '北匈奴', '南匈奴',
    # 地名
    '长安', '洛阳', '汉中', '南中', '安南', '湘州', '河西', '西域', '漠北',
    '关中', '荆州', '扬州', '益州', '幽州', '并州', '凉州', '徐州', '青州',
    # 概念/制度
    '科举', '藩镇', '北伐', '皮革', '算赋', '宗法', '继承', '君权', '相权',
    '宿儒', '魏晋', '汉代',
    # 书名
    '战国策', '唐律疏议',
    # 事件
    '八王之乱', '楚汉战争', '赤眉军', '乌桓',
    # 官职/尊称（无具体人名）
    '尚书台', '侍御史', '国子祭酒', '渤海太守', '武安侯', '庐陵王',
    '淮阳宪王', '成都王颖',
    # 帝号（通常已有页或已链接）
    '汉成帝', '汉哀帝', '汉惠帝', '汉顺帝', '汉安帝', '汉灵帝', '汉昭帝',
    '汉鲁恭王', '唐中宗', '唐敬宗', '晋元帝', '宣武帝', '赵悼襄王',
    # 其他明确非人名
    '罗马帝国', '皇位', '北伐', '西周', '东周',
    # 歧义词：在古文中兼做虚词/短语，不宜自动链接
    '子之', '王章', '法章', '周本', '刘良', '王嘉', '刘延', '张章',
    # 普通名词（被误入 broken-links 的）
    '国家', '民间', '政府', '朝廷', '社会', '经济', '文化', '军事',
    '皇室', '贵族', '官员', '百官', '士族', '豪族', '豪强',
    '军队', '诏书', '祭祀',
    # 制度/政策
    '推恩令', '五德终始', '少数民族',
    # 地理工程
    '都江堰', '郑国渠', '渤海国',
    # 破损书名片段
    '《资治通鉴',
    # 帝号（另有页）
    '唐武宗',
    # 书名/典籍
    '史记', '论语', '左传', '孙子兵法', '过秦论', '三国志', '汉书', '后汉书',
    '资治通鉴', '周礼', '仪礼', '礼记', '尚书', '诗经', '春秋', '易经',
    '庄子', '老子', '孟子', '荀子', '韩非子', '吕氏春秋', '国语',
    '战国策', '世说新语', '文选', '史通', '通典', '贞观政要',
    # 历史断代/组合期名
    '秦汉', '汉末', '隋唐', '武周', '南梁', '北汉', '东汉末', '魏晋南北朝',
    '先秦', '中唐', '晚唐', '初唐', '盛唐', '两汉', '三代',
    # 概念/制度
    '地支', '天干', '干支', '六部', '三省', '三省六部', '九品', '九品中正',
    '建筑', '冶铁', '铸铜', '漕运', '驿站', '均田', '租庸调', '两税',
    # 国家/地区
    '高丽', '新罗', '百济', '倭国', '日本', '天竺', '大食', '波斯',
    '林邑', '真腊', '室韦', '靺鞨', '铁勒', '柔然', '突厥', '回鹘',
    '吐蕃', '南诏', '渤海', '契丹', '党项', '女真',
    # 官职/制度术语
    '中书令', '门下省', '尚书省', '中书省', '御史台', '太常寺',
    '大将军', '车骑将军', '骠骑将军', '卫将军', '镇军将军', '大司马',
    # 地名（非人名）
    '虎牢关', '兖州', '广州', '泉州', '三吴', '泽潞', '安西四镇', '关陇集团',
    # 概念/通称
    '中央', '战乱', '外交', '官吏', '冀州刺史',
    # 朝代/割据政权
    '冉魏', '汉赵',
    # 时期
    '唐末',
    # 书籍
    '毛诗',
}

NON_PERSON_SUFFIXES = ('朝', '代', '帝国', '王朝', '战争', '起义', '之乱')

STOPWORDS = {
    '他', '她', '它', '的', '了', '是', '在', '有', '不', '也', '都', '而',
    '这', '那', '就', '被', '与', '对', '从', '为', '以', '上', '下', '中',
    '大', '小', '来', '去', '说', '道', '看', '见', '听', '知', '如',
    '其', '之', '或', '等', '自', '已', '又', '再', '更', '便', '却', '只',
    '资治通鉴', '司马光', '臣光',
}

WIKILINK_RE = re.compile(r'\[\[([^\]|]+?)(?:\|[^\]]+?)?\]\]')
EXISTING_LINK_RE = re.compile(r'\[\[[^\]]+\]\]')
FRONTMATTER_RE = re.compile(r'\A---\s*\n.*?\n---\s*\n', re.DOTALL)
SEE_ALSO_RE = re.compile(r'^## (参见|相关词条)$', re.MULTILINE)


def load_registry():
    data = json.loads(REG_PATH.read_text(encoding="utf-8"))
    return data["pages"]


def build_existing_terms(all_pages: dict) -> set[str]:
    """所有已有页的 label/alias/slug 集合。"""
    existing = set()
    for slug, meta in all_pages.items():
        existing.add(slug)
        label = meta.get("label", slug)
        existing.add(label)
        for a in meta.get("aliases", []):
            if isinstance(a, str):
                existing.add(a)
    return existing


def is_person_like(term: str, existing: set[str]) -> bool:
    """判断 broken wikilink target 是否像人名（没有对应页）。"""
    if term in existing:
        return False  # 已有页
    if term in NON_PERSON or term in STOPWORDS:
        return False
    for suf in NON_PERSON_SUFFIXES:
        if term.endswith(suf):
            return False
    if len(term) < 2 or len(term) > 5:
        return False
    return True


def collect_wanted_persons(all_pages: dict, existing: set[str]) -> list[str]:
    """从实体页面的 broken wikilinks 中收集人名候选。"""
    wanted: Counter = Counter()
    for md in PAGES_DIR.glob("*.md"):
        meta = all_pages.get(md.stem, {})
        if meta.get("type") == "章节":
            continue
        text = md.read_text(encoding="utf-8")
        body = FRONTMATTER_RE.sub('', text)
        for m in WIKILINK_RE.finditer(body):
            target = m.group(1).strip()
            if target.startswith(('Special:', 'Category:', '[')):
                continue
            if is_person_like(target, existing):
                wanted[target] += 1
    # 返回所有（按频次排序）
    return [term for term, _ in wanted.most_common()]


def make_link_pattern(terms: list[str]):
    """编译多词最长匹配正则。"""
    sorted_terms = sorted(terms, key=len, reverse=True)
    pattern = '|'.join(re.escape(t) for t in sorted_terms)
    return re.compile(pattern)


def add_links_to_segment(text: str, pattern: re.Pattern) -> str:
    """在不含 wikilink 的纯文本段落中添加链接（仅第一次出现）。"""
    result = []
    last = 0
    seen = set()
    for m in pattern.finditer(text):
        s, e = m.start(), m.end()
        result.append(text[last:s])
        word = m.group(0)
        if word not in seen:
            result.append(f'[[{word}]]')
            seen.add(word)
        else:
            result.append(word)
        last = e
    result.append(text[last:])
    return ''.join(result)


def wikify_chapter(content: str, pattern: re.Pattern) -> tuple[str, int]:
    """
    处理章节页内容：在 [NNN-PPP] 正文段中为未标注的人名添加链接。
    返回 (新内容, 新增链接数)。
    """
    # 截断到 ## 参见 之前
    see_also = SEE_ALSO_RE.search(content)
    process_end = see_also.start() if see_also else len(content)

    old_count = len(EXISTING_LINK_RE.findall(content[:process_end]))

    # 分割：frontmatter + body
    fm_match = FRONTMATTER_RE.match(content)
    if fm_match:
        frontmatter = content[:fm_match.end()]
        body = content[fm_match.end():]
        body_offset = fm_match.end()
    else:
        frontmatter = ''
        body = content
        body_offset = 0

    # 在 body 中逐段处理：跳过 [[...]] 内部、> 引用块、## 标题
    parts = []
    pos = 0
    # 找到所有"已有结构"的范围：wikilinks、blockquotes、headings
    SKIP_RE = re.compile(
        r'(\[\[[^\]]+\]\]'       # [[wikilink]]
        r'|^>.*$'                 # blockquote 行
        r'|^#{1,6}\s.*$'         # heading
        r'|`[^`]+`'              # inline code
        r')',
        re.MULTILINE
    )
    for skip in SKIP_RE.finditer(body):
        ss, se = skip.start(), skip.end()
        if ss > pos:
            segment = body[pos:ss]
            parts.append(add_links_to_segment(segment, pattern))
        parts.append(body[ss:se])
        pos = se
    if pos < len(body):
        parts.append(add_links_to_segment(body[pos:], pattern))

    new_body = ''.join(parts)
    new_content = frontmatter + new_body

    new_count = len(EXISTING_LINK_RE.findall(new_content[:process_end + (len(new_content) - len(content))]))
    added = max(0, new_count - old_count)
    return new_content, added


def main():
    dry_run = '--dry-run' in sys.argv
    limit = None
    for i, arg in enumerate(sys.argv):
        if arg == '--limit' and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    all_pages = load_registry()
    existing = build_existing_terms(all_pages)

    wanted_persons = collect_wanted_persons(all_pages, existing)
    print(f"[wikify-chapters] 收集到 {len(wanted_persons)} 个无页人名候选", file=sys.stderr)
    if not wanted_persons:
        print("无需处理。")
        return

    pattern = make_link_pattern(wanted_persons)

    # 取所有章节页
    chapter_slugs = sorted(
        slug for slug, meta in all_pages.items()
        if meta.get("type") == "章节"
    )
    if limit:
        chapter_slugs = chapter_slugs[:limit]

    print(f"[wikify-chapters] 处理 {len(chapter_slugs)} 个章节页"
          f"{' (DRY RUN)' if dry_run else ''}...", file=sys.stderr)

    modified = 0
    total_added = 0
    t0 = time.time()

    for i, slug in enumerate(chapter_slugs):
        path = PAGES_DIR / f"{slug}.md"
        if not path.exists():
            continue

        original = path.read_text(encoding="utf-8")
        new_content, added = wikify_chapter(original, pattern)

        if added == 0 or new_content == original:
            continue

        if not dry_run:
            path.write_text(new_content, encoding="utf-8")
            r = subprocess.run(
                [sys.executable, str(RECORD_REVISION), slug,
                 "--summary", "章节页：为无页人名添加 wikilinks",
                 "--author", "butler"],
                capture_output=True, text=True, cwd=ROOT,
            )
            if r.returncode != 0:
                print(f"  ✗ {slug}: {r.stderr.strip()[:80]}", file=sys.stderr)
                continue

        modified += 1
        total_added += added
        if dry_run and modified <= 5:
            # 展示前几个样例
            import difflib
            diff = list(difflib.unified_diff(
                original.splitlines()[:50], new_content.splitlines()[:50],
                lineterm='', n=1
            ))
            print(f"\n--- {slug} (+{added} links) ---")
            for line in diff[:20]:
                print(line)

        if (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 1
            eta = (len(chapter_slugs) - i - 1) / rate
            print(f"  [{i+1}/{len(chapter_slugs)}] {modified} modified, "
                  f"{total_added} links added, ~{eta:.0f}s left", file=sys.stderr)

    elapsed = time.time() - t0

    if not dry_run and modified > 0:
        print("  Rebuilding registry...", file=sys.stderr)
        subprocess.run(
            [sys.executable, str(BUILD_REGISTRY), str(PAGES_DIR),
             "--out", str(ROOT / "wiki/public/pages.json"),
             "--out-lite", str(ROOT / "wiki/public/pages.lite.json")],
            capture_output=True, text=True, cwd=ROOT,
        )

    print(f"\n[wikify-chapters] {'DRY RUN ' if dry_run else ''}完成：",
          f"{modified}/{len(chapter_slugs)} 卷修改，{total_added} 链接新增，{elapsed:.1f}s")


if __name__ == "__main__":
    main()
