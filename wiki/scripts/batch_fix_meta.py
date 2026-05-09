#!/usr/bin/env python3
"""
batch_fix_meta.py — 批量填充 Wiki 页面缺失的 frontmatter 字段

当前支持：
- dynasty: 通过 tags → dynasty 映射推断（仅对含明确朝代标签的页面）

用法：
    python3 wiki/scripts/batch_fix_meta.py                     # 全量处理
    python3 wiki/scripts/batch_fix_meta.py --dry-run           # 预览，不写入
    python3 wiki/scripts/batch_fix_meta.py --limit 50          # 限前 50 页
    python3 wiki/scripts/batch_fix_meta.py --slug 琉璃          # 只处理指定页
"""

import os, re, sys, argparse

# ── 高置信度 tag → dynasty 映射 ──────────────────────────────
# 来源：通过分析已有页面中 tags 与 dynasty 的对应关系（>=80% 一致性）
TAG_DYNASTY = {
    # 主要朝代
    "西汉": "西汉", "东汉": "东汉", "唐": "唐", "战国": "战国",
    "周": "周", "五代十国": "五代十国", "三国": "三国",
    "东晋": "东晋", "西晋": "西晋", "秦": "秦", "南北朝": "南北朝",
    "隋": "隋", "新朝": "新朝", "十六国": "十六国", "春秋": "春秋",
    "汉": "汉", "晋": "晋", "北魏": "北魏",
    # 朝代别名
    "唐朝": "唐", "隋朝": "隋", "秦朝": "秦", "汉代": "汉", "唐代": "唐",
    # 跨时期
    "先秦": "先秦", "秦汉": "秦汉", "魏晋": "魏晋", "隋唐": "隋唐",
    "南朝": "南朝", "北朝": "北朝",
    # 细分南北朝
    "三国魏": "三国魏", "南北朝宋": "南北朝宋", "南北朝梁": "南北朝梁",
    "南北朝齐": "南北朝齐", "南北朝陈": "南北朝陈",
    "刘宋": "南北朝", "南梁": "南北朝", "南陈": "南北朝", "南齐": "南北朝",
    "南朝陈": "南北朝", "南朝齐": "南北朝",
    # 五代十国细分
    "后梁": "后梁", "后唐": "后唐", "后晋": "后晋",
    "后汉": "后汉", "后周": "后周",
    # 十六国细分
    "前秦": "前秦", "前燕": "前燕", "后凉": "十六国",
    "前赵": "十六国", "北燕": "十六国",
    "冉魏": "十六国", "前凉": "十六国", "成汉": "十六国",
    "南凉": "十六国", "西秦": "十六国", "西凉": "十六国",
    # 注意: "夏" 已移除（歧义：夏朝 vs 十六国·夏）
    # 南北朝政权
    "北齐": "北齐", "北周": "北周",
    # 唐+五代十国分支
    "南唐": "五代十国", "前蜀": "五代十国", "后蜀": "五代十国",
    "南吴": "五代十国", "北汉": "五代十国", "十国": "五代十国",
    # 唐代周边/分期
    "南诏": "唐", "吐蕃": "唐", "回鹘": "唐", "回纥": "唐",
    "武周": "唐", "中唐": "唐", "晚唐": "唐",
    # 战国七雄
    "秦国": "战国", "赵国": "战国", "魏国": "战国",
    "韩国": "战国", "楚国": "战国", "燕国": "战国", "齐国": "战国",
    # 特定三国
    "蜀汉": "三国",
    # 事件→朝代
    "安史之乱": "唐", "八王之乱": "西晋",
    "淝水之战": "东晋", "七国之乱": "西汉",
    "丝绸之路": "西汉", "丝路": "西汉",
}

PAGES_DIR = os.path.join(os.path.dirname(__file__), "..", "public", "pages")
PAGES_DIR = os.path.normpath(PAGES_DIR)

# 正则
RE_DYNASTY = re.compile(r"^dynasty:\s*(.+)$", re.MULTILINE)
RE_TYPE = re.compile(r"^type:\s*(.+)$", re.MULTILINE)
RE_CAT = re.compile(r"^cat:\s*(.+)$", re.MULTILINE)
RE_TAGS_INLINE = re.compile(r"^tags:\s*\[(.*?)\]$", re.MULTILINE)
RE_TAGS_BLOCK = re.compile(r"^tags:\s*\n((?:\s+-\s+.+\n?)+)", re.MULTILINE)


