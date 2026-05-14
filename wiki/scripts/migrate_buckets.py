#!/usr/bin/env python3
"""migrate_buckets.py — 将 pages/ 下所有页面按拼音前缀迁移到子目录。

用法:
    python3 wiki/scripts/migrate_buckets.py [--dry-run]

安全:
    - 使用 rename（同一 filesystem）而非复制再删除
    - 记录迁移日志到 wiki/logs/bucket_migration.jsonl
    - --dry-run 只预览不执行
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# 确保 page_bucket 可导入
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from page_bucket import page_bucket  # noqa: E402

PAGES = ROOT / "wiki/public/pages"
LOG_DIR = ROOT / "wiki/logs"
LOG_FILE = LOG_DIR / "bucket_migration.jsonl"


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    if not PAGES.is_dir():
        print(f"[error] pages dir not found: {PAGES}", file=sys.stderr)
        sys.exit(1)

    md_files = sorted(PAGES.glob("*.md"))
    total = len(md_files)
    print(f"Found {total} .md files in {PAGES}")

    # 计算每个文件的 bucket
    moves: list[tuple[Path, str, str]] = []  # (src, slug, bucket)
    for f in md_files:
        slug = f.stem
        bucket = page_bucket(slug)
        moves.append((f, slug, bucket))

    # 检查冲突：同 slug 被分到不同 bucket（理论上不可能，但检查一下）
    slug_buckets: dict[str, str] = {}
    for f, slug, bucket in moves:
        if slug in slug_buckets and slug_buckets[slug] != bucket:
            print(f"[warn] CONFLICT: {slug} → {slug_buckets[slug]} and {bucket}")
        slug_buckets[slug] = bucket

    # 统计分桶
    bucket_counts: dict[str, int] = {}
    for _, _, bucket in moves:
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

    print(f"\nBucket distribution ({len(bucket_counts)} buckets):")
    for b, c in sorted(bucket_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"  {b}/: {c}")
    print(f"  ... ({len(bucket_counts) - 10} more)")
    counts = sorted(bucket_counts.values())
    print(f"  Max: {counts[-1]}, Avg: {sum(counts)/len(counts):.1f}, Min: {counts[0]}")

    if dry_run:
        print("\n[dry-run] No files moved.")
        print("To execute: python3 wiki/scripts/migrate_buckets.py")
        return

    # 确认
    print(f"\nAbout to move {total} files into {len(bucket_counts)} buckets. Continue? [y/N] ", end="")
    resp = input().strip().lower()
    if resp != "y":
        print("Aborted.")
        return

    # 执行迁移
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_entries = []
    moved = 0
    errors = 0

    for src, slug, bucket in moves:
        dest_dir = PAGES / bucket
        dest = dest_dir / f"{slug}.md"

        if dest.exists():
            print(f"[error] destination exists, skipping: {dest}", file=sys.stderr)
            errors += 1
            continue

        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            src.rename(dest)
            log_entries.append({
                "slug": slug,
                "bucket": bucket,
                "src": str(src.relative_to(PAGES)),
                "dest": str(dest.relative_to(PAGES)),
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
            moved += 1
        except OSError as e:
            print(f"[error] failed to move {src.name}: {e}", file=sys.stderr)
            errors += 1

    # 写日志
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        for entry in log_entries:
            log.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"\nDone: {moved} moved, {errors} errors")
    print(f"Log: {LOG_FILE}")


if __name__ == "__main__":
    main()
