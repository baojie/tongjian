#!/usr/bin/env python3
"""
build_office_pages.py — 为具体官职（如范阳节度使）生成历任表格页面。

流程：
  1. 扫描 294 章节页，用任命句式正则提取「职位 → 担任者 + 引注」
  2. 对预定义目标职位，整理去重后的历任列表
  3. 用 add_page.py / edit_page.py 创建或更新 wiki 页面
  4. 页面中包含 Markdown 表格：| 任职者 | 引注 | 备注 |

用法：
  python3 wiki/scripts/butler/build_office_pages.py [--dry-run] [--position 范阳节度使]
"""
from __future__ import annotations

import re
import sys
import json
import subprocess
import tempfile
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field

ROOT = Path(__file__).resolve().parents[3]
PAGES_DIR = ROOT / "wiki/public/pages"
REG_PATH = ROOT / "wiki/public/pages.json"
ADD_PAGE = ROOT / "wiki/scripts/add_page.py"
EDIT_PAGE = ROOT / "wiki/scripts/edit_page.py"
RECORD = ROOT / "wiki/scripts/record_revision.py"

# ── 目标职位及其元数据 ────────────────────────────────────────────
@dataclass
class OfficeSpec:
    name: str               # 职位名（slug）
    label: str              # 显示名
    parent: str             # 通用职位（用于 aliases / 参见）
    dynasty: str            # 所属朝代
    description: str        # 一句话描述
    tags: list[str] = field(default_factory=list)


# 唐代节度使（十大节度 + 主要内地节度）
TANG_JIEDUSHI = [
    OfficeSpec("范阳节度使", "范阳节度使", "节度使", "唐",
               "唐代范阳镇节度使，治幽州，安禄山曾长期担任此职，为安史之乱的策源地。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("平卢节度使", "平卢节度使", "节度使", "唐",
               "唐代平卢镇节度使，治营州，后移治青州（淄青），为河北三镇之一。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("河东节度使", "河东节度使", "节度使", "唐",
               "唐代河东镇节度使，治太原，为拱卫关中、抵御北方的要冲。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("朔方节度使", "朔方节度使", "节度使", "唐",
               "唐代朔方镇节度使，治灵州，郭子仪等名将曾任此职，安史之乱时为平叛主力。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("河西节度使", "河西节度使", "节度使", "唐",
               "唐代河西镇节度使，治凉州，负责西北边防，安史之乱后被吐蕃蚕食。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("陇右节度使", "陇右节度使", "节度使", "唐",
               "唐代陇右镇节度使，治鄯州，与河西节度使共御吐蕃。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("剑南节度使", "剑南节度使", "节度使", "唐",
               "唐代剑南镇节度使，治成都，安史之乱后分为西川、东川两镇。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("岭南节度使", "岭南节度使", "节度使", "唐",
               "唐代岭南镇节度使，治广州，管辖岭南诸道。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("淮西节度使", "淮西节度使", "节度使", "唐",
               "唐代淮西镇节度使，治蔡州，元和中宪宗以裴度、李愬平之。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("宣武节度使", "宣武节度使", "节度使", "唐",
               "唐代宣武镇节度使，治汴州，朱温（朱全忠）由此起家，代唐建梁。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("魏博节度使", "魏博节度使", "节度使", "唐",
               "唐代魏博镇节度使，治魏州，为河北三镇之一，长期割据对抗中央。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("成德节度使", "成德节度使", "节度使", "唐",
               "唐代成德镇节度使，治恒州，为河北三镇之一，长期世袭。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("卢龙节度使", "卢龙节度使", "节度使", "唐",
               "唐代卢龙镇节度使，治幽州（安史乱后），为河北三镇之一。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("昭义节度使", "昭义节度使", "节度使", "唐",
               "唐代昭义镇节度使，治潞州，介于河北、关中之间，具重要战略地位。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("西川节度使", "西川节度使", "节度使", "唐",
               "唐代西川镇节度使，治成都，剑南节度使分置后西川的行政中心。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("东川节度使", "东川节度使", "节度使", "唐",
               "唐代东川镇节度使，治梓州，剑南节度使分置后东川部分。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("凤翔节度使", "凤翔节度使", "节度使", "唐",
               "唐代凤翔镇节度使，治凤翔，拱卫长安西门，唐末多与宦官、皇位争夺相关。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("忠武节度使", "忠武节度使", "节度使", "唐",
               "唐代忠武镇节度使，治许州，藩镇割据时期中原重要节镇。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("义成节度使", "义成节度使", "节度使", "唐",
               "唐代义成镇节度使，治滑州，地处中原交通要道。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("河阳节度使", "河阳节度使", "节度使", "唐",
               "唐代河阳镇节度使，治河阳（今孟州），控黄河南北渡口。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("淮南节度使", "淮南节度使", "节度使", "唐",
               "唐代淮南镇节度使，治扬州，为财赋重地，高骈等曾任此职。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("山南东道节度使", "山南东道节度使", "节度使", "唐",
               "唐代山南东道节度使，治襄州，控汉水中游。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("山南西道节度使", "山南西道节度使", "节度使", "唐",
               "唐代山南西道节度使，治兴元，控汉中地区。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("荆南节度使", "荆南节度使", "节度使", "唐",
               "唐代荆南镇节度使，治江陵，控长江中游门户。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("镇海节度使", "镇海节度使", "节度使", "唐",
               "唐代镇海镇节度使，治润州，控江南东道，李锜曾任此职并叛乱。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("天平节度使", "天平节度使", "节度使", "唐",
               "唐代天平镇节度使，治郓州，处黄河下游。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("武宁节度使", "武宁节度使", "节度使", "唐",
               "唐代武宁镇节度使，治徐州，唐末为军事要冲。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("邠宁节度使", "邠宁节度使", "节度使", "唐",
               "唐代邠宁镇节度使，治邠州，为关中西北屏障。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("振武节度使", "振武节度使", "节度使", "唐",
               "唐代振武镇节度使，治单于都护府，防御北方草原。",
               ["节度使", "藩镇", "唐"]),
    OfficeSpec("泾原节度使", "泾原节度使", "节度使", "唐",
               "唐代泾原镇节度使，治泾州，泾原兵变为唐中期重大政治事件。",
               ["节度使", "藩镇", "唐"]),
]

