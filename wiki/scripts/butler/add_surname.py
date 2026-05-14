#!/usr/bin/env python3
"""
为所有人物页面推断并添加 surname 字段，然后创建姓氏索引页面。

规则：
  - 先秦人物（战国及以前）优先使用氏，不知氏则用姓
  - 秦汉及以后人物用姓（即名字首字符）

用法：
    # 预览（不改写文件）
    python3 wiki/scripts/butler/add_surname.py --dry-run

    # 执行：追加 surname 到人物页 frontmatter
    python3 wiki/scripts/butler/add_surname.py --apply

    # 执行并创建姓氏页面
    python3 wiki/scripts/butler/add_surname.py --apply --create-pages
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# butler/ → scripts → wiki → root
ROOT = Path(__file__).resolve().parent.parent.parent.parent
PAGES = ROOT / "wiki/public/pages"

# ── 已知多字姓氏（按长度降序，优先匹配长姓氏） ──
MULTI_CHAR_SURNAMES = sorted([
    "万俟", "上官", "司马", "司徒", "司空", "宇文", "尉迟", "长孙", "慕容", "贺兰", "独孤",
    "拓跋", "呼延", "沮渠", "段干", "百里", "东郭", "西门", "南宫",
    "公孙", "诸葛", "夏侯", "欧阳", "皇甫", "公冶", "公西", "端木", "颛孙",
    "漆雕", "钟离", "澹台", "羊舌", "左丘", "仲孙", "叔孙", "季孙",
    "司寇", "梁丘", "即墨", "闾丘", "谷梁", "夹谷", "亓官",
    "鲜于", "申屠", "第五", "哥舒", "可汗",
    "阿史那", "仆固", "执失", "契苾", "阿跌", "达奚", "宇文", "慕容",
    "豆卢", "库狄", "若干", "侯莫陈", "破六韩", "乙弗", "乙速孤",
    "达步干", "莫多娄", "莫折", "费也头", "綦连", "贺拔", "尔朱",
    "大野", "叱罗", "叱干", "郁久闾", "可朱浑", "纥豆陵", "步大汗",
    "大莫干", "吐万", "纥干", "吐谷浑", "慕容", "赫连",
], key=len, reverse=True)

# ── 已知复姓 2 字（已包含在上面的列表中，此列表用于快速判断）──
SURNAME_2_SET = {s for s in MULTI_CHAR_SURNAMES if len(s) == 2}
SURNAME_3_SET = {s for s in MULTI_CHAR_SURNAMES if len(s) >= 3}

# ── 先秦/战国人物 氏→姓 映射 ──
# 对于先秦人物，部分人的"氏"与名字首字不同。
# 格式：页面名 → 氏（用作 surname 字段值）
PRE_QIN_CLAN = {
    # 姬姓诸侯
    "公子成":    "姬",
    "公子章":    "姬",
    "公子虔":    "姬",
    "公子卬":    "姬",
    "公子华":    "姬",
    "公子兰":    "姬",
    "公子无忌":  "姬",  # 信陵君
    "太子丹":    "姬",
    "太子建":    "芈",
    "太子商臣":  "芈",
    # 嬴姓
    "秦始皇":    "嬴",
    "嬴政":      "嬴",
    "嬴渠梁":    "嬴",  # 秦孝公
    "嬴驷":      "嬴",  # 秦惠文王
    "嬴稷":      "嬴",  # 秦昭襄王
    "嬴异人":    "嬴",  # 秦庄襄王
    "嬴胡亥":    "嬴",  # 秦二世
    "嬴子婴":    "嬴",
    # 芈姓
    "宣太后":    "芈",
    "屈原":      "芈",
    "屈匄":      "芈",
    "屈平":      "芈",
    # 子姓
    "孔子":      "孔",  # 子姓，孔氏
    "孔丘":      "孔",
    "宋康王":    "子",
    # 姒姓
    "杞梁":      "姒",
    # 妫姓/陈姓
    "陈完":      "妫",
    "陈轸":      "妫",
    # 其他复姓或特殊氏
    "扁鹊":      "秦",  # 秦氏，名越人
    "商鞅":      "公孙",  # 姬姓，公孙氏，卫氏
    "卫鞅":      "公孙",
    "公孙鞅":    "公孙",
    "孟尝君":    "田",  # 妫姓，田氏
    "春申君":    "芈",  # 芈姓，黄氏
    "平原君":    "嬴",  # 嬴姓，赵氏
    "信陵君":    "姬",  # 姬姓，魏氏
    "文信侯":    "吕",  # 吕不韦
    "安陵君":    "姬",  # 魏国封君
    "龙阳君":    "姬",
    "冯驩":      "冯",
    "冯谖":      "冯",
    "尹鐸":      "尹",
    "新垣衍":    "新垣",  # 复姓
    "樗里疾":    "樗里",  # 复姓
    "司马穰苴":  "司马",
    "微子启":    "微",  # 子姓，微氏
    "伯夷":      "墨",  # 一说墨胎氏
    "叔齐":      "墨",
    # 越国
    "勾践":      "姒",
    "无疆":      "姒",
    # 吴国
    "阖闾":      "姬",
    "夫差":      "姬",
    "吴王僚":    "姬",
    "季札":      "姬",
    # 孔子弟子
    "子路":      "仲",    # 仲由，氏仲
    "子贡":      "端木",  # 端木赐
    "子贡":      "端木",  # 端木赐
    "子夏":      "卜",    # 卜商
    "子张":      "颛孙",  # 颛孙师
    "子张":      "颛孙",  # 颛孙师
    "曾子":      "曾",    # 姒姓，曾氏
    "曾参":      "曾",
    "颜回":      "颜",
    "子思":      "孔",
    "孟子":      "孟",  # 姬姓，孟氏
    "孟轲":      "孟",
    "荀子":      "荀",  # 荀况
    "荀况":      "荀",
    "老子":      "李",  # 李耳
    "老子聃":    "李",
    "庄周":      "庄",
    "庄子":      "庄",
    "墨子":      "墨",  # 墨翟
    "墨翟":      "墨",
    "韩非":      "韩",  # 姬姓，韩氏
    "韩非子":    "韩",
    "孙武":      "孙",  # 妫姓，孙氏
    "孙膑":      "孙",
    "吴起":      "吴",  # 吴起，卫国人，氏吴
    "乐毅":      "乐",
    "乐羊":      "乐",
    "乐乘":      "乐",
    "乐闲":      "乐",
    "廉颇":      "廉",
    "蔺相如":    "蔺",
    "赵奢":      "嬴",  # 嬴姓，赵氏
    "赵括":      "嬴",
    "赵胜":      "嬴",  # 平原君
    "赵雍":      "嬴",  # 赵武灵王
    "赵盾":      "嬴",
    "赵衰":      "嬴",
    "赵鞅":      "嬴",
    "赵无恤":    "嬴",
    "赵朔":      "嬴",
    "赵武":      "嬴",
    "屠岸贾":    "屠岸",
}

# ── 不适合建立姓氏页面的人物类型 ──
# 如以封号/谥号/称号为页面名的人物，不是真正的姓氏
TITLE_PREFIXES = ("公子", "公主", "太子", "王子", "王孙", "皇帝", "太上皇")

# ── 标题式页面名 → 实际姓氏映射（用封号/称号而非真名的情况）──
TITLE_SURNAMES = {
    "信陵君":    "魏",
    "孟尝君":    "田",
    "平原君":    "赵",
    "春申君":    "黄",
    "安陵君":    "魏",
    "龙阳君":    "魏",
    "文信侯":    "吕",
    "宣太后":    "芈",
    "扁鹊":      "秦",
    "秦始皇":    "嬴",
    "孔子":      "孔",
    "孟子":      "孟",
    "孟子":      "孟",
    "荀子":      "荀",
    "庄子":      "庄",
    "老子":      "李",
    "墨子":      "墨",
    "韩非子":    "韩",
    "孙子":      "孙",
}

# ── 已知的显式姓氏（直接指定，覆盖自动推断）──
KNOWN_SURNAMES: dict[str, str] = {}
KNOWN_SURNAMES.update(PRE_QIN_CLAN)
KNOWN_SURNAMES.update(TITLE_SURNAMES)


def extract_surname(name: str) -> str | None:
    """从人物名称中提取姓氏/氏。"""
    # 已知映射优先
    if name in KNOWN_SURNAMES:
        return KNOWN_SURNAMES[name]

    # 跳过标题式前缀
    for prefix in TITLE_PREFIXES:
        if name.startswith(prefix) and len(name) > len(prefix):
            # 保留后面的部分再提取
            rest = name[len(prefix):]
            if rest in KNOWN_SURNAMES:
                return KNOWN_SURNAMES[rest]
            # 从后面的部分提 surname
            return extract_surname(rest)

    # 尝试匹配多字姓氏
    for s in MULTI_CHAR_SURNAMES:
        if name.startswith(s):
            return s

    # 如果是 2 字名，取第一个字为姓
    if len(name) >= 1:
        return name[0]

    return None


def parse_frontmatter(text: str) -> dict:
    m = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return {}
    try:
        import yaml
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}


def rebuild_frontmatter(text: str, updates: dict) -> str:
    """在 frontmatter 中追加或更新字段，保持已有字段不变。"""
    m = re.match(r"\A(---\s*\n)(.*?)(\n---)", text, re.DOTALL)
    if not m:
        return text

    prefix = m.group(1)
    fm_body = m.group(2)
    suffix = m.group(3)
    rest = text[m.end():]

    # 解析已有 frontmatter
    try:
        import yaml
        fm = yaml.safe_load(fm_body) or {}
    except Exception:
        fm = {}

    changed = False
    for k, v in updates.items():
        if fm.get(k) != v:
            fm[k] = v
            changed = True

    if not changed:
        return text

    # 重新序列化为 YAML，控制格式
    lines = fm_body.split("\n")
    # 找到插入点：在最后一项之前或之后，保持现有格式
    # 简单方式：在 category 类字段后追加
    insert_before = None
    for i, line in enumerate(lines):
        stripped = line.rstrip()
        if stripped.startswith("quality:") or stripped.startswith("featured:") or stripped.startswith("image:"):
            insert_before = i

    # 在现有 frontmatter 基础上重建
    # 保留原有所有行，在末尾或指定位置前插入新字段
    new_lines = list(lines)

    # 新字段如果已存在则替换，否则追加
    for k, v in updates.items():
        found = False
        for i, line in enumerate(lines):
            if line.rstrip().startswith(k + ":"):
                new_lines[i] = f"{k}: {v}"
                found = True
                break
        if not found:
            # 追加到 frontmatter 末尾
            if insert_before is not None:
                new_lines.insert(insert_before, f"{k}: {v}")
            else:
                new_lines.append(f"{k}: {v}")

    new_fm = "\n".join(new_lines)
    return prefix + new_fm + suffix + rest


def add_surname_to_frontmatter(text: str, surname: str) -> str:
    """向 frontmatter 添加 surname 字段。"""
    return rebuild_frontmatter(text, {"surname": surname})


def get_page_type(front: dict) -> str:
    return front.get("type", "")


def main():
    ap = argparse.ArgumentParser(description="为人物页面添加 surname 字段")
    ap.add_argument("--dry-run", action="store_true", help="仅预览，不改写文件")
    ap.add_argument("--apply", action="store_true", help="执行改写")
    ap.add_argument("--fix", action="store_true", help="修正已存在的错误 surname（如公孙被误判为公）")
    ap.add_argument("--create-pages", action="store_true", help="创建姓氏页面")
    args = ap.parse_args()

    if not args.dry_run and not args.apply:
        print("请指定 --dry-run（预览）或 --apply（执行）")
        sys.exit(1)

    # 扫描所有人物页面
    person_pages = []
    surname_counts = {}
    no_surname = []
    multi_char_surnames_found = set()

    for md_file in sorted(PAGES.glob("*.md")):
        pid = md_file.stem
        text = md_file.read_text(encoding="utf-8")
        front = parse_frontmatter(text)
        ptype = front.get("type", "")
        if ptype != "人物":
            continue

        person_pages.append((pid, md_file, text, front))

    print(f"共扫描到 {len(person_pages)} 个人物页面\n")

    # 统计当前已存在 surname 的情况
    has_surname = sum(1 for _, _, _, f in person_pages if f.get("surname"))
    print(f"已有 surname 字段: {has_surname}")
    print(f"缺少 surname 字段: {len(person_pages) - has_surname}\n")

    # 提取/推断 surname
    changes = []
    fixes = []
    for pid, md_file, text, front in person_pages:
        current = front.get("surname")
        expected = extract_surname(pid)

        if current and not expected:
            # 无法推断但已有值，保留
            surname_counts[current] = surname_counts.get(current, 0) + 1
            continue

        if current and expected and current != expected:
            # 已有但错误（如公孙被误判为公）
            new_text = add_surname_to_frontmatter(text, expected)
            if new_text != text:
                fixes.append((pid, md_file, new_text, current, expected))
                if args.fix or not args.apply:
                    surname_counts[expected] = surname_counts.get(expected, 0) + 1
                else:
                    surname_counts[current] = surname_counts.get(current, 0) + 1
                if len(expected) > 1:
                    multi_char_surnames_found.add(expected)
                continue
            else:
                surname_counts[current] = surname_counts.get(current, 0) + 1
                continue

        if current:
            # 已有且正确
            surname_counts[current] = surname_counts.get(current, 0) + 1
            if len(current) > 1:
                multi_char_surnames_found.add(current)
            continue

        surname = extract_surname(pid)
        if not surname:
            no_surname.append(pid)
            continue

        surname_counts[surname] = surname_counts.get(surname, 0) + 1
        if len(surname) > 1:
            multi_char_surnames_found.add(surname)

        new_text = add_surname_to_frontmatter(text, surname)
        if new_text != text:
            changes.append((pid, md_file, new_text, surname))

    if no_surname:
        print(f"\n无法推断姓氏的人物 ({len(no_surname)}):")
        for pid in no_surname[:20]:
            print(f"  {pid}")
        if len(no_surname) > 20:
            print(f"  ... 还有 {len(no_surname) - 20} 个")

    print(f"\n需添加 surname 的人物: {len(changes)}")

    # 执行改写（新增 surname）
    if args.apply and changes:
        for pid, md_file, new_text, surname in changes:
            md_file.write_text(new_text, encoding="utf-8")
            print(f"  ✓ {pid} → {surname}")
        print(f"\n已新增 {len(changes)} 个页面的 surname")

    # 执行修正（错误 surname）
    if args.apply and args.fix and fixes:
        for pid, md_file, new_text, old, new in fixes:
            md_file.write_text(new_text, encoding="utf-8")
            print(f"  ✎ {pid}: {old} → {new}")
        print(f"\n已修正 {len(fixes)} 个页面的 surname")

    # 预览修正
    if not args.apply and fixes:
        print(f"\n需要修正的 surname（使用 --fix 会修正）:")
        for pid, _, _, old, new in fixes[:30]:
            print(f"  ✎ {pid}: {old} → {new}")
        if len(fixes) > 30:
            print(f"  ... 还有 {len(fixes) - 30} 个")
        print(f"\n共 {len(fixes)} 个待修正（使用 --apply --fix 执行）")

    # 统计
    print(f"\n=== 姓氏统计 ===")
    print(f"唯一姓氏数: {len(surname_counts)}")
    print(f"多字姓氏数: {len(multi_char_surnames_found)}")
    print(f"多字姓氏: {sorted(multi_char_surnames_found)}")

    print(f"\n=== 姓氏频次 Top 50 ===")
    for s, c in sorted(surname_counts.items(), key=lambda x: -x[1])[:50]:
        print(f"  {s}: {c}")

    if args.create_pages:
        created = 0
        existed = 0
        for surname in sorted(surname_counts.keys()):
            page_name = f"{surname}（姓氏）"
            target = PAGES / f"{page_name}.md"
            count = surname_counts[surname]
            if target.exists():
                existed += 1
                continue

            old_target = PAGES / f"{surname}.md"
            if old_target.exists():
                existing_fm = parse_frontmatter(old_target.read_text(encoding="utf-8"))
                if existing_fm.get("type") == "姓氏":
                    old_target.rename(target)

            description = f"姓「{surname}」的历史人物列表，共 {count} 人。"
            content = f"""---
id: {surname}（姓氏）
type: 姓氏
label: {surname}
description: {description}
tags: [姓氏]
---

# {surname}姓

::: query
type: 人物
surname: {surname}
display: table
fields: [label, tags, total_refs, description]
sort: total_refs
order: desc
:::
"""
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", encoding="utf-8", delete=False) as f:
                f.write(content)
                tmp_path = f.name

            result = subprocess.run(
                [sys.executable, str(ROOT / "wiki/scripts/add_page.py"),
                 page_name, tmp_path,
                 "--summary", f"新增姓氏页: {page_name}（{count} 人）",
                 "--author", "butler"],
                capture_output=True, text=True, cwd=ROOT
            )
            Path(tmp_path).unlink()

            if result.returncode == 0:
                print(f"  ✓ 创建 {page_name}（{count} 人）")
                created += 1
            elif "页面已存在" in result.stderr:
                existed += 1
            else:
                print(f"  ✗ {page_name}: {result.stderr.strip()}")

        print(f"\n姓氏页面：新建 {created}，已存在 {existed}")
    elif surname_counts:
        print(f"\n提示: 使用 --create-pages 可创建 {len(surname_counts)} 个姓氏页面")


if __name__ == "__main__":
    main()
