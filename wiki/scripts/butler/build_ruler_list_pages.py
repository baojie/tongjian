#!/usr/bin/env python3
"""
build_ruler_list_pages.py — 为所有政权创建「XX君主列表」页面。

流程：
  1. 从现有 56 个政权页提取君主世系表格
  2. 补全 ~18 个缺失政权的君主数据
  3. 生成「XX君主列表」页面内容和更新后的政权页内容
  4. 通过 add_page.py / edit_page.py 写入 wiki

用法：
  python3 wiki/scripts/butler/build_ruler_list_pages.py [--dry-run] [--phase all|create|update] [--state SLUG]
"""
from __future__ import annotations

import re
import sys
import json
import os
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass, field

ROOT = Path(__file__).resolve().parents[3]  # noqa: E402



ROOT = Path(__file__).resolve().parents[3]
PAGES_DIR = ROOT / "wiki/public/pages"
REG_PATH = ROOT / "wiki/public/pages.json"
ADD_PAGE = ROOT / "wiki/scripts/add_page.py"
EDIT_PAGE = ROOT / "wiki/scripts/edit_page.py"

OUT_DIR = Path("/tmp/enrich/ruler_lists")
CREATE_DIR = OUT_DIR / "create"  # 列表页内容（给 add_page.py）
UPDATE_DIR = OUT_DIR / "update"  # 更新后的政权页内容（给 edit_page.py）


@dataclass
class RulerEntry:
    title: str      # 称号（含 wikilink）
    name: str       # 姓名（4列格式），3列格式为空
    reign: str      # 在位年数/时期
    relation: str   # 与前代关系


@dataclass
class RegimeSpec:
    slug: str               # 政权页 slug
    list_slug: str          # 列表页 slug
    label: str              # 政权显示名
    description: str        # 列表页描述
    column_format: str      # "4col" | "3col"
    tags: list[str] = field(default_factory=lambda: ["君主", "列表"])
    rulers: list[RulerEntry] = field(default_factory=list)
    is_summary: bool = False   # 是否为 overview 摘要页
    sub_list_slugs: list[str] = field(default_factory=list)  # 子列表 slug


# ── 表提取 ──────────────────────────────────────────────────────────

def find_section(content: str, section_title: str) -> str | None:
    """提取 ## section_title 到下一个 ## 之间的文本"""
    m = re.search(
        rf'^##\s*{re.escape(section_title)}\s*$.*?(?=^\s*##\s|\Z)',
        content, re.MULTILINE | re.DOTALL
    )
    if m:
        return m.group(0)
    return None


def extract_table_from_section(section_text: str) -> list[str] | None:
    """从章节文本中提取 markdown 表格行（含表头）。"""
    lines = section_text.split('\n')
    table_lines = []
    in_table = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and stripped.endswith('|'):
            table_lines.append(stripped)
            in_table = True
        elif in_table and not stripped.startswith('|'):
            break
        elif in_table and stripped.startswith('|'):
            table_lines.append(stripped)
    return table_lines if len(table_lines) >= 3 else None  # header + sep + 1 row


def detect_column_format(header_line: str) -> str:
    """检测表列格式：4col / 3col"""
    cols = [c.strip() for c in header_line.strip('|').split('|')]
    if len(cols) >= 4:
        return "4col"
    elif len(cols) == 3:
        return "3col"
    return "other"


def extract_sub_tables(section_text: str) -> list[tuple[str, list[str]]]:
    """提取 overview 页面中的子表，返回 [(sub_name, table_lines), ...]"""
    lines = section_text.split('\n')
    result = []
    current_sub = None
    current_table = []

    for line in lines:
        stripped = line.strip()
        # 检测子标题 ###
        m = re.match(r'^###\s+(.+?)(?:\s*（.*）)?\s*$', stripped)
        if m:
            if current_sub and len(current_table) >= 3:
                result.append((current_sub, current_table))
            current_sub = m.group(1).strip()
            current_table = []
        elif stripped.startswith('|') and stripped.endswith('|'):
            current_table.append(stripped)

    if current_sub and len(current_table) >= 3:
        result.append((current_sub, current_table))

    return result


def count_rulers(table_lines: list[str]) -> int:
    """统计数据行数（去掉表头、分隔行、空行）"""
    count = 0
    for i, line in enumerate(table_lines):
        if i == 0 or i == 1:  # 跳过表头和分隔行
            continue
        if line.strip().startswith('|') and '---' not in line:
            count += 1
    return count


def extract_regime_description(content: str) -> str:
    """从页面内容提取政权描述（用于列表页 description）"""
    # 先从 frontmatter 取
    m = re.search(r'^description:\s*(.+)', content, re.MULTILINE)
    if m:
        desc = m.group(1).strip().strip('"').strip("'")
        return desc
    return ""


