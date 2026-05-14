#!/usr/bin/env python3
"""
为人物页生成「生平年表」—— 从《资治通鉴》原文中按年份提取关键事件。

用法:
    # 单个人物（dry-run）
    python3 wiki/scripts/butler/build_timeline.py 曹操 --dry-run

    # 单个人物（写入页面）
    python3 wiki/scripts/butler/build_timeline.py 曹操 --apply

    # 批量处理 top N
    python3 wiki/scripts/butler/build_timeline.py --top 50 --apply

    # 批量处理所有人物
    python3 wiki/scripts/butler/build_timeline.py --all --apply
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "wiki/scripts"))
from page_bucket import resolve_page_file  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent.parent.parent
PAGES_DIR = ROOT / "wiki" / "public" / "pages"
DATA_DIR = ROOT / "wiki" / "data"
PN_CACHE = DATA_DIR / "pn_to_year.json"
REG_PATH = ROOT / "wiki" / "public" / "pages.json"
EDIT_PAGE = ROOT / "wiki" / "scripts" / "edit_page.py"

RE_PN = re.compile(r"^\[(\d{3})-(\d{3})\]\s*(.*)")

# 别名过滤：这些词太通用，跳过
GENERIC_ALIASES = {
    "帝", "皇帝", "王", "公", "侯", "后", "太后", "皇后", "太子",
    "上", "陛下", "天子", "丞相", "将军", "大夫", "卿", "君",
    "大人", "公", "仆射", "尚书", "刺史", "太守", "令", "长史",
    # 常见爵位/谥号泛称
    "武侯", "文侯", "忠武侯", "文公", "武公", "景公", "平公",
    "桓公", "庄公", "襄公", "穆公", "献公", "惠公", "昭公",
    "悼公", "共公", "灵公", "出公", "简公", "孝公",
    "武王", "文王", "宣王", "平王", "庄王", "惠王", "襄王",
    "昭王", "景王", "灵王", "简王", "贞王", "定王",
    # 庙号泛称（各朝共用，极易张冠李戴）
    "太祖", "太宗", "高宗", "中宗", "世宗", "显宗", "肃宗",
    "高祖", "代宗", "德宗", "穆宗", "敬宗", "文宗", "武宗",
    "宣宗", "懿宗", "僖宗", "昭宗", "哀宗",
    "神宗", "哲宗", "徽宗", "钦宗",
}
# 别名少于等于此长度的跳过
MIN_ALIAS_LEN = 2
# 结尾为侯/公/王 且总长<=3的别名跳过
RE_SHORT_TITLE = re.compile(r"^[一-鿿]{1,2}[侯公王]$")


def load_pn_cache() -> dict[str, dict]:
    """加载 PN→年号 缓存。"""
    if not PN_CACHE.exists():
        print("错误: 请先运行 pn_year_cache.py 构建缓存", file=sys.stderr)
        sys.exit(1)
    with open(PN_CACHE) as f:
        return json.load(f)


def load_registry() -> dict:
    """加载 pages.json。"""
    with open(REG_PATH) as f:
        return json.load(f)


def load_volume_texts() -> dict[str, list[tuple[str, str]]]:
    """加载所有卷页面，返回 {vol_num: [(pn, text), ...]}。"""
    vols: dict[str, list[tuple[str, str]]] = {}
    for vf in sorted(PAGES_DIR.rglob("第???卷.md")):
        text = vf.read_text(encoding="utf-8")
        text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL)
        vol_pns: list[tuple[str, str]] = []
        for line in text.splitlines():
            line_s = line.strip()
            if not line_s:
                continue
            m = RE_PN.match(line_s)
            if m:
                pn = f"{m.group(1)}-{m.group(2)}"
                content = m.group(3).strip()
                vol_pns.append((pn, content))
        if vol_pns:
            vols[vf.stem.replace("第", "").replace("卷", "")] = vol_pns
    return vols


def clean_text(text: str) -> str:
    """去掉 wikilink 格式，保留可读文本。"""
    t = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    t = re.sub(r"\[\[([^\]]+)\]\]", r"\1", t)
    # 去掉关键词搜索高亮 【】
    t = t.replace("【", "").replace("】", "")
    return t.strip()


def extract_event(text: str, name: str) -> str:
    """从段落文本中提取短语式事件描述（~30字以内）。"""
    cleaned = clean_text(text)
    # 找到包含名字的句子
    sentences = re.split(r"(?<=[。！？；])", cleaned)
    for sent in sentences:
        if name not in sent:
            continue
        event = sent.strip()
        # 找到含人名的核心子句（按逗号/分句切分）
        clauses = re.split(r"[，；]", event)
        for clause in clauses:
            if name in clause:
                snippet = clause.strip()
                # 去掉句首连词
                snippet = re.sub(r"^(于是|乃|遂|则|因|而|及|初|又|复|亦|既|已|遂|以|因)", "", snippet).strip()
                snippet = snippet.lstrip("，、").strip()
                # 截断
                if len(snippet) > 40:
                    snippet = snippet[:37] + "…"
                return snippet
        # 无逗号分句，直接用整句
        if len(event) > 45:
            event = event[:42] + "…"
        return event
    # 没找到含名字的句子
    return cleaned[:35]


def format_year(year_entry: dict) -> str:
    """格式化年份：有公元就用公元，否则用年号原文。"""
    y = year_entry.get("year", "")
    ad = year_entry.get("ad")
    if ad:
        return str(ad)
    # 无公元（pre-Qin/early Han）
    cleaned = re.sub(r"[（(][^）)]*[）)]", "", y).strip()
    # 优先匹配年号+年数（2-4字年号 + 年数）
    m = re.search(r".*([一-龿]{2,4}[王公侯帝]?[元一二三四五六七八九十]+年)$", cleaned)
    if m:
        candidate = m.group(1)
        # 分离年号部分（年数前的内容）
        year_end = re.search(r"[元一二三四五六七八九十]+年$", candidate)
        if year_end:
            era_part = candidate[:year_end.start()]
            # 过滤掉尊号残留：含"之" 或 纯单字"上""中""下"
            has_positional = "之" in era_part
            is_single_positional = len(era_part) == 1 and era_part in "上中下"
            if era_part and not has_positional and not is_single_positional:
                return candidate
    # fallback: 只保留年数部分
    m2 = re.search(r"([元一二三四五六七八九十]+年)$", cleaned)
    return m2.group(1) if m2 else cleaned[:20]


def get_persons_sorted(registry: dict) -> list[tuple[str, dict]]:
    """返回按 total_refs 降序排列的人物列表。"""
    persons = []
    for pid, entry in registry["pages"].items():
        if entry.get("type") == "人物":
            refs = entry.get("total_refs", 0) or 0
            persons.append((refs, pid, entry))
    persons.sort(key=lambda x: -x[0])
    return [(p[1], p[2]) for p in persons]


def is_valid_alias(alias: str, registry: dict, page_id: str) -> bool:
    """判断别名是否可用（不通用、不与其他页面冲突）。"""
    if len(alias) < MIN_ALIAS_LEN:
        return False
    if alias in GENERIC_ALIASES:
        return False
    if RE_SHORT_TITLE.search(alias):
        return False
    if alias == page_id:
        return True  # 主名始终可用
    # 检查多少页面共享此别名
    count = 0
    for pid, entry in registry["pages"].items():
        if alias in entry.get("aliases", []) or alias == pid:
            count += 1
            if count > 3:
                return False
    return True


def build_timeline_for_person(
    pid: str,
    entry: dict,
    pn_cache: dict[str, dict],
    volumes: dict[str, list[tuple[str, str]]],
    registry: dict,
) -> str | None:
    """为一个人物生成生平年表 Markdown。返回 None 表示无数据。"""
    name = pid
    raw_aliases = entry.get("aliases", [])
    if isinstance(raw_aliases, str):
        raw_aliases = [raw_aliases]
    aliases = [pid] + raw_aliases
    valid_aliases = [a for a in aliases if is_valid_alias(a, registry, pid)]

    # 搜索所有卷中提及此人（含别名）的段落
    mentions: list[tuple[str, str]] = []  # [(pn, text), ...]
    # 为每个别名预编译检测模式
    alias_patterns = {}
    for alias in valid_aliases:
        # 裸 wikilink [[别名]]（无管道符，排除错误链接别名→别名）
        alias_patterns[alias] = re.compile(
            r"\[\[" + re.escape(alias) + r"\]\]"
        )

    # Pre-compute wikilink pattern to extract display text
    RE_WIKILINK = re.compile(r"\[\[(?:[^\]|]+)\|([^\]]+)\]\]|\[\[([^\]]+)\]\]")

    RE_YEAR_LINE = re.compile(r"[元一二三四五六七八九十零〇○\d]+年[）\)]?\s*$")

    for vol_num, paragraphs in volumes.items():
        for pn, ptext in paragraphs:
            # 跳过纯年号标记行（如 [[汉武帝]]上之上建元元年）
            if RE_YEAR_LINE.search(ptext) and len(ptext) < 80:
                continue

            # 转为显示文本（wikilink → 显示文字）
            display_text = RE_WIKILINK.sub(lambda m: m.group(1) or m.group(2), ptext)

            for alias in valid_aliases:
                # 检查别名是否以 wikilink target 形式出现
                if alias_patterns[alias].search(ptext):
                    mentions.append((pn, ptext))
                    break
                # 检查别名是否以裸文本形式出现
                if alias in display_text:
                    mentions.append((pn, ptext))
                    break

    if not mentions:
        return None

    # 去重 PN
    seen_pns = set()
    unique_mentions = []
    for pn, text in mentions:
        if pn not in seen_pns:
            seen_pns.add(pn)
            unique_mentions.append((pn, text))

    # 映射到年份，过滤无年份的
    year_groups: dict[str, list[tuple[str, str, dict]]] = {}
    total_refs = 0
    for pn, text in unique_mentions:
        year_entry = pn_cache.get(pn)
        if not year_entry:
            continue
        year_label = format_year(year_entry)
        year_key = f"{year_entry.get('ad', 9999):04d}-{year_label}"
        if year_key not in year_groups:
            year_groups[year_key] = []
        year_groups[year_key].append((pn, text, year_entry))
        total_refs += 1

    if not year_groups:
        return None

    # 按年份（和PN顺序）排序
    sorted_years = sorted(year_groups.keys(), key=lambda k: (
        year_groups[k][0][0],  # PN 序号
    ))

    # 按 refs 数量决定行数上限
    total_years = len(sorted_years)
    if total_refs >= 200:
        max_rows = 50
    elif total_refs >= 50:
        max_rows = 25
    else:
        max_rows = total_years

    # 取前 N 年的第一条事件
    rows = []
    for year_key in sorted_years:
        if len(rows) >= max_rows:
            break
        matches = year_groups[year_key]
        year_label = year_key.split("-", 1)[1] if "-" in year_key else year_key
        # 用第一条匹配的段落
        best_pn, best_text, _ = matches[0]
        event = extract_event(best_text, pid)
        # 用 pid 中较短的那个别名
        short_name = min([a for a in valid_aliases if a != pid] + [pid], key=len)
        event = event.replace(pid, short_name) if len(short_name) < len(pid) else event
        rows.append((year_label, event, best_pn))

    if not rows:
        return None

    # 生成 Markdown
    lines = ["## 生平年表", "", "| 时间 | 主要事件 | 出处 |", "|------|---------|------|"]
    for year_label, event, pn in rows:
        pn_formatted = f"（{pn}）"
        lines.append(f"| {year_label} | {event} | {pn_formatted} |")

    if max_rows < total_years:
        lines.append("")
        lines.append(f"> 注：仅展示前 {max_rows} 年条目，共 {total_years} 年有记载。")

    return "\n".join(lines) + "\n"


def insert_timeline(existing_content: str, timeline_md: str) -> str:
    """在页面中插入生平年表（放在 ## 参见 之前或末尾）。"""
    existing_content = existing_content.rstrip()
    see_also_pos = existing_content.find("\n## 参见")
    if see_also_pos != -1:
        before = existing_content[:see_also_pos]
        after = existing_content[see_also_pos:]
        return before.rstrip() + "\n\n" + timeline_md + "\n\n" + after
    else:
        return existing_content + "\n\n" + timeline_md