# 重要刺史
IMPORTANT_CISHI = [
    OfficeSpec("益州刺史", "益州刺史", "刺史", "汉至南北朝",
               "益州刺史，治成都，为西南地区最高军政长官，三国蜀汉的核心地域。",
               ["刺史", "汉", "三国", "南北朝"]),
    OfficeSpec("荆州刺史", "荆州刺史", "刺史", "汉至南北朝",
               "荆州刺史，治所屡迁，控长江中游，为南北争夺要地。",
               ["刺史", "汉", "三国", "南北朝"]),
    OfficeSpec("扬州刺史", "扬州刺史", "刺史", "汉至南北朝",
               "扬州刺史，治建康或寿春，为东南财赋之地长官。",
               ["刺史", "汉", "三国", "南北朝"]),
    OfficeSpec("幽州刺史", "幽州刺史", "刺史", "汉至南北朝",
               "幽州刺史，治蓟城，为北方边境要地，历代重要屏障。",
               ["刺史", "汉", "南北朝"]),
]

ALL_OFFICES = TANG_JIEDUSHI + IMPORTANT_CISHI

# ── 任命句式提取 ─────────────────────────────────────────────────
PARA_RE = re.compile(r'\[(\d{3})-(\d{3})\]\s*(.+?)(?=\n\[|\Z)', re.DOTALL)
WIKILINK_CLEAN = re.compile(r'\[\[([^\]|]+?)(?:\|[^\]]+?)?\]\]')


def clean_wikilinks(text: str) -> str:
    return WIKILINK_CLEAN.sub(r'\1', text)


def make_appt_patterns(position: str):
    pos = re.escape(position)
    # 合法分隔字符（句末/下一动作）
    boundary = r'(?=[，。；！？\s]|$)'
    # 官职词（可能出现在「以X职衔 人名 兼/为 POSITION」中）
    title_seg = r'(?:[^\s，。；：]{2,8}(?:节度使|刺史|太守|都督|都护|经略使|观察使))?'
    return [
        # 以X为/兼/充/权知/权领/守 POSITION（简单形式）
        re.compile(r'以([^\s，。；：「」【】\[\]（）以]{2,5})(?:为|兼|充|权知|权领|守)(?:[^\s，。；]{0,4}、)?' + pos),
        # 以[职衔]X兼/为 POSITION（嵌套形式，如「以平卢节度使安禄山兼范阳节度使」）
        re.compile(r'以' + title_seg + r'([^\s，。；：「」【】\[\]（）以]{2,4})(?:兼|为|充)' + pos),
        # X拜/除/授/迁/判/领/知/兼 POSITION
        re.compile(r'([^\s，。；：「」【】\[\]（）以]{2,5})(?:拜|除|授|迁|判|领|知)' + pos),
        # POSITION X（职位紧跟人名，名后需接动词或标点）
        re.compile(pos + r'([^\s，。；：「」【】\[\]（）以为]{2,4})' + boundary),
        # X为 POSITION（X不能以「以/其/自」开头）
        re.compile(r'(?<![以其自乃])([^\s，。；：「」【】\[\]（）以]{2,5})为' + pos),
    ]


