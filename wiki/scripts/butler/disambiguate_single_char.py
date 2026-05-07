#!/usr/bin/env python3
"""
单字条目消歧义迁移脚本。

对所有单汉字页面（如 云.md → 云_(天文).md），
- 创建带消歧义后缀的新文件
- 更新 frontmatter id + 添加 label
- 删除旧文件
- 更新所有 [[X]] wikilinks → [[X_(类别)|X]]

用法:
    python3 wiki/scripts/butler/disambiguate_single_char.py [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import yaml

PAGES_DIR = Path("wiki/public/pages")

# 类型 → 消歧义后缀映射
TYPE_SUFFIX = {
    "concept": "概念",
    "artifact": "器物",
    "astronomy": "天文",
    "place": "地名",
    "military": "军事",
    "economy": "经济",
    "ritual": "礼制",
    "tribe": "部族",
    "institution": "制度",
    "dynasty": "朝代",
    "law": "法律",
    "state": "国名",
    "official": "官制",
    "person": "人物",
}

# 特别规则：某些字根据描述更精确归类
SPECIAL_MAP: dict[str, str] | None = None

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
SINGLE_HANZI = re.compile(r"^[一-鿿㐀-䶿豈-﫿]$")
# 消歧义后缀格式：X_(概念)，不包含额外下划线
SUFFIX_DELIM = "_("
SUFFIX_CLOSE = ")"
WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+)(?:\|[^\[\]]+)?\]\]")


def get_disambiguation_suffix(char: str, front: dict) -> str:
    """Determine the disambiguation suffix for a single character."""
    page_type = front.get("type", "概念")
    return TYPE_SUFFIX.get(page_type, "概念")


def update_wikilinks_in_text(text: str, char_map: dict[str, str]) -> str:
    """Replace [[X]] with [[X_(suffix)|X]] for all single-char links."""
    def replace_link(m: re.Match) -> str:
        target = m.group(1)
        if target in char_map:
            suffix_name = char_map[target]
            return f"[[{suffix_name}|{target}]]"
        return m.group(0)
    return WIKILINK_RE.sub(replace_link, text)


def main():
    parser = argparse.ArgumentParser(description="单字条目消歧义迁移")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不做实际修改")
    args = parser.parse_args()

    os.chdir(Path(__file__).resolve().parents[3])

    # Step 1: 扫描所有单字页面
    single_char_pages: list[tuple[str, dict, str]] = []  # (char, frontmatter, full_content)
    for f in sorted(os.listdir(PAGES_DIR)):
        if not f.endswith(".md"):
            continue
        name = f[:-3]
        if not SINGLE_HANZI.match(name):
            continue
        path = PAGES_DIR / f
        content = path.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(content)
        if not m:
            print(f"[warn] {f}: 无 frontmatter，跳过")
            continue
        try:
            front = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as e:
            print(f"[warn] {f}: YAML 解析失败 ({e})，跳过")
            continue
        single_char_pages.append((name, front, content))

    print(f"共扫描到 {len(single_char_pages)} 个单字页面")

    # Step 2: 构建映射 char → new_id
    char_map: dict[str, str] = {}
    for char, front, _ in single_char_pages:
        suffix = get_disambiguation_suffix(char, front)
        new_id = f"{char}_({suffix})" if suffix else char
        char_map[char] = new_id

    if args.dry_run:
        print("\n消歧义映射预览（前30条）:")
        for char in list(char_map.keys())[:30]:
            print(f"  {char} → {char_map[char]}")
        print(f"  ... 共 {len(char_map)} 条")
        # 检查冲突
        print("\n目标文件名冲突检查:")
        seen = {}
        conflicts = []
        for char, new_id in char_map.items():
            if new_id in seen:
                conflicts.append((char, seen[new_id], new_id))
            seen[new_id] = char
        if conflicts:
            print(f"  [冲突] 发现 {len(conflicts)} 个冲突:")
            for c1, c2, nid in conflicts:
                print(f"    {c1} 和 {c2} 都映射到 {nid}")
        else:
            print("  无冲突 ✓")
        return

    print(f"\n准备将 {len(char_map)} 个单字页面迁移到带消歧义后缀的名称")

    # Step 3: 创建新文件 + 删除旧文件
    created = 0
    for char, front, content in single_char_pages:
        old_path = PAGES_DIR / f"{char}.md"
        suffix = get_disambiguation_suffix(char, front)
        if not suffix:
            print(f"[skip] {char}: 无匹配后缀")
            continue
        new_id = f"{char}_({suffix})"
        new_path = PAGES_DIR / f"{new_id}.md"

        # 更新 frontmatter
        old_id = front.get("id", char)
        front["id"] = new_id
        if not front.get("label"):
            front["label"] = char
        # 添加 alias 确保旧 [[X]] 链接仍可解析
        aliases = front.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [aliases]
        if char not in aliases:
            aliases.append(char)
        front["aliases"] = aliases

        # 重建 frontmatter YAML
        new_front_yaml = yaml.dump(front, allow_unicode=True, default_flow_style=False, sort_keys=False).strip()
        # 重建正文（去掉旧的 frontmatter）
        body = content[m.end():] if (m := FRONTMATTER_RE.match(content)) else content

        new_content = f"---\n{new_front_yaml}\n---\n\n{body.lstrip()}"

        # 写新文件
        new_path.write_text(new_content, encoding="utf-8")
        # 删旧文件
        old_path.unlink()
        created += 1

        if created % 100 == 0:
            print(f"  已迁移 {created}/{len(char_map)}")

    print(f"\n✓ 已迁移 {created} 个单字页面")

    # Step 4: 更新所有页面中的 wikilinks
    print("\n更新 all pages 中的 wikilinks...")
    updated_pages = 0
    for f in sorted(os.listdir(PAGES_DIR)):
        if not f.endswith(".md"):
            continue
        # 跳过只读卷页面
        if f.startswith("第") and f.endswith("卷.md"):
            continue
        path = PAGES_DIR / f
        content = path.read_text(encoding="utf-8")
        new_content = update_wikilinks_in_text(content, char_map)
        if new_content != content:
            path.write_text(new_content, encoding="utf-8")
            updated_pages += 1

    print(f"✓ 已更新 {updated_pages} 个页面中的 wikilinks")

    # Step 5: 重建 pages.json
    print("\n重建 pages.json...")
    os.system("python3 wiki/scripts/build_registry.py wiki/public/pages --out wiki/public/pages.json --out-lite wiki/public/pages.lite.json")
    print("✓ pages.json 已重建")


if __name__ == "__main__":
    main()
