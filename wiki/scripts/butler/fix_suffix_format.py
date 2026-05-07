#!/usr/bin/env python3
"""
修正后缀格式：X_(_概念).md → X_(概念).md
并处理残留裸单字文件。
"""
import os, re, json, sys
from pathlib import Path

PAGES_DIR = Path("wiki/public/pages")
SINGLE_HANZI = re.compile(r"^[一-鿿㐀-䶿豈-﫿]$")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Load TYPE_SUFFIX mapping
TYPE_SUFFIX = {
    "concept": "概念", "artifact": "器物", "astronomy": "天文",
    "place": "地名", "military": "军事", "economy": "经济",
    "ritual": "礼制", "tribe": "部族", "institution": "制度",
    "dynasty": "朝代", "law": "法律", "state": "国名",
    "official": "官制", "person": "人物",
}

import yaml

os.chdir(Path(__file__).resolve().parents[3])

# Step 1: Rename X_(_类别).md → X_(类别).md and update frontmatter
renamed = 0
for f in sorted(os.listdir(PAGES_DIR)):
    if not f.endswith(".md"):
        continue
    # Match files like X_(_类别).md
    m = re.match(r"^(.+?)_\(_(.+)\)\.md$", f)
    if not m:
        continue
    char = m.group(1)
    suffix = m.group(2)
    if not SINGLE_HANZI.match(char):
        continue
    old_path = PAGES_DIR / f
    new_name = f"{char}_({suffix}).md"
    new_path = PAGES_DIR / new_name

    if new_path.exists():
        print(f"[skip] {new_name} 已存在")
        continue

    # Read and update frontmatter
    content = old_path.read_text(encoding="utf-8")
    m_fm = FRONTMATTER_RE.match(content)
    if m_fm:
        try:
            front = yaml.safe_load(m_fm.group(1))
        except Exception:
            front = {}
        if front:
            old_id = front.get("id", "")
            new_id = f"{char}_({suffix})"
            if old_id != new_id:
                front["id"] = new_id
                body = content[m_fm.end():]
                new_front_yaml = yaml.dump(front, allow_unicode=True, default_flow_style=False, sort_keys=False).strip()
                new_content = f"---\n{new_front_yaml}\n---\n\n{body.lstrip()}"
                new_path.write_text(new_content, encoding="utf-8")
                old_path.unlink()
                renamed += 1
                if renamed % 200 == 0:
                    print(f"  已修正 {renamed}...")
                continue

    # Fallback: plain rename without frontmatter update
    old_path.rename(new_path)
    renamed += 1

print(f"✓ 已修正 {renamed} 个文件格式")

# Step 2: Process remaining bare single-char files
remaining = []
for f in sorted(os.listdir(PAGES_DIR)):
    if not f.endswith(".md"):
        continue
    name = f[:-3]
    if not SINGLE_HANZI.match(name):
        continue
    remaining.append(name)

print(f"\n剩余裸单字文件: {len(remaining)}")
for char in remaining:
    path = PAGES_DIR / f"{char}.md"
    content = path.read_text(encoding="utf-8")
    m_fm = FRONTMATTER_RE.match(content)
    if not m_fm:
        print(f"  [skip] {char}: 无 frontmatter")
        continue
    try:
        front = yaml.safe_load(m_fm.group(1)) or {}
    except Exception:
        print(f"  [skip] {char}: YAML 解析失败")
        continue

    page_type = front.get("type", "concept")
    suffix = TYPE_SUFFIX.get(page_type, "概念")
    new_id = f"{char}_({suffix})"
    new_path = PAGES_DIR / f"{new_id}.md"

    if new_path.exists():
        print(f"  [skip] {char}: {new_id} 已存在")
        path.unlink()
        continue

    # Update frontmatter
    front["id"] = new_id
    if not front.get("label"):
        front["label"] = char
    aliases = front.get("aliases", [])
    if isinstance(aliases, str):
        aliases = [aliases]
    if char not in aliases:
        aliases.append(char)
    front["aliases"] = aliases

    new_front_yaml = yaml.dump(front, allow_unicode=True, default_flow_style=False, sort_keys=False).strip()
    body = content[m_fm.end():]
    new_content = f"---\n{new_front_yaml}\n---\n\n{body.lstrip()}"
    new_path.write_text(new_content, encoding="utf-8")
    path.unlink()
    print(f"  ✓ {char} → {new_id}")

print(f"\n✓ 处理完成")

# Step 3: Fix wikilinks (X_(_类别) → X_(类别))
print("\n修正 wikilinks...")
fixed_links = 0
OLD_LINK_RE = re.compile(r"\[\[([^\[\]|]+)\(_\(([^\)]+)\)(\|[^\[\]]+)?\]\]")
for f in sorted(os.listdir(PAGES_DIR)):
    if not f.endswith(".md"):
        continue
    if f.startswith("第") and f.endswith("卷.md"):
        continue
    path = PAGES_DIR / f
    content = path.read_text(encoding="utf-8")
    new_content = OLD_LINK_RE.sub(lambda m: f"[[{m.group(1)}_({m.group(2)}){m.group(3) or ''}]]", content)
    if new_content != content:
        path.write_text(new_content, encoding="utf-8")
        fixed_links += 1

print(f"✓ 已修正 {fixed_links} 个文件中的 wikilinks")

# Step 4: Rebuild pages.json
print("\n重建 pages.json...")
os.system("python3 wiki/scripts/build_registry.py wiki/public/pages --out wiki/public/pages.json --out-lite wiki/public/pages.lite.json")
print("✓ pages.json 已重建")