# 噪声词过滤：明显非人名
NOISE = {
    '节度使', '刺史', '太守', '都督', '都护', '经略使', '观察使',
    '防御使', '招讨使', '行军', '副使', '行军司马', '监军', '留后',
    '此职', '本道', '其人', '将士', '诸将', '大臣', '百官',
    '先是', '初', '既', '遂', '乃', '而', '则', '以',
}


_BAD_START = set('以其自乃而则遂于在亦且至及与、制')
_BAD_END = set('以将已既专为之等兵军卒道郡州府使帅薨卒病朝入令')
_POSITION_TERMS = ('节度使', '刺史', '太守', '都督', '都护', '经略使', '观察使',
                   '防御使', '招讨使', '节度', '行军', '司马', '监军',
                   '留守', '度使', '少师', '少傅', '仆射', '侍中', '尚书',
                   '都统', '镇遏', '判度', '置使', '镇守', '副使',
                   '河南尹', '太子', '中书')

def is_valid_name(name: str) -> bool:
    if not name or len(name) < 2 or len(name) > 5:
        return False
    if name in NOISE:
        return False
    if re.search(r'[，。；：\s0-9]', name):
        return False
    if name[0] in _BAD_START:
        return False
    if name[-1] in _BAD_END:
        return False
    # 人名中不应包含官职词
    for term in _POSITION_TERMS:
        if term in name:
            return False
    return True


@dataclass
class Appointment:
    person: str
    vol: int
    para: int
    context: str


def extract_holders(position: str, pages_dir: Path) -> list[Appointment]:
    patterns = make_appt_patterns(position)
    seen: dict[tuple[str, int], Appointment] = {}

    for md in sorted(pages_dir.glob("第*.md")):
        text = md.read_text(encoding="utf-8")
        for m in PARA_RE.finditer(text):
            vol, para = int(m.group(1)), int(m.group(2))
            seg = m.group(3)
            if position not in seg:
                continue
            clean = clean_wikilinks(seg)
            for pat in patterns:
                for pm in pat.finditer(clean):
                    name = pm.group(1).strip()
                    if not is_valid_name(name):
                        continue
                    key = (name, vol)
                    if key not in seen:
                        seen[key] = Appointment(
                            person=name,
                            vol=vol,
                            para=para,
                            context=clean[:80].strip(),
                        )

    # 按人名去重：若「史思明」和「思明」都出现，保留更长的那个
    by_name: dict[str, Appointment] = {}
    for appt in seen.values():
        name = appt.person
        # 检查是否是已有记录的子串（「思明」⊂「史思明」）
        dominated = False
        for existing_name in list(by_name.keys()):
            if name in existing_name:
                dominated = True
                break
            if existing_name in name:
                # 新记录更长，替换
                del by_name[existing_name]
        if not dominated:
            if name not in by_name or appt.vol < by_name[name].vol:
                by_name[name] = appt

    result = sorted(by_name.values(), key=lambda a: (a.vol, a.para))
    return result


# ── 页面内容生成 ──────────────────────────────────────────────────

def format_pn(vol: int, para: int) -> str:
    return f"（{vol:03d}-{para:03d}）"


