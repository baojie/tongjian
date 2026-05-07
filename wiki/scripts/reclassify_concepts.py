#!/usr/bin/env python3
"""
reclassify_concepts.py — 将 concept 页面按 tags 重分类为细化类型。

优先级（高→低，先匹配先得）：
  law        [法律, 刑罚, 刑法, 刑戮, 刑辟, 刑名, 治狱]
  artifact   [器物, 兵器, 乐器, 车舆, 工具, 符节, 服饰, 纺织]
  astronomy  [天象, 天文, 星占, 历法, 祥瑞, 天人感应, 谶纬, 预言]
  ritual     [祭祀, 礼仪, 丧葬, 巡幸, 婚姻, 礼乐, 礼俗, 丧服, 风俗]
  economy    [经济, 货币, 赋税, 财政, 农业, 土地制度, 度量衡, 赋役,
              手工业, 畜牧, 交通, 水利, 工程]
  military   [军事, 战术, 兵制, 边防, 兵法, 后勤, 水军, 骑兵, 间谍,
              战国, 兵器（仅当无器物标签时）]
  institution 其余含 [制度] 标签的页面

不迁移：已经是 official/tribe/ritual/year/dynasty 等非 concept 的页面。

用法：
  python3 wiki/scripts/reclassify_concepts.py [--dry-run]
"""
from __future__ import annotations
import re, json, sys, subprocess
from pathlib import Path
from collections import defaultdict

ROOT      = Path(__file__).resolve().parents[1]   # wiki/
PAGES_DIR = ROOT / "public/pages"
REG_PATH  = ROOT / "public/pages.json"
RECORD    = ROOT / "scripts/record_revision.py"

# ── 优先级规则 ────────────────────────────────────────────────────
RULES: list[tuple[str, set[str]]] = [
    ("law", {
        "法律", "刑罚", "刑法", "刑戮", "刑辟", "刑名", "刑狱", "治狱",
        "刑罚", "妖言", "徒刑",
    }),
    ("artifact", {
        "器物", "兵器", "乐器", "车舆", "工具", "符节", "服饰", "纺织",
        "建筑", "仪仗",
    }),
    ("astronomy", {
        "天象", "天文", "星占", "历法", "祥瑞", "天人感应",
        "谶纬", "预言", "方术", "灾害",
    }),
    ("ritual", {
        "祭祀", "礼仪", "丧葬", "巡幸", "婚姻", "礼乐", "礼俗",
        "丧服", "风俗", "宗法", "宗室", "家族",
    }),
    ("economy", {
        "经济", "货币", "赋税", "财政", "农业", "土地制度", "度量衡",
        "赋役", "手工业", "畜牧", "交通", "水利", "工程", "户籍",
        "人口",
    }),
    ("military", {
        "军事", "战术", "兵制", "边防", "兵法", "后勤", "水军",
        "骑兵", "间谍", "兵器",
    }),
    ("institution", {
        "制度",
    }),
]


def target_type(tags: list[str]) -> str | None:
    tag_set = set(tags)
    for new_type, trigger_tags in RULES:
        if tag_set & trigger_tags:
            return new_type
    return None


def main():
    dry_run = "--dry-run" in sys.argv

    data    = json.loads(REG_PATH.read_text(encoding="utf-8"))
    pages   = data["pages"]

    counts: dict[str, int] = defaultdict(int)
    examples: dict[str, list[str]] = defaultdict(list)

    for md in sorted(PAGES_DIR.glob("*.md")):
        slug = md.stem
        meta = pages.get(slug, {})
        if meta.get("type") != "concept":
            continue

        tags    = meta.get("tags", [])
        new_type = target_type(tags)
        if not new_type:
            continue

        counts[new_type] += 1
        if len(examples[new_type]) < 5:
            examples[new_type].append(slug)

        if dry_run:
            continue

        text     = md.read_text(encoding="utf-8")
        new_text = re.sub(
            r'^type: concept$', f'type: {new_type}',
            text, flags=re.MULTILINE, count=1
        )
        if new_text == text:
            continue
        md.write_text(new_text, encoding="utf-8")
        subprocess.run(
            [sys.executable, str(RECORD), slug,
             "--summary", f"分类调整: concept→{new_type}",
             "--author", "butler"],
            capture_output=True, cwd=ROOT.parent,
        )

    print(f"{'[DRY RUN] ' if dry_run else ''}迁移结果：")
    total = 0
    for new_type, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        total += cnt
        print(f"  {new_type:12s} {cnt:4d}  例: {', '.join(examples[new_type])}")
    print(f"  {'─'*30}")
    print(f"  {'合计':12s} {total:4d}")


if __name__ == "__main__":
    main()