# ── 缺失数据定义 ──────────────────────────────────────────────────────

# 以下定义 ~18 个缺少君主世系表的政权的君主数据
MISSING_REGIMES = {
    "曹魏": RegimeSpec(
        slug="曹魏", list_slug="曹魏君主列表", label="曹魏",
        description="三国之一，曹操奠基、曹丕建立，历五帝46年",
        column_format="4col",
        tags=["三国", "君主", "列表"],
        rulers=[
            RulerEntry("[[曹丕|文帝]]", "[[曹丕]]", "7年（220—226）", "开国（[[曹操]]之子）"),
            RulerEntry("[[汉明帝|明帝]]", "[[曹叡]]", "13年（226—239）", "[[隋文帝|文帝]]之子"),
            RulerEntry("[[齐王]]（[[李从珂|废帝]]）", "曹芳", "15年（239—254）", "[[汉明帝|明帝]]养子"),
            RulerEntry("高贵乡公", "[[曹髦]]", "6年（254—260）", "[[隋文帝|文帝]]之孙"),
            RulerEntry("[[元帝]]（[[陈留]]王）", "曹奂", "6年（260—266）", "[[曹操]]之孙"),
        ]
    ),
    "武周": RegimeSpec(
        slug="武周", list_slug="武周君主列表", label="武周",
        description="武则天建立的周朝（690—705年），仅一代",
        column_format="4col",
        tags=["唐朝", "君主", "列表"],
        rulers=[
            RulerEntry("[[武则天|则天大圣皇帝]]", "[[武则天|武曌]]", "15年（690—705）", "开国（[[唐高宗]]之后）"),
        ]
    ),
    "闽国": RegimeSpec(
        slug="闽国", list_slug="闽国君主列表", label="闽国",
        description="五代十国之一，王审知所建，历6主37年",
        column_format="4col",
        tags=["五代十国", "君主", "列表"],
        rulers=[
            RulerEntry("[[闽太祖|太祖]]", "[[王审知]]", "29年（909—935）", "开国（[[唐末]][[节度使]]）"),
            RulerEntry("嗣主", "王延翰", "1年（935—936）", "太祖之子"),
            RulerEntry("[[闽太宗|太宗]]", "王延钧", "4年（936—939）", "太祖之子"),
            RulerEntry("康宗", "王继鹏", "7年（939—944）", "太宗之子"),
            RulerEntry("景宗", "王延羲", "2年（944—945）", "太祖之子"),
            RulerEntry("[[天德]]帝", "王延政", "1年（945—946）", "太祖之子"),
        ]
    ),
    "夏国": RegimeSpec(
        slug="夏国", list_slug="夏国君主列表", label="夏国",
        description="十六国之一，赫连勃勃所建，历三主25年（407—431）",
        column_format="4col",
        tags=["十六国", "君主", "列表"],
        rulers=[
            RulerEntry("[[夏武烈帝|武烈帝]]", "[[赫连勃勃]]", "18年（407—425）", "开国（[[刘卫辰]]之子）"),
            RulerEntry("[[夏|废帝]]", "赫连昌", "4年（425—428）", "[[赫连勃勃|武烈帝]]之子"),
            RulerEntry("[[夏|平帝]]", "赫连定", "3年（428—431）", "[[赫连勃勃|武烈帝]]之子"),
        ]
    ),
    "西秦": RegimeSpec(
        slug="西秦", list_slug="西秦君主列表", label="西秦",
        description="十六国之一，乞伏氏所建，历四主47年（385—431）",
        column_format="4col",
        tags=["十六国", "君主", "列表"],
        rulers=[
            RulerEntry("[[西秦宣烈王|宣烈王]]", "[[乞伏国仁]]", "3年（385—388）", "开国（[[陇西]][[鲜卑]]首领）"),
            RulerEntry("[[西秦武元王|武元王]]", "[[乞伏乾归]]", "24年（388—412）", "宣烈王之弟"),
            RulerEntry("[[西秦文昭王|文昭王]]", "[[乞伏炽磐]]", "16年（412—428）", "武元王之子"),
            RulerEntry("[[西秦|末主]]", "乞伏暮末", "3年（428—431）", "文昭王之子"),
        ]
    ),
    "越国": RegimeSpec(
        slug="越国", list_slug="越国君主列表", label="越国",
        description="周代诸侯国，姒姓，春秋五霸之一",
        column_format="3col",
        tags=["春秋", "战国", "君主", "列表"],
        rulers=[
            RulerEntry("[[越王勾践]]", "", "前496—前465", "开国霸主"),
            RulerEntry("越王鹿郢", "", "前465—前459", "勾践之子"),
            RulerEntry("越王不寿", "", "前459—前449", "鹿郢之子"),
            RulerEntry("越王翁", "", "前449—前412", "不寿之子"),
            RulerEntry("越王翳", "", "前412—前376", "翁之子"),
            RulerEntry("越王无疆", "", "前376—前333", "翳之子（通鉴所载）"),
        ]
    ),
    "西周": RegimeSpec(
        slug="西周", list_slug="西周君主列表", label="西周（战国）",
        description="战国小国，周王室分裂后的西周公国",
        column_format="3col",
        tags=["战国", "君主", "列表"],
        rulers=[
            RulerEntry("[[西周桓公|桓公]]", "", "前441—？", "开国（[[周考王]]分封）"),
            RulerEntry("西周威公", "", "？—前367", "桓公之子"),
            RulerEntry("西周惠公", "", "前367—前320", "威公之子"),
            RulerEntry("西周武公", "", "前320—前270", "惠公之子"),
            RulerEntry("西周文公", "", "前270—前256", "武公之子（为秦所灭）"),
        ]
    ),
    "仇池": RegimeSpec(
        slug="仇池", list_slug="仇池君主列表", label="仇池",
        description="氐族杨氏建立的政权，据仇池山，历多代",
        column_format="4col",
        tags=["十六国", "君主", "列表"],
        rulers=[
            RulerEntry("[[杨茂搜|仇池公]]", "杨茂搜", "？—317", "开国（氐[[部落]]首领）"),
            RulerEntry("[[杨难敌|仇池公]]", "杨难敌", "317—334", "茂搜之子"),
            RulerEntry("[[杨毅|仇池公]]", "杨毅", "334—337", "难敌之子"),
            RulerEntry("[[杨初|仇池公]]", "杨初", "337—355", "毅之族弟"),
            RulerEntry("[[杨国|仇池公]]", "杨国", "355—356", "初之子"),
            RulerEntry("[[杨俊|仇池公]]", "杨俊", "356—360", "国之叔父"),
            RulerEntry("[[杨世|仇池公]]", "杨世", "360—370", "俊之子"),
            RulerEntry("[[杨统|仇池公]]", "杨统", "370—371", "世之弟"),
            RulerEntry("[[杨纂|仇池公]]", "杨纂", "371", "世之子"),
            RulerEntry("[[杨定|武都王]]", "杨定", "385—395", "纂之族弟（复国）"),
            RulerEntry("[[杨盛|仇池公]]", "杨盛", "395—425", "定之族弟"),
            RulerEntry("[[杨玄|武都王]]", "杨玄", "425—429", "盛之子"),
            RulerEntry("[[杨难当|武都王]]", "杨难当", "429—442", "玄之弟"),
        ]
    ),
    "大月氏": RegimeSpec(
        slug="大月氏", list_slug="大月氏君主列表", label="大月氏",
        description="西域古族，曾居敦煌祁连间，后西迁至中亚",
        column_format="3col",
        tags=["西域", "君主", "列表"],
        rulers=[
            RulerEntry("[[月氏王]]（早期）", "", "前3—前2世纪", "居敦煌、祁连间"),
            RulerEntry("月氏王（西迁后）", "", "前2世纪后", "西迁至[[妫水]]流域"),
            RulerEntry("[[丘就却|贵霜翕侯]]", "丘就却", "约30—80年", "统一五翕侯，立[[贵霜]]"),
            RulerEntry("[[阎膏珍]]", "阎膏珍", "约80—105年", "丘就却之子"),
        ]
    ),
    "宕昌": RegimeSpec(
        slug="宕昌", list_slug="宕昌君主列表", label="宕昌",
        description="羌族政权，南北朝时据陇西，梁勤所建",
        column_format="4col",
        tags=["南北朝", "君主", "列表"],
        rulers=[
            RulerEntry("梁勤", "梁勤", "？", "开国（[[羌]][[部落]]首领）"),
            RulerEntry("梁弥忽", "梁弥忽", "？", "梁勤之孙"),
            RulerEntry("梁弥黄", "梁弥黄", "？", "弥忽之子"),
            RulerEntry("梁弥瑾", "梁弥瑾", "？—485", "弥黄之子"),
            RulerEntry("梁弥颐", "梁弥颐", "485—？", "弥瑾之子"),
            RulerEntry("梁弥承", "梁弥承", "？", "弥颐之子"),
            RulerEntry("梁弥博", "梁弥博", "？—505", "弥承之子"),
            RulerEntry("梁弥像", "梁弥像", "505—？", "弥博之子"),
        ]
    ),
    "邓至": RegimeSpec(
        slug="邓至", list_slug="邓至君主列表", label="邓至",
        description="羌族政权，南北朝时据陇西白水",
        column_format="4col",
        tags=["南北朝", "君主", "列表"],
        rulers=[
            RulerEntry("邓至王（像舒）", "像舒", "？", "开国（[[羌]][[部落]]首领）"),
            RulerEntry("邓至王（像屈耽）", "像屈耽", "？", "像舒之子"),
            RulerEntry("邓至王（像舒彭）", "像舒彭", "？—507", "像屈耽之子"),
        ]
    ),
    "高丽": RegimeSpec(
        slug="高丽", list_slug="高丽君主列表", label="高丽",
        description="高句丽政权，周代至唐初的东北古国",
        column_format="4col",
        tags=["东北", "君主", "列表"],
        rulers=[
            RulerEntry("[[高朱蒙|东明王]]", "高朱蒙", "前37—前19", "开国"),
            RulerEntry("[[高类利|琉璃王]]", "高类利", "前19—18年", "东明王之子"),
            RulerEntry("[[高无恤|大武神王]]", "高无恤", "18—44", "琉璃王之子"),
            RulerEntry("[[高宫|太祖王]]", "高宫", "53—146", "琉璃王之孙"),
            RulerEntry("[[高伯固|新大王]]", "高伯固", "165—179", "太祖王之弟"),
            RulerEntry("[[高男武|故国川王]]", "高男武", "179—197", "新大王之子"),
            RulerEntry("[[高伊夷模|山上王]]", "高伊夷模", "197—227", "故国川王之弟"),
            RulerEntry("[[高忧位居|东川王]]", "高忧位居", "227—248", "山上王之子"),
            RulerEntry("[[高然弗|中川王]]", "高然弗", "248—270", "东川王之子"),
            RulerEntry("[[高药卢|西川王]]", "高药卢", "270—292", "中川王之子"),
            RulerEntry("[[高相夫|美川王]]", "高相夫", "300—331", "西川王之子"),
            RulerEntry("[[高乙弗利|故国原王]]", "高乙弗利", "331—371", "美川王之子"),
            RulerEntry("[[高丘德|长寿王]]", "高丘德", "413—491", "故国原王之子"),
            RulerEntry("[[高罗云|文咨王]]", "高罗云", "491—519", "长寿王之孙"),
            RulerEntry("[[高兴安|安藏王]]", "高高兴", "519—531", "文咨王之子"),
            RulerEntry("[[高宝藏|宝藏王]]", "高宝藏", "642—668", "荣留王之侄（为唐所灭）"),
        ]
    ),
    "柔然": RegimeSpec(
        slug="柔然", list_slug="柔然君主列表", label="柔然",
        description="南北朝时期的北方游牧政权，可汗世系",
        column_format="4col",
        tags=["南北朝", "君主", "列表"],
        rulers=[
            RulerEntry("[[郁久闾社仑|丘豆伐可汗]]", "郁久闾社仑", "402—410", "开国（统一[[漠北]]）"),
            RulerEntry("[[郁久闾斛律|蔼苦盖可汗]]", "郁久闾斛律", "410—414", "社仑之弟"),
            RulerEntry("[[郁久闾大檀|牟汗纥升盖可汗]]", "郁久闾大檀", "414—429", "社仑之从弟"),
            RulerEntry("[[郁久闾吴提|敕连可汗]]", "郁久闾吴提", "429—444", "大檀之子"),
            RulerEntry("[[郁久闾吐贺真|处可汗]]", "郁久闾吐贺真", "444—464", "吴提之子"),
            RulerEntry("[[郁久闾予成|受罗部真可汗]]", "郁久闾予成", "464—485", "吐贺真之子"),
            RulerEntry("[[郁久闾豆仑|伏名敦可汗]]", "郁久闾豆仑", "485—492", "予成之子"),
            RulerEntry("[[郁久闾那盖|候其伏代库者可汗]]", "郁久闾那盖", "492—506", "予成之弟"),
            RulerEntry("[[郁久闾伏图|他汗可汗]]", "郁久闾伏图", "506—508", "那盖之子"),
            RulerEntry("[[郁久闾丑奴|豆罗伏跋豆伐可汗]]", "郁久闾丑奴", "508—520", "伏图之子"),
            RulerEntry("[[郁久闾阿那瓌|敕连头兵豆伐可汗]]", "郁久闾阿那瓌", "520—552", "伏图之子（为[[突厥]]所灭）"),
        ]
    ),
    "蜀": RegimeSpec(
        slug="蜀", list_slug="蜀国君主列表", label="蜀国",
        description="周代诸侯国，古蜀国，战国时为秦所灭",
        column_format="3col",
        tags=["战国", "君主", "列表"],
        rulers=[
            RulerEntry("[[开明氏]]（丛帝）", "", "约前7—前6世纪", "开国（蜀王[[杜宇]]之后）"),
            RulerEntry("蜀王（开明氏历代）", "", "前6—前316", "世系不详"),
            RulerEntry("蜀王（[[开明|芦子]]）", "", "前316（为[[秦]]灭）", "末代蜀王"),
        ]
    ),
    "齐国": RegimeSpec(
        slug="齐国", list_slug="齐国君主列表", label="齐国",
        description="西周至战国诸侯国，姜齐与田齐相继统治",
        column_format="3col",
        tags=["春秋", "战国", "君主", "列表"],
        rulers=[
            RulerEntry("[[姜太公|太公望]]", "", "前11世纪", "开国（[[周武王]]封）"),
            RulerEntry("[[齐桓公]]", "", "前685—前643", "[[春秋]]首霸"),
            RulerEntry("[[齐威王]]", "", "前357—前320", "[[田齐]]中兴之主"),
            RulerEntry("[[齐宣王]]", "", "前320—前301", "威王之子"),
            RulerEntry("[[齐湣王]]", "", "前301—前284", "宣王之子"),
            RulerEntry("齐襄王", "", "前284—前265", "湣王之子"),
            RulerEntry("齐[[王建]]", "", "前265—前221", "襄王之子（为秦所灭）"),
        ]
    ),
}