def main():
    import argparse

    ap = argparse.ArgumentParser(description="生命年表生成")
    ap.add_argument("person", nargs="?", help="人物名")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不修改")
    ap.add_argument("--apply", action="store_true", help="写入页面")
    ap.add_argument("--top", type=int, help="处理前 N 个最高引用人物")
    ap.add_argument("--all", action="store_true", help="处理所有人物")
    args = ap.parse_args()

    if not args.dry_run and not args.apply and not args.top and not args.all:
        ap.print_help()
        return

    print("加载数据...")
    pn_cache = load_pn_cache()
    registry = load_registry()
    volumes = load_volume_texts()
    print(f"  卷页面: {len(volumes)}")
    print(f"  PN 缓存: {len(pn_cache)} 条")

    if args.person:
        persons = [(args.person, registry["pages"].get(args.person, {}))]
        if not persons[0][1]:
            print(f"错误: 未找到人物 '{args.person}'")
            sys.exit(1)
    elif args.top:
        all_persons = get_persons_sorted(registry)
        persons = all_persons[:args.top]
    elif args.all:
        persons = get_persons_sorted(registry)
    else:
        return

    print(f"处理 {len(persons)} 个人物...")
    ok = 0
    skipped = 0

    for pid, entry in persons:
        timeline = build_timeline_for_person(pid, entry, pn_cache, volumes, registry)
        if not timeline:
            print(f"  ⏭ {pid} — 无年份数据")
            skipped += 1
            continue

        if args.dry_run:
            print(f"\n{'='*60}")
            print(f"  {pid} (total_refs={entry.get('total_refs', '?')})")
            print(f"{'='*60}")
            print(timeline[:500])
            ok += 1
            continue

        if args.apply:
            page_path = resolve_page_file(PAGES_DIR, pid)
            if page_path is None:
                print(f"  ⚠ {pid} — 页面文件不存在")
                skipped += 1
                continue
            existing = page_path.read_text(encoding="utf-8")
            if "## 生平年表" in existing:
                print(f"  ⏭ {pid} — 已有生平年表")
                skipped += 1
                continue
            new_content = insert_timeline(existing, timeline)
            page_path.write_text(new_content, encoding="utf-8")
            print(f"  ✓ {pid} — 年表已写入")
            ok += 1

    print(f"\n完成: {ok} 成功, {skipped} 跳过")


if __name__ == "__main__":
    main()