def parse_tags(content: str) -> list[str]:
    """从 frontmatter 中提取 tags"""
    m = RE_TAGS_INLINE.search(content)
    if m:
        return [t.strip().strip("\"").strip("'") for t in m.group(1).split(",") if t.strip()]
    m = RE_TAGS_BLOCK.search(content)
    if m:
        return [t.strip().strip("-").strip() for t in m.group(1).split("\n") if t.strip()]
    return []


def infer_dynasty_from_tags(tags: list[str]) -> str | None:
    """通过 tag→dynasty 映射推断朝代"""
    for tag in tags:
        if tag in TAG_DYNASTY:
            return TAG_DYNASTY[tag]
    return None


def add_dynasty_to_frontmatter(content: str, dynasty: str) -> str:
    """在 frontmatter 中插入 dynasty 字段"""
    front_end = content.index("---", 3)  # 第二个 ---
    front = content[:front_end + 3]
    body = content[front_end + 3:]

    # 检查是否已有 dynasty
    if RE_DYNASTY.search(front):
        return content  # 已有，不修改

    # 插入位置：有 cat 则在 cat 之后，否则在 type 之后
    insert_after = None
    cm = RE_CAT.search(front)
    if cm:
        insert_after = cm.group(0)
    else:
        tm = RE_TYPE.search(front)
        if tm:
            insert_after = tm.group(0)

    if insert_after:
        new_front = front.replace(insert_after, insert_after + f"\ndynasty: {dynasty}", 1)
    else:
        # fallback: 在 --- 前插入
        new_front = front.replace("---", f"dynasty: {dynasty}\n---")

    return new_front + body


def process_page(slug: str, dry_run: bool = False) -> dict:
    """处理单个页面，返回操作结果"""
    fname = f"{slug}.md"
    path = os.path.join(PAGES_DIR, fname)
    if not os.path.exists(path):
        return {"slug": slug, "status": "not_found"}

    # 跳过章节页
    if slug.startswith("第") and slug.endswith("卷"):
        return {"slug": slug, "status": "skipped_chapter"}

    with open(path) as f:
        content = f.read()

    # 已有 dynasty
    if RE_DYNASTY.search(content):
        return {"slug": slug, "status": "already_has"}

    tags = parse_tags(content)
    dynasty = infer_dynasty_from_tags(tags)

    if not dynasty:
        return {"slug": slug, "status": "no_match", "tags": tags}

    new_content = add_dynasty_to_frontmatter(content, dynasty)
    if new_content == content:
        return {"slug": slug, "status": "unchanged"}

    if not dry_run:
        with open(path, "w") as f:
            f.write(new_content)

    return {"slug": slug, "status": "fixed", "dynasty": dynasty, "tags": tags}


def main():
    parser = argparse.ArgumentParser(description="批量填充缺失的 frontmatter 字段")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不写入")
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 页")
    parser.add_argument("--slug", type=str, default=None, help="只处理指定词条")
    args = parser.parse_args()

    slugs_to_process = []
    if args.slug:
        slugs_to_process = [args.slug]
    else:
        for fname in sorted(os.listdir(PAGES_DIR)):
            if fname.endswith(".md"):
                slugs_to_process.append(fname[:-3])
        if args.limit > 0:
            slugs_to_process = slugs_to_process[:args.limit]

    # 统计
    counts = {"fixed": 0, "already_has": 0, "skipped_chapter": 0, "no_match": 0, "not_found": 0, "unchanged": 0}
    fixed_pages = []

    for slug in slugs_to_process:
        result = process_page(slug, dry_run=args.dry_run)
        counts[result["status"]] = counts.get(result["status"], 0) + 1
        if result["status"] == "fixed":
            fixed_pages.append(result)
            tag_str = ",".join(result.get("tags", []))
            print(f"  ✓ {slug:20s} → dynasty: {result['dynasty']:10s}  tags=[{tag_str}]")

    print(f"\n{'='*60}")
    print(f"结果统计{'（预览模式）' if args.dry_run else ''}:")
    print(f"  ✓ 已填充:    {counts['fixed']}")
    print(f"  - 已有dynasty: {counts['already_has']}")
    print(f"  - 章节页跳过: {counts['skipped_chapter']}")
    print(f"  - 无法推断:  {counts['no_match']}（跨朝代概念）")
    print(f"  - 未找到:    {counts['not_found']}")
    print(f"{'='*60}")
    print(f"合计处理 {sum(counts.values())} 页，填充 {counts['fixed']} 页")


if __name__ == "__main__":
    main()