# 名称覆盖（label 不准确时需要）
LIST_NAME_OVERRIDE = {
    "隋_(朝代)": "隋朝君主列表",
    "唐_(朝代)": "唐朝君主列表",
    "齐_(国名)": "齐国君主列表",
}

# 重复政权页面，指向相同列表页
DUPLICATE_MAP = {
    "赵": ("赵国", "赵国君主列表"),
    "楚": ("楚国", "楚国君主列表"),
    "齐": ("齐国", "齐国君主列表"),
    "齐_(国名)": ("齐国", "齐国君主列表"),
}

# Overview 页面：子政权列表
OVERVIEW_SUB_MAP = {
    "三国": {
        "subs": ["曹魏君主列表", "蜀汉君主列表", "东吴君主列表"],
        "summary": "三国（220—280年）魏蜀吴三国鼎立时期。",
    },
    "五代": {
        "subs": ["后梁君主列表", "后唐君主列表", "后晋君主列表", "后汉君主列表", "后周君主列表"],
        "summary": "五代（907—960年）唐宋之间的五个中原王朝。",
    },
    "南朝": {
        "subs": ["刘宋君主列表", "南齐君主列表", "梁朝君主列表", "陈朝君主列表"],
        "summary": "南朝（420—589年）南北朝时代南方相继的四个政权。",
    },
}


