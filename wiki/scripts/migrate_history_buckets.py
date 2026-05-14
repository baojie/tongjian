#!/usr/bin/env python3
"""
migrate_history_buckets.py — 将 history/ 下的 .jsonl 文件按页面名拼音前缀分片到子目录。

和 pages/ 分桶使用同一算法（page_bucket），确保 history/ 和 pages/ 的目录结构一致。

用法：
    python3 wiki/scripts/migrate_history_buckets.py [--dry-run]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from page_bucket import page_bucket

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "public" / "history"
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "history_bucket_migration.jsonl"


def migrate(dry_run: bool = False) -> None:
    """扫描 history/ 下所有 *.jsonl 主文件，按 page_bucket 移入子目录。"""
    # 收集所有主文件（非归档文件，即名中不含 .N. 模式）
    main_files = []
    for f in sorted(HIST.iterdir()):
        if not f.name.endswith(".jsonl"):
            continue
        # 跳过已存在的桶目录
        if f.is_dir():
            continue
        # 主文件：不包含 .\d+.jsonl 模式
        stem = f.stem  # 如 "刘备" 或 "刘备.1"
        if stem.rsplit(".", 1)[-1].isdigit():
            continue  # 归档文件如 刘备.1.jsonl
        main_files.append(f)

    total = len(main_files)
    print(f"扫描到 {total} 个主 history 文件")

    ok = 0
    errors = 0
    skipped = 0

    for f in main_files:
        slug = f.stem  # 页面名
        bucket = page_bucket(slug)
        target_dir = HIST / bucket
        target = target_dir / f.name

        if target.exists():
            # 归档文件也需检查是否存在
            print(f"  ⏭ {slug} → {bucket}/ — 目标已存在")
            skipped += 1
            continue

        if dry_run:
            print(f"  · {slug} → {bucket}/{f.name}")
            ok += 1
            continue

        target_dir.mkdir(parents=True, exist_ok=True)

        # 移动主文件
        f.rename(target)

        # 移动对应的归档文件（如 刘备.1.jsonl, 刘备.2.jsonl）
        archives = list(HIST.glob(f"{slug}.*.jsonl"))
        for af in archives:
            af_stem = af.stem
            if af_stem.rsplit(".", 1)[-1].isdigit():
                af_target = target_dir / af.name
                if not af_target.exists():
                    af.rename(af_target)
                else:
                    print(f"  ⚠ {af.name} 归档目标已存在，跳过")

        # 记录迁移日志
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as log:
            log.write(
                json.dumps(
                    {
                        "slug": slug,
                        "bucket": bucket,
                        "file": f.name,
                        "timestamp": datetime.now().isoformat(),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

        ok += 1
        if ok % 500 == 0:
            print(f"  进度: {ok}/{total}")

    print(f"\n完成: {ok} 迁移, {skipped} 跳过, {errors} 错误")
    if dry_run:
        print(f"DRY-RUN: 加 --apply 实际执行")


def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("[DRY-RUN] 预览模式")
    migrate(dry_run=dry_run)


if __name__ == "__main__":
    main()