def build_full_page(spec: OfficeSpec, holders: list[Appointment]) -> str:
    tags_yaml = ', '.join(f'"{t}"' for t in spec.tags)
    aliases_yaml = f'["{spec.parent}", "{spec.label}"]'
    fm = f"""---
id: {spec.name}
type: official
label: {spec.label}
aliases: {aliases_yaml}
dynasty: {spec.dynasty}
tags: [{tags_yaml}]
description: {spec.description}
---"""

    table_rows = []
    for a in holders:
        pn = format_pn(a.vol, a.para)
        ctx = a.context[:40].replace('|', '｜')
        name_link = f"[[{a.person}]]"
        table_rows.append(f"| {name_link} | {pn} | {ctx} |")

    see_also = set([spec.parent, '节度使', '藩镇']) if '节度使' in spec.name else {spec.parent}
    see_lines = '\n'.join(f'- [[{s}]]' for s in sorted(see_also) if s != spec.name)
    body = f"""# [[{spec.name}]]

## 简介

{spec.description}

## 历任列表

| 任职者 | 首见引注 | 语境摘要 |
|--------|----------|----------|
""" + '\n'.join(table_rows) + f"""

## 参见

{see_lines}
"""
    return fm + '\n' + body


def build_page_content(spec: OfficeSpec, holders: list[Appointment]) -> str:
    """仅返回 body（无 frontmatter），用于更新已有页。"""
    table_rows = []
    for a in holders:
        pn = format_pn(a.vol, a.para)
        ctx = a.context[:40].replace('|', '｜')
        name_link = f"[[{a.person}]]"
        table_rows.append(f"| {name_link} | {pn} | {ctx} |")

    lines = [
        f"## 历任列表",
        f"",
        f"| 任职者 | 首见引注 | 语境摘要 |",
        f"|--------|----------|----------|",
    ] + table_rows + [
        f"",
        f"## 参见",
        f"",
        f"- [[{spec.parent}]]",
    ]
    return '\n'.join(lines)


# ── 主流程 ────────────────────────────────────────────────────────

def load_registry():
    data = json.loads(REG_PATH.read_text(encoding="utf-8"))
    return data["pages"]


def page_exists(slug: str, pages: dict) -> bool:
    return slug in pages and (PAGES_DIR / f"{slug}.md").exists()


def create_or_update_page(spec: OfficeSpec, holders: list[Appointment],
                          pages: dict, dry_run: bool) -> str:
    slug = spec.name
    exists = page_exists(slug, pages)

    if dry_run:
        action = "update" if exists else "create"
        return f"[dry] {action} {slug}"

    if not exists:
        full_page = build_full_page(spec, holders)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md',
                                        encoding='utf-8', delete=False) as f:
            f.write(full_page)
            tmp = f.name
        try:
            r = subprocess.run(
                [sys.executable, str(ADD_PAGE), slug, tmp,
                 '--summary', f'新增词条：{slug}（历任官员表格）',
                 '--author', 'butler'],
                capture_output=True, text=True, cwd=ROOT,
            )
            if r.returncode != 0:
                return f"✗ create {slug}: {r.stderr.strip()[:100]}"
            return f"✓ created {slug}"
        finally:
            Path(tmp).unlink(missing_ok=True)
    else:
        md_path = PAGES_DIR / f"{slug}.md"
        existing = md_path.read_text(encoding='utf-8')
        new_table_section = build_page_content(spec, holders)
        if '## 历任列表' in existing:
            new_text = re.sub(
                r'## 历任列表\n.*?(?=\n## |\Z)',
                new_table_section,
                existing,
                flags=re.DOTALL,
            )
        else:
            new_text = existing.rstrip() + '\n\n' + new_table_section + '\n'
        if new_text == existing:
            return f"~ unchanged {slug}"
        md_path.write_text(new_text, encoding='utf-8')
        subprocess.run(
            [sys.executable, str(RECORD), slug,
             '--summary', '更新历任列表',
             '--author', 'butler'],
            capture_output=True, cwd=ROOT,
        )
        return f"✓ updated {slug}"


def main():
    dry_run = '--dry-run' in sys.argv
    filter_pos = None
    for i, arg in enumerate(sys.argv):
        if arg == '--position' and i + 1 < len(sys.argv):
            filter_pos = sys.argv[i + 1]

    pages = load_registry()

    targets = [s for s in ALL_OFFICES
               if filter_pos is None or s.name == filter_pos]

    print(f"处理 {len(targets)} 个职位{'（DRY RUN）' if dry_run else ''}...")

    for spec in targets:
        holders = extract_holders(spec.name, PAGES_DIR)
        if not holders:
            print(f"  {spec.name}: 未找到任职记录，跳过")
            continue

        result = create_or_update_page(spec, holders, pages, dry_run)
        print(f"  {result} [{len(holders)} 条任职记录]")

    print("完成。")


if __name__ == '__main__':
    main()