# ── 页面生成 ──────────────────────────────────────────────────────────

def build_list_page_content(
    spec: RegimeSpec,
    table_lines: list[str] | None = None,
) -> str:
    """生成君主列表页面的完整 markdown 内容（含 frontmatter）。"""
    tags_yaml = ', '.join(f'"{t}"' for t in spec.tags)
    fm = f"""---
id: {spec.list_slug}
type: 综述
label: {spec.list_slug}
tags: [{tags_yaml}]
description: {spec.description}
---"""

    title = f"# {spec.list_slug}"

    if spec.is_summary:
        # Overview 摘要页：列出子政权链接
        links = '\n'.join(
            f'- [[{s}]]' for s in spec.sub_list_slugs
        )
        body = f"""
{title}

{spec.description}

## 子政权列表

{links}
"""
    elif table_lines:
        # 从现有表格构建
        table_str = '\n'.join(table_lines)
        ruler_count = count_rulers(table_lines)
        desc = spec.description.rstrip('。.')
        body = f"""
{title}

{desc}，共{ruler_count}位。

{table_str}
"""
    elif spec.rulers:
        # 手动定义的数据
        desc = spec.description.rstrip('。.')
        if spec.column_format == "4col":
            header = "| 称号 | 姓名 | 在位年数 | 与前代关系 |"
            sep = "|------|------|---------|-----------|"
            rows = []
            for r in spec.rulers:
                rows.append(f"| {r.title} | {r.name} | {r.reign} | {r.relation} |")
        else:
            header = "| 称号 | 在位时期 | 与前代关系 |"
            sep = "|------|---------|-----------|"
            rows = []
            for r in spec.rulers:
                rows.append(f"| {r.title} | {r.reign} | {r.relation} |")

        table_str = '\n'.join([header, sep] + rows)
        body = f"""
{title}

{desc}，共{len(spec.rulers)}位。

{table_str}
"""
    else:
        body = f"""
{title}

{spec.description}
"""

    return fm + '\n' + body


