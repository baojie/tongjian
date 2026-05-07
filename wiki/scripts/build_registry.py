#!/usr/bin/env python3
"""
构建 pages.json 注册表（给浏览器端 wikilink 解析用）。

用法:
    python3 wiki/scripts/build_registry.py wiki/public/pages --out wiki/public/pages.json
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from compute_quality import compute_quality_score  # noqa: E402

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+)(?:\|[^\[\]]+)?\]\]")

# 语义链接 [[rel::target]] 中的 target 提取
SEMANTIC_TARGET_RE = re.compile(r"^[^:]+::(.+)$")
# 单汉字 wikilink 检测：[[记]]、[[花]] 等，通常是拆分书名时的错误标注
SINGLE_HANZI_LINK_RE = re.compile(r"[一-鿿㐀-䶿豈-﫿]")


def parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}


def build_registry(pages_root: Path) -> dict:
    pages: dict = {}
    alias_index: dict = {}

    for md_file in sorted(pages_root.rglob("*.md")):
        rel = md_file.relative_to(pages_root)
        pid = str(rel.with_suffix(""))
        text = md_file.read_text(encoding="utf-8")
        front = parse_frontmatter(text)

        # body = everything after frontmatter
        m_fm = FRONTMATTER_RE.match(text)
        body = text[m_fm.end():] if m_fm else text

        entry: dict = {
            "type":    front.get("type", "unknown"),
            "label":   front.get("label", pid),
            "aliases": front.get("aliases", []),
            "tags":    front.get("tags", []),
        }
        if front.get("description"):
            entry["description"] = front["description"]
        if front.get("featured"):
            entry["featured"] = True
        if front.get("image"):
            entry["image"] = front["image"]
        if front.get("quality"):
            entry["quality"] = front["quality"]
            entry["quality_score"] = compute_quality_score(front, body)
        # chapter-specific fields
        for field in ("book", "book_seq", "pn_prefix"):
            if front.get(field) is not None:
                entry[field] = front[field]

        # extra display fields that may be queried
        for field in ("birthday", "gender", "father", "mother", "spouse", "children",
                      "siblings", "uncles", "aunts", "nephews", "nieces",
                      "grandparents", "grandchildren", "cousins", "in_laws",
                      "master", "servants", "fate",
                      # event
                      "date", "end_date", "location", "participants", "result",
                      # place
                      "region", "modern_name", "place_type",
                      # poem
                      "author", "genre", "context",
                      # object
                      "owner", "material", "object_type",
                      # food
                      "food_type", "occasion",
                      # family
                      "house", "members",
                      # concept
                      "concept_type", "concept_cat"):
            if front.get(field) is not None:
                entry[field] = front[field]

        pages[pid] = entry

        # alias index — chapter pages: only register by id, not label
        label_keys = [] if entry["type"] == "chapter" else [entry["label"]]
        for key in [pid] + label_keys + (entry["aliases"] or []):
            if not isinstance(key, str):
                continue
            if key in alias_index and alias_index[key] != pid:
                print(f"[warn] alias conflict: '{key}' → {alias_index[key]} vs {pid}", file=sys.stderr)
            else:
                alias_index[key] = pid

    # ── 第二遍扫描：统计 wikilink 引用 ──────────────
    # 为 alias_index 加自身 id，保证 resolve 时自洽
    for pid in pages:
        if pid not in alias_index:
            alias_index[pid] = pid

    def resolve_wikilink(target: str) -> str | None:
        """将 [[原始名称]] 解析为 pages 中的 pid，找不到返回 None"""
        t = target.strip()
        if t in pages:
            return t
        return alias_index.get(t)

    total_refs: dict[str, int] = collections.defaultdict(int)
    ch_refs: dict[str, set[str]] = collections.defaultdict(set)  # pid → set of source chapter pids

    for md_file in sorted(pages_root.rglob("*.md")):
        rel = md_file.relative_to(pages_root)
        src_pid = str(rel.with_suffix(""))
        src_page = pages.get(src_pid)
        is_chapter = (src_page and src_page.get("type") == "chapter")

        text = md_file.read_text(encoding="utf-8")
        m_fm = FRONTMATTER_RE.match(text)
        body = text[m_fm.end():] if m_fm else text

        seen_local: set[str] = set()
        for match in WIKILINK_RE.finditer(body):
            raw = match.group(1)
            # ── lint: 单汉字 wikilink ──
            if SINGLE_HANZI_LINK_RE.fullmatch(raw):
                fm_end = m_fm.end() if m_fm else 0
                line_no = text[:fm_end + match.start()].count('\n') + 1
                print(f"[lint] {src_pid}:{line_no}: 单汉字 wikilink [[{raw}]] "
                      f"——可能是词条拆分错误，请确认是否为全书名的一部分", file=sys.stderr)
            # 语义链接 [[rel::target]] 只取 target 部分做引用统计
            if "::" in raw:
                m = SEMANTIC_TARGET_RE.match(raw)
                if m:
                    raw = m.group(1)
            resolved = resolve_wikilink(raw)
            if resolved and resolved != src_pid:  # 不自引用
                if resolved not in seen_local:
                    total_refs[resolved] += 1
                    seen_local.add(resolved)
                if is_chapter:
                    ch_refs[resolved].add(src_pid)

    # 写入 computed 字段
    for pid, entry in pages.items():
        entry["total_refs"] = total_refs.get(pid, 0)
        entry["total_chapters"] = len(ch_refs.get(pid, set()))

    return {
        "pages":       pages,
        "alias_index": alias_index,
        "page_count":  len(pages),
        "generated":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def strip_lite(entry: dict) -> dict:
    """lite 版本仅保留 wikilink 解析所需字段。"""
    return {k: entry[k] for k in ("type", "label", "aliases") if k in entry}


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pages_root", help="wiki/public/pages directory")
    ap.add_argument("--out", default="wiki/public/pages.json")
    ap.add_argument("--out-lite", default=None,
                    help="lite 输出路径（默认 --out 同目录下的 pages.lite.json）")
    args = ap.parse_args()

    root = Path(args.pages_root)
    if not root.is_dir():
        print(f"[error] not a directory: {root}", file=sys.stderr)
        sys.exit(1)

    registry = build_registry(root)

    # ── 全量输出 ──
    out = Path(args.out)
    write_json(out, registry)
    print(f"[ok] {len(registry['pages'])} pages → {out}")

    # ── lite 输出 ──
    lite_path = Path(args.out_lite) if args.out_lite else out.with_name("pages.lite.json")
    lite_registry = {
        "pages":       {pid: strip_lite(e) for pid, e in registry["pages"].items()},
        "alias_index": registry["alias_index"],
        "page_count":  registry["page_count"],
        "generated":   registry["generated"],
    }
    write_json(lite_path, lite_registry)
    print(f"[ok] {len(lite_registry['pages'])} pages → {lite_path} (lite)")


if __name__ == "__main__":
    main()
