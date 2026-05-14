#!/usr/bin/env python3
"""build_line_index.py — 构建全局行索引。

扫描所有页面和历史版本，为每个唯一行计算 base62 hash，
按 hash_bucket 分入 992 个桶，输出到 wiki/public/line_index/<bucket>.json。

不同页面中的相同行内容共享同一个 hash + 索引条目。
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
BASE62 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'

sys.path.insert(0, str(ROOT / "wiki/scripts"))
from page_bucket import hash_bucket  # noqa: E402


def _hex_to_base62(hex_str: str) -> str:
    n = int(hex_str, 16)
    chars = []
    while n:
        chars.append(BASE62[n % 62])
        n //= 62
    return ''.join(reversed(chars))


def compute_hash(line: str, registry: dict[str, str]) -> str:
    """为 line 计算唯一 base62 hash（碰撞时延长）。"""
    b62 = _hex_to_base62(hashlib.sha256(line.encode("utf-8")).hexdigest())
    for length in range(MIN_HASH_LEN, 17):
        h = b62[:length]
        if h not in registry or registry[h] == line:
            return h
    raise RuntimeError(f"无法为行生成唯一 hash（16 位仍有碰撞）: {line[:60]}")


def lines_from_text(text: str) -> list[str]:
    return text.splitlines()


def scan_pages(registry: dict[str, str], stats: dict) -> None:
    """扫描 pages/ 下所有桶的 .md 文件，注册所有行。"""
    for bucket_dir in sorted(PAGES.iterdir()):
        if not bucket_dir.is_dir() or bucket_dir.name.startswith("."):
            continue
        for fpath in sorted(bucket_dir.glob("*.md")):
            try:
                text = fpath.read_text(encoding="utf-8")
            except Exception:
                continue
            for line in lines_from_text(text):
                h = compute_hash(line, registry)
                if h not in registry:
                    registry[h] = line
                    stats["new_lines"] += 1
            stats["pages_scanned"] += 1


def scan_history(registry: dict[str, str], stats: dict) -> None:
    """扫描 history/ 下所有桶的 .jsonl（含归档），从 content 字段提取行。"""
    for bucket_dir in sorted(HIST.iterdir()):
        if not bucket_dir.is_dir() or bucket_dir.name.startswith("."):
            continue
        for fpath in sorted(bucket_dir.glob("*.jsonl")):
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
                        h = compute_hash(text_line, registry)
                        if h not in registry:
                            registry[h] = text_line
                            stats["new_lines"] += 1
                    summary = entry.get("summary") or entry.get("su") or ""
                    if summary:
                        h = compute_hash(summary, registry)
                        if h not in registry:
                            registry[h] = summary
                            stats["new_lines"] += 1
                    stats["history_entries"] += 1
            except Exception:
                continue


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)

    registry: dict[str, str] = {}
    stats = {"pages_scanned": 0, "history_entries": 0, "new_lines": 0}

    print("扫描页面...")
    scan_pages(registry, stats)
    print(f"  {stats['pages_scanned']} 页, {stats['new_lines']} 唯一行")

    print("扫描历史...")
    scan_history(registry, stats)
    print(f"  {stats['history_entries']} 历史条目, {stats['new_lines']} 唯一行")

    # 按 hash_bucket 分区
    print("按 hash 分桶...")
    buckets: dict[str, dict[str, str]] = {}
    for h, content in registry.items():
        b = hash_bucket(h)
        if b not in buckets:
            buckets[b] = {}
        buckets[b][h] = content

    n_buckets = len(buckets)
    index_bytes = 0

    for b in sorted(buckets):
        reg = buckets[b]
        out_path = OUT / f"{b}.json"
        json_str = json.dumps(reg, ensure_ascii=False, sort_keys=True)
        out_path.write_text(json_str, encoding="utf-8")
        sz = out_path.stat().st_size
        index_bytes += sz
        if n_buckets <= 100 or sz > 1024 * 100:
            print(f"  {b}/  {len(reg):6d} 行  {sz/1024:7.1f} KB")
        else:
            print(f"  .", end="", flush=True)

    if n_buckets > 100:
        print()

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"完成: {n_buckets} 桶  {stats['pages_scanned']} 页  "
          f"{stats['history_entries']} 历史条目")
    print(f"唯一行总数: {stats['new_lines']}")
    print(f"索引总大小: {index_bytes/1024/1024:.1f} MB")
    print(f"耗时: {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