def generate_regime_update_content(
    content: str,
    list_slug: str,
    is_duplicate: bool = False,
) -> str | None:
    """
    为有 君主世系 表的政权页生成更新内容。
    将 `## 君主世系` 节替换为引用链接。
    返回新内容，或 None 如果不需要更新。
    """
    section = find_section(content, "君主世系")
    if not section:
        return None

    # 重复页：直接使用简单引用
    if is_duplicate:
        replacement = f"## 君主世系\n\n详见：[[{list_slug}]]。\n"
        new_content = content.replace(section.strip(), replacement.strip())
        return new_content

    # 检测是否是 overview 多子表页
    sub_tables = extract_sub_tables(section)
    if sub_tables:
        # overview 页：生成子表链接列表
        slug_match = re.search(r'^id:\s*(\S+)', content, re.MULTILINE)
        slug = slug_match.group(1) if slug_match else ""
        overview_info = OVERVIEW_SUB_MAP.get(slug)
        if overview_info:
            sub_names = overview_info["subs"]
        else:
            sub_names = [n for n, _ in sub_tables]
        sub_links = [f"- [[{n}]]" for n in sub_names]
        summary = overview_info["summary"] if overview_info else ""
        replacement = f"## 君主世系\n\n{summary}\n\n" + '\n'.join(sub_links) + "\n"
    else:
        replacement = f"## 君主世系\n\n详见：[[{list_slug}]]。\n"

    new_content = content.replace(section.strip(), replacement.strip())
    return new_content


