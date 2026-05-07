#!/usr/bin/env python3
"""扫描所有页面，检查 frontmatter 中缺少 type 字段的页面，推断其类型并生成报告。

用法:
    python3 wiki/scripts/scan_missing_type.py wiki/public/pages
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---", re.DOTALL)


def parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        fm[key.strip()] = val.strip().strip("\"'")
    return fm


def infer_type(front: dict, content: str, pid: str) -> str:
    """根据 frontmatter 和内容推断缺失的类型。"""
    # 有明确的推断线索
    if front.get("event_type"):
        et = front["event_type"]
        if et in ("战争", "战役"):
            return "战役" if et == "战役" else "事件"
        return "事件"
    if front.get("cat"):
        return "人物"
    if front.get("concept_cat"):
        return front["concept_cat"]  # 已分拆
    if front.get("dynasty"):
        # 有朝代但没有 cat → 可能是概念或地点
        return None  # 无法确定
    if front.get("place_type") or front.get("modern_name") or front.get("region"):
        return "地点"
    if front.get("birthday") or front.get("gender"):
        return "人物"
    if front.get("author") or front.get("genre"):
        return "名句"  # 诗词名句
    if front.get("book"):
        return "章节"
    # 按 ID 模式推断
    if re.match(r"^第\d+卷$", pid) or re.match(r"^\d{6}$", pid):
        return "章节"
    if re.match(r"^第\d+回$", pid):
        return "章节"
    if re.match(r"^-?\d{1,4}[年]?$", pid) or re.match(r"^公元", pid):
        return "年份"
    if re.match(r"^[A-Z]", pid):
        return None  # 无法确定
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pages_root", help="wiki/public/pages directory")
    ap.add_argument("--out", default="wiki/logs/butler/missing_type_report.json")
    args = ap.parse_args()

    root = Path(args.pages_root)
    if not root.is_dir():
        print(f"[error] not a directory: {root}", file=sys.stderr)
        sys.exit(1)

    results = []
    total = 0
    missing = 0

    for md_file in sorted(root.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        m = FRONTMATTER_RE.match(text)
        if not m:
            continue
        front = parse_frontmatter(text)
        pid = str(md_file.relative_to(root).with_suffix(""))

        # 检查 type
        if "type" in front:
            total += 1
            continue

        missing += 1
        content = text[m.end():].strip()
        inferred = infer_type(front, content, pid)

        rec = {
            "id": pid,
            "front": {k: v for k, v in front.items() if k != "type"},
            "inferred_type": inferred,
            "content_preview": content[:100],
        }
        results.append(rec)

        if inferred:
            print(f"[suggest] {pid} → {inferred}  (基于: {list(front.keys())})")
        else:
            print(f"[unclear] {pid}  无法推断 (front: {list(front.keys())})")

    # 写入报告
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "generated": datetime.now().isoformat(),
        "total_pages": total + missing,
        "missing_type": missing,
        "pages": results,
        "summary": {
            "by_inferred_type": {},
        },
    }
    for r in results:
        t = r["inferred_type"] or "unclear"
        report["summary"]["by_inferred_type"][t] = \
            report["summary"]["by_inferred_type"].get(t, 0) + 1

    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n报告已写入 {out_path}")
    print(f"总页面: {total + missing}, 缺 type: {missing}")
    print(f"推断汇总: {json.dumps(report['summary']['by_inferred_type'], ensure_ascii=False)}")


if __name__ == "__main__":
    main()
