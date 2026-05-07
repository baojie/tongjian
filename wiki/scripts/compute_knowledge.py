#!/usr/bin/env python3
"""
计算资治通鉴 Wiki 知识量快照，写入：
  wiki/public/data/knowledge_latest.json    — 最新快照（覆盖写）
  wiki/public/data/knowledge_timeline.jsonl — 历史时间线（追加写，去重）

K 值 = 所有实体页（非 chapter）quality_score 之和，反映知识深度与覆盖广度。
link_hit_rate = [[wikilink]] 解析命中率（0~1）。
quality_counts = 各等级页面数量：premium/featured/standard/basic/stub。

用法：
    python3 wiki/scripts/compute_knowledge.py
    python3 wiki/scripts/compute_knowledge.py --dry-run   # 只打印，不写文件
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = ROOT / "public" / "pages"
PAGES_JSON = ROOT / "public" / "pages.json"
DATA_DIR = ROOT / "public" / "data"
LATEST_PATH = DATA_DIR / "knowledge_latest.json"
TIMELINE_PATH = DATA_DIR / "knowledge_timeline.jsonl"

RE_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
QUALITY_TIERS = ["premium", "featured", "standard", "basic", "stub"]


def load_registry() -> dict:
    with open(PAGES_JSON, encoding="utf-8") as f:
        return json.load(f)


def compute_snapshot(registry: dict) -> dict:
    pages = registry.get("pages", {})

    quality_counts: dict[str, int] = {t: 0 for t in QUALITY_TIERS}
    total_score = 0
    entity_count = 0

    for page in pages.values():
        if page.get("type") == "章节":
            continue
        entity_count += 1
        q = page.get("quality", "stub")
        qs = page.get("quality_score", 0) or 0
        total_score += qs
        if q in quality_counts:
            quality_counts[q] += 1
        else:
            quality_counts["stub"] += 1

    # link hit rate: scan all page files for [[links]]
    registry_ids = set(pages.keys())
    total_links = hit_links = 0
    for md_file in PAGES_DIR.glob("*.md"):
        text = md_file.read_text(encoding="utf-8", errors="replace")
        for m in RE_WIKILINK.finditer(text):
            slug = m.group(1).strip()
            total_links += 1
            if slug in registry_ids:
                hit_links += 1

    hit_rate = (hit_links / total_links) if total_links > 0 else 1.0

    return {
        "K": total_score,
        "page_count": entity_count,
        "link_hit_rate": round(hit_rate, 4),
        "quality_counts": quality_counts,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def load_timeline() -> list[dict]:
    if not TIMELINE_PATH.exists():
        return []
    lines = TIMELINE_PATH.read_text(encoding="utf-8").strip().splitlines()
    result = []
    for line in lines:
        line = line.strip()
        if line:
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return result


def snapshot_key(s: dict) -> str:
    return s.get("generated", "")[:10]  # date-level dedup


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    registry = load_registry()
    snap = compute_snapshot(registry)

    print(f"[compute_knowledge] K={snap['K']:,}  pages={snap['page_count']}"
          f"  hit_rate={snap['link_hit_rate']*100:.1f}%"
          f"  quality={snap['quality_counts']}")

    if args.dry_run:
        print("[dry-run] 不写文件。")
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 写最新快照
    LATEST_PATH.write_text(
        json.dumps(snap, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # 追加到时间线（同一天只保留最新一条）
    timeline = load_timeline()
    today = snap["generated"][:10]
    timeline = [s for s in timeline if snapshot_key(s) != today]
    timeline.append(snap)
    timeline.sort(key=lambda s: s.get("generated", ""))

    TIMELINE_PATH.write_text(
        "\n".join(json.dumps(s, ensure_ascii=False) for s in timeline) + "\n",
        encoding="utf-8",
    )

    print(f"[compute_knowledge] 已写入 {LATEST_PATH.name}，时间线共 {len(timeline)} 条。")


if __name__ == "__main__":
    main()
