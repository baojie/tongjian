#!/usr/bin/env python3
"""build_line_index.py — 构建全局行索引。

扫描所有页面和历史版本，为每个拼音桶建立 line_hash → line_content 映射。
输出到 wiki/public/line_index/<bucket>.json，供 v2 history 格式使用。
"""
from __future__ import annotations
import hashlib, json, os, sys, time
from pathlib import Path

ROOT    = Path(__file__).resolve().parents[2]
PUBLIC  = ROOT / "wiki/public"
PAGES   = PUBLIC / "pages"
HIST    = PUBLIC / "history"
OUT     = PUBLIC / "line_index"

MIN_HASH_LEN = 6


def compute_hash(line: str, registry: dict[str, str]) -> str:
    """为 line 计算唯一 hash（碰撞时延长）。

    registry: {hash: line_content} 全局已注册映射。
    返回一个不在 registry 中、或已在 registry 中但指向同一 line 的 hash。
    """
    full = hashlib.sha256(line.encode("utf-8")).hexdigest()
    for length in range(MIN_HASH_LEN, 17):
        h = full[:length]
        if h not in registry or registry[h] == line:
            return h
    raise RuntimeError(f"无法为行生成唯一 hash（16 位仍有碰撞）: {line[:60]}")


def lines_from_text(text: str) -> list[str]:
    """将文本拆分为行（保留空行，去掉末尾空行）。"""
    return text.rstrip("\n").split("\n")


def scan_pages(bucket: str, registry: dict[str, str],
               stats: dict) -> None:
    """扫描 pages/<bucket>/*.md，注册所有行。"""
    pages_dir = PAGES / bucket
    if not pages_dir.is_dir():
        return
    for fpath in sorted(pages_dir.glob("*.md")):
        try:
            text = fpath.read_text(encoding="utf-8")
        except Exception:
            continue
        for line in lines_from_text(text):
            if not line:
                continue
            h = compute_hash(line, registry)
            if h not in registry:
                registry[h] = line
                stats["new_lines"] += 1
        stats["pages_scanned"] += 1


def scan_history(bucket: str, registry: dict[str, str],
                 stats: dict) -> None:
    """扫描 history/<bucket>/*.jsonl（含归档），从 content 字段提取行。"""
    hist_dir = HIST / bucket
    if not hist_dir.is_dir():
        return
    for fpath in sorted(hist_dir.glob("*.jsonl")):
        if fpath.name.endswith(".bak"):
            continue
        try:
            for line in fpath.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = entry.get("content") or ""
                for text_line in lines_from_text(content):
                    if not text_line:
                        continue
                    h = compute_hash(text_line, registry)
                    if h not in registry:
                        registry[h] = text_line
                        stats["new_lines"] += 1
                stats["history_entries"] += 1
        except Exception:
            continue
    stats["buckets_completed"] += 1


def main() -> int:
    t0 = time.time()

    OUT.mkdir(parents=True, exist_ok=True)

    buckets = sorted([
        d.name for d in PAGES.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ])

    total_stats = {
        "pages_scanned": 0,
        "history_entries": 0,
        "new_lines": 0,
        "buckets_completed": 0,
        "errors": [],
    }
    index_bytes = 0

    for bucket in buckets:
        registry: dict[str, str] = {}
        stats = {
            "pages_scanned": 0,
            "history_entries": 0,
            "new_lines": 0,
            "buckets_completed": 0,
        }

        scan_pages(bucket, registry, stats)
        # 先扫历史版本，确保已删除行也有索引
        scan_history(bucket, registry, stats)

        out_path = OUT / f"{bucket}.json"
        json_str = json.dumps(registry, ensure_ascii=False, sort_keys=True)
        out_path.write_text(json_str, encoding="utf-8")

        sz = out_path.stat().st_size
        index_bytes += sz
        el = time.time() - t0
        print(f"  {bucket}/  {stats['pages_scanned']:4d} 页  "
              f"{len(registry):6d} 唯一行  {sz/1024:7.1f} KB  "
              f"({el:.0f}s)")

        for k in total_stats:
            if k == "errors":
                continue
            total_stats[k] += stats.get(k, 0)

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"完成: {total_stats['buckets_completed']} 桶  "
          f"{total_stats['pages_scanned']} 页  "
          f"{total_stats['history_entries']} 历史条目")
    print(f"唯一行总数: {total_stats['new_lines']}")
    print(f"索引总大小: {index_bytes/1024/1024:.1f} MB")
    print(f"耗时: {elapsed:.1f}s")
    print(f"{'='*60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