# ── 主流程 ──────────────────────────────────────────────────────────

def load_registry():
    data = json.loads(REG_PATH.read_text(encoding="utf-8"))
    return data["pages"]


def load_page(slug: str) -> str:
    path = resolve_page_file(PAGES_DIR, slug)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def get_regime_info(content: str) -> dict:
    """从 frontmatter 提取信息"""
    info = {"label": "", "dynasty": "", "tags": []}
    m = re.search(r'^label:\s*(.+)', content, re.MULTILINE)
    if m:
        info["label"] = m.group(1).strip()
    m = re.search(r'^dynasty:\s*(.+)', content, re.MULTILINE)
    if m:
        info["dynasty"] = m.group(1).strip()
    return info


def process_all(dry_run: bool = False, phase: str = "all", state_filter: str | None = None):
    """主处理逻辑"""
    pages = load_registry()
    os.makedirs(CREATE_DIR, exist_ok=True)
    os.makedirs(UPDATE_DIR, exist_ok=True)

    # 收集所有 74 个 regime slug
    regime_slugs = []
    for slug, meta in pages.items():
        if meta.get("type") in ("国家", "王朝"):
            regime_slugs.append(slug)

    if state_filter:
        regime_slugs = [s for s in regime_slugs if state_filter in s]
        if not regime_slugs:
            # 也检查是否是手动数据
            pass

    regime_slugs.sort()
    print(f"共 {len(regime_slugs)} 个政权页面")

    # 处理每个政权
    created = 0
    updated = 0
    skipped = 0

    for slug in regime_slugs:
        # 检查重复
        if slug in DUPLICATE_MAP:
            target_slug, list_slug = DUPLICATE_MAP[slug]
            if phase in ("all", "update"):
                # 对于重复页，直接添加引用
                content = load_page(slug)
                if not content:
                    continue
                # 检查是否有君主世系节
                section = find_section(content, "君主世系")
                if not section:
                    # 添加引用
                    reference = f"## 君主世系\n\n详见：[[{list_slug}]]。\n"
                    # 找到插入位置（在最后一个 ## 节后，或末尾）
                    new_content = content.rstrip() + '\n\n' + reference
                    update_path = UPDATE_DIR / f"{slug}_enrich.md"
                    update_path.write_text(new_content, encoding="utf-8")
                    if not dry_run:
                        print(f"  [enrich] {slug} → {list_slug}")
                    else:
                        print(f"  [dry-enrich] {slug} → {list_slug}")
                    updated += 1
                else:
                    # 已有君主世系，替换
                    new_content = generate_regime_update_content(content, list_slug, is_duplicate=True)
                    if new_content:
                        update_path = UPDATE_DIR / f"{slug}_replace.md"
                        update_path.write_text(new_content, encoding="utf-8")
                        print(f"  [replace] {slug}: 君主世系 → 引用 [[{list_slug}]]")
                        updated += 1
            continue

        # 处理正常政权
        content = load_page(slug)
        if not content:
            print(f"  ! 页面不存在: {slug}")
            skipped += 1
            continue

        # 确定列表页 slug
        info = get_regime_info(content)
        list_slug = f"{info['label']}君主列表"
        if list_slug == "君主列表":
            list_slug = f"{slug}君主列表"  # fallback
        # 名称覆盖（label 不准确时）
        if slug in LIST_NAME_OVERRIDE:
            list_slug = LIST_NAME_OVERRIDE[slug]

        # 检查是否有君主世系表
        section = find_section(content, "君主世系")
        table_lines = None
        sub_tables = []

        if section:
            sub_tables = extract_sub_tables(section)
            if sub_tables:
                # Overview 页，跳过（会在下面单独处理）
                pass
            else:
                table_lines = extract_table_from_section(section)

        # 检查是否是 overview 页
        is_overview = slug in OVERVIEW_SUB_MAP

        if is_overview and phase in ("all", "create"):
            # 创建 overview 摘要页
            overview_info = OVERVIEW_SUB_MAP[slug]
            sub_sub_list_slugs = overview_info["subs"]

            spec = RegimeSpec(
                slug=slug, list_slug=list_slug, label=info.get("label", slug),
                description=overview_info['summary'],
                column_format="4col",
                is_summary=True,
                sub_list_slugs=sub_sub_list_slugs,
            )
            page_content = build_list_page_content(spec)
            create_path = CREATE_DIR / f"{list_slug}.md"
            create_path.write_text(page_content, encoding="utf-8")
            if not dry_run:
                print(f"  [create-sum] {list_slug}")
            else:
                print(f"  [dry-sum] {list_slug}")
            created += 1

            # 处理 overview 页的更新
            if phase in ("all", "update"):
                new_content = generate_regime_update_content(content, list_slug)
                if new_content:
                    update_path = UPDATE_DIR / f"{slug}_replace.md"
                    update_path.write_text(new_content, encoding="utf-8")
                    print(f"  [replace] {slug}: 君主世系 → 子政权链接")
                    updated += 1

        elif table_lines and phase in ("all", "create"):
            # 有现有表格 → 创建列表页
            dynasty_tag = info.get("dynasty", "") or slug
            desc = extract_regime_description(content)
            spec = RegimeSpec(
                slug=slug, list_slug=list_slug, label=info.get("label", slug),
                description=desc,
                column_format=detect_column_format(table_lines[0]),
                tags=[dynasty_tag, "君主", "列表"],
            )
            page_content = build_list_page_content(spec, table_lines)
            create_path = CREATE_DIR / f"{list_slug}.md"
            create_path.write_text(page_content, encoding="utf-8")
            if not dry_run:
                print(f"  [create] {list_slug} ({count_rulers(table_lines)} rulers from {slug})")
            else:
                print(f"  [dry] {list_slug}")
            created += 1

            # 生成更新内容
            if phase in ("all", "update"):
                new_content = generate_regime_update_content(content, list_slug)
                if new_content:
                    update_path = UPDATE_DIR / f"{slug}_replace.md"
                    update_path.write_text(new_content, encoding="utf-8")
                    print(f"  [replace] {slug} → [[{list_slug}]]")
                    updated += 1

        elif slug in MISSING_REGIMES and phase in ("all", "create"):
            # 缺失数据政权
            spec = MISSING_REGIMES[slug]
            # 使用 LIST_NAME_OVERRIDE 优先
            if slug in LIST_NAME_OVERRIDE:
                actual_list_slug = LIST_NAME_OVERRIDE[slug]
            else:
                actual_list_slug = spec.list_slug
            page_content = build_list_page_content(spec)
            create_path = CREATE_DIR / f"{actual_list_slug}.md"
            create_path.write_text(page_content, encoding="utf-8")
            if not dry_run:
                print(f"  [create-manual] {actual_list_slug} ({len(spec.rulers)} rulers)")
            else:
                print(f"  [dry-manual] {actual_list_slug}")
            created += 1

            # 对于无表政权，也在 update 中添加引用
            if phase in ("all", "update"):
                section = find_section(content, "君主世系")
                if section:
                    new_content = generate_regime_update_content(content, actual_list_slug)
                    if new_content:
                        update_path = UPDATE_DIR / f"{slug}_replace.md"
                        update_path.write_text(new_content, encoding="utf-8")
                        print(f"  [replace] {slug} → [[{list_slug}]]")
                        updated += 1
                else:
                    # 添加君主世系引用
                    ref_list_slug = actual_list_slug if slug in MISSING_REGIMES else list_slug
                    reference = f"## 君主世系\n\n详见：[[{ref_list_slug}]]。\n"
                    new_content = content.rstrip() + '\n\n' + reference
                    update_path = UPDATE_DIR / f"{slug}_enrich.md"
                    update_path.write_text(new_content, encoding="utf-8")
                    print(f"  [enrich] {slug}: +君主世系 → [[{ref_list_slug}]]")
                    updated += 1

        else:
            print(f"  - {slug}: 跳过（无数据）")
            skipped += 1

    print(f"\n== 汇总 ==")
    print(f"  创建列表页: {created}")
    print(f"  更新政权页: {updated}")
    print(f"  跳过: {skipped}")
    print(f"  输出目录: {OUT_DIR}")
    print(f"    CREATE: {CREATE_DIR}/ ({len(list(CREATE_DIR.rglob('*.md'))) if CREATE_DIR.exists() else 0} files)")
    print(f"    UPDATE: {UPDATE_DIR}/ ({len(list(UPDATE_DIR.rglob('*.md'))) if UPDATE_DIR.exists() else 0} files)")


def apply_create(dry_run: bool = False):
    """应用创建：运行 add_page.py 创建所有列表页"""
    print("应用创建列表页...")
    files = sorted(CREATE_DIR.rglob("*.md"))
    print(f"共 {len(files)} 个列表页待创建")

    for f in files:
        slug = f.stem
        if dry_run:
            print(f"  [dry] add_page {slug}")
            continue
        try:
            r = subprocess.run(
                [sys.executable, str(ADD_PAGE), slug, str(f),
                 '--summary', f'新增词条：{slug}（君主列表）',
                 '--author', 'butler'],
                capture_output=True, text=True, cwd=ROOT,
            )
            if r.returncode == 0:
                print(f"  ✓ {slug}")
            else:
                stderr = r.stderr.strip()[:120]
                if "already exists" in stderr:
                    print(f"  ~ {slug}: 已存在，跳过")
                else:
                    print(f"  ✗ {slug}: {stderr}")
        except Exception as e:
            print(f"  ✗ {slug}: {e}")


def apply_update(dry_run: bool = False):
    """应用更新：运行 edit_page.py 更新政权页"""
    print("应用更新政权页...")

    # 先处理 replace 类型（已有君主世系，需替换）
    replace_files = sorted(UPDATE_DIR.glob("*_replace.md"))
    for f in replace_files:
        slug = f.stem.replace("_replace", "")
        if dry_run:
            print(f"  [dry] edit_page {slug} (replace)")
            continue
        try:
            r = subprocess.run(
                [sys.executable, str(EDIT_PAGE), slug, str(f),
                 '--summary', '替换君主世系表为引用链接',
                 '--author', 'butler', '--allow-shrink'],
                capture_output=True, text=True, cwd=ROOT,
            )
            if r.returncode == 0:
                print(f"  ✓ {slug} (replace)")
            else:
                stderr = r.stderr.strip()[:120]
                print(f"  ✗ {slug}: {stderr}")
        except Exception as e:
            print(f"  ✗ {slug}: {e}")

    # 再处理 enrich 类型（没有君主世系，需追加）
    enrich_files = sorted(UPDATE_DIR.glob("*_enrich.md"))
    for f in enrich_files:
        slug = f.stem.replace("_enrich", "")
        if dry_run:
            print(f"  [dry] edit_page {slug} (enrich)")
            continue
        try:
            r = subprocess.run(
                [sys.executable, str(EDIT_PAGE), slug, str(f),
                 '--summary', '新增君主世系链接',
                 '--author', 'butler', '--enrich'],
                capture_output=True, text=True, cwd=ROOT,
            )
            if r.returncode == 0:
                print(f"  ✓ {slug} (enrich)")
            else:
                stderr = r.stderr.strip()[:120]
                print(f"  ✗ {slug}: {stderr}")
        except Exception as e:
            print(f"  ✗ {slug}: {e}")


def main():
    dry_run = '--dry-run' in sys.argv
    phase = "all"
    state_filter = None

    for i, arg in enumerate(sys.argv):
        if arg == '--phase' and i + 1 < len(sys.argv):
            phase = sys.argv[i + 1]
        if arg == '--state' and i + 1 < len(sys.argv):
            state_filter = sys.argv[i + 1]

    if phase in ("all", "prepare"):
        print(f"阶段: prepare{'（DRY RUN）' if dry_run else ''}")
        process_all(dry_run, "all", state_filter)

    if phase in ("all", "create"):
        print(f"\n阶段: create{'（DRY RUN）' if dry_run else ''}")
        apply_create(dry_run)

    if phase in ("all", "update"):
        print(f"\n阶段: update{'（DRY RUN）' if dry_run else ''}")
        apply_update(dry_run)

    print("\n完成。")


if __name__ == '__main__':
    main()
